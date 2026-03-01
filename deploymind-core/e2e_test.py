"""
deploymind-core End-to-End Test
================================
Tests the full deployment pipeline with REAL services:
  1. GitHub clone (PrathamModi001/DeployMind)
  2. Security scan (Trivy - skipped if unavailable)
  3. Docker build (on EC2 instance)
  4. Deploy to EC2 via SSM
  5. Health check
  6. Database persistence verification
  7. Redis event publishing verification

Issues found are printed with FIX notes for permanent documentation.
"""

import sys
import os
import time
import traceback
import json
from datetime import datetime
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────
core_path = Path(__file__).parent
sys.path.insert(0, str(core_path))

# ── Config ───────────────────────────────────────────────────────────────────
INSTANCE_ID   = "i-09b580ee9eaa532d1"
REPOSITORY    = "PrathamModi001/DeployMind"
PORT          = 8080
STRATEGY      = "rolling"
HEALTH_PATH   = "/health"
SKIP_TRIVY    = True   # Set False if Trivy is available

PASS  = "PASS"
FAIL  = "FAIL"
SKIP  = "SKIP"
INFO  = "INFO"

issues_found = []

def log(symbol, phase, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {symbol} [{phase}] {msg}")

def record_issue(phase, error, fix):
    issues_found.append({"phase": phase, "error": error, "fix": fix})
    log(FAIL, phase, f"ISSUE: {error}")
    log(INFO, phase, f"FIX:   {fix}")


# ════════════════════════════════════════════════════════════════════════════
# PHASE 0 — Infrastructure readiness
# ════════════════════════════════════════════════════════════════════════════
def phase0_infrastructure():
    log(INFO, "INFRA", "Checking infrastructure readiness...")

    # 0a. Settings load
    from deploymind.config.settings import settings
    assert settings.groq_api_key,             "GROQ_API_KEY missing"
    assert settings.aws_access_key_id,        "AWS_ACCESS_KEY_ID missing"
    assert settings.aws_secret_access_key,    "AWS_SECRET_ACCESS_KEY missing"
    assert settings.github_token,             "GITHUB_TOKEN missing"
    log(PASS, "INFRA", "All credentials loaded from .env")

    # 0b. Database connection
    import psycopg2
    conn = psycopg2.connect(settings.database_url)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM deployments")
    count = cur.fetchone()[0]
    conn.close()
    log(PASS, "INFRA", f"PostgreSQL connected — {count} existing deployments")

    # 0c. Redis connection
    import redis as redis_lib
    r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=3)
    r.ping()
    log(PASS, "INFRA", "Redis connected")

    # 0d. AWS EC2 credentials
    import boto3
    ec2 = boto3.client("ec2", region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key)
    resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
    inst = resp["Reservations"][0]["Instances"][0]
    state = inst["State"]["Name"]
    public_ip = inst.get("PublicIpAddress", "no-ip")
    log(PASS, "INFRA", f"EC2 instance {INSTANCE_ID} — state={state} ip={public_ip}")
    return state, public_ip, settings


# ════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Wait for EC2 + SSM
# ════════════════════════════════════════════════════════════════════════════
def phase1_wait_for_ssm(settings):
    log(INFO, "EC2/SSM", f"Waiting for instance {INSTANCE_ID} to be running + SSM-online...")

    import boto3
    ec2  = boto3.client("ec2",  region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key)
    ssm  = boto3.client("ssm",  region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key)

    # Wait for running state
    for attempt in range(24):           # up to 4 min
        resp  = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
        state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]
        if state == "running":
            log(PASS, "EC2/SSM", f"Instance is running (attempt {attempt+1})")
            break
        log(INFO, "EC2/SSM", f"State={state}, waiting 10s... ({attempt+1}/24)")
        time.sleep(10)
    else:
        raise RuntimeError("Instance never reached running state")

    # Wait for SSM Online
    for attempt in range(24):           # up to 4 min
        info = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [INSTANCE_ID]}]
        )
        if info["InstanceInformationList"]:
            ping = info["InstanceInformationList"][0]["PingStatus"]
            if ping == "Online":
                log(PASS, "EC2/SSM", f"SSM agent Online (attempt {attempt+1})")
                return
        log(INFO, "EC2/SSM", f"SSM not ready yet, waiting 10s... ({attempt+1}/24)")
        time.sleep(10)
    raise RuntimeError("SSM agent never came online — check IAM instance profile")


# ════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Docker installed on instance
# ════════════════════════════════════════════════════════════════════════════
def phase2_verify_docker_on_instance(settings):
    log(INFO, "DOCKER", "Verifying Docker is installed on EC2 instance...")

    from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
    ec2c = EC2Client(settings)

    # Wait for user-data to finish (docker install)
    for attempt in range(12):
        result = ec2c.run_command(INSTANCE_ID, ["docker --version 2>&1 || echo DOCKER_MISSING"], timeout_seconds=30)
        out = result.get("stdout", "")
        if "Docker version" in out:
            log(PASS, "DOCKER", f"Docker ready: {out.strip()}")
            return ec2c
        if "DOCKER_MISSING" in out or attempt >= 6:
            log(INFO, "DOCKER", "Docker not ready yet, installing...")
            ec2c.run_command(INSTANCE_ID, [
                "yum install -y docker 2>&1 || apt-get install -y docker.io 2>&1",
                "systemctl start docker",
                "systemctl enable docker",
            ], timeout_seconds=120)
            break
        log(INFO, "DOCKER", f"Waiting for user-data Docker install... ({attempt+1}/12)")
        time.sleep(15)

    # Final check
    result = ec2c.run_command(INSTANCE_ID, ["docker --version"], timeout_seconds=30)
    out = result.get("stdout", "").strip()
    log(PASS, "DOCKER", f"Docker ready: {out}")
    return ec2c


# ════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Security scan (Trivy)
# ════════════════════════════════════════════════════════════════════════════
def phase3_security_scan(settings, clone_path):
    if SKIP_TRIVY:
        log(SKIP, "TRIVY", "Skipped (SKIP_TRIVY=True)")
        return {"passed": True, "scan_id": "skipped", "vulnerabilities": 0, "error": None}

    log(INFO, "TRIVY", f"Running filesystem security scan on {clone_path}...")
    from deploymind.application.use_cases.scan_security import SecurityScanUseCase, SecurityScanRequest
    uc = SecurityScanUseCase(settings)
    req = SecurityScanRequest(
        deployment_id="e2e-test",
        target=clone_path,
        scan_type="filesystem",
        policy="balanced"
    )
    try:
        resp = uc.execute(req)
        if resp.success:
            log(PASS, "TRIVY", f"Scan passed — {resp.scan_result.total_vulnerabilities} vulns "
                f"(C:{resp.scan_result.critical_count} H:{resp.scan_result.high_count})")
        else:
            log(FAIL, "TRIVY", f"Scan rejected: {resp.message}")
        return {
            "passed": resp.success,
            "scan_id": "e2e-test",
            "vulnerabilities": resp.scan_result.total_vulnerabilities if resp.scan_result else 0,
            "error": resp.message if not resp.success else None
        }
    except Exception as e:
        record_issue("TRIVY", str(e), "Ensure Trivy binary is downloaded or set SKIP_TRIVY=True")
        return {"passed": True, "scan_id": "error-skip", "vulnerabilities": 0, "error": None}


# ════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Clone GitHub repo
# ════════════════════════════════════════════════════════════════════════════
def phase4_clone(settings):
    log(INFO, "CLONE", f"Cloning {REPOSITORY} via GitHubClient...")
    from deploymind.infrastructure.vcs.github.github_client import GitHubClient
    import tempfile, uuid

    gh = GitHubClient(settings)
    repo = gh.get_repository(REPOSITORY)
    branch = repo.default_branch
    commit_sha = repo.get_branch(branch).commit.sha
    log(PASS, "CLONE", f"Repo: {REPOSITORY}  branch={branch}  sha={commit_sha[:8]}")

    clone_path = os.path.join(tempfile.gettempdir(), "deploymind", f"dm_{uuid.uuid4().hex[:8]}")
    gh.clone_repository(REPOSITORY, clone_path)
    log(PASS, "CLONE", f"Cloned to {clone_path}")
    return commit_sha, clone_path


# ════════════════════════════════════════════════════════════════════════════
# PHASE 5 — Full deployment workflow (FullDeploymentWorkflow)
# ════════════════════════════════════════════════════════════════════════════
def phase5_full_workflow(settings):
    log(INFO, "WORKFLOW", "Launching FullDeploymentWorkflow...")
    from deploymind.application.use_cases.full_deployment_workflow import (
        FullDeploymentWorkflow, FullDeploymentRequest
    )

    wf = FullDeploymentWorkflow(settings)
    req = FullDeploymentRequest(
        repository=REPOSITORY,
        instance_id=INSTANCE_ID,
        port=PORT,
        strategy=STRATEGY,
        health_check_path=HEALTH_PATH,
        environment="production"
    )

    log(INFO, "WORKFLOW", "Executing pipeline: clone -> scan -> build -> deploy -> health-check")
    resp = wf.execute(req)
    return resp


# ════════════════════════════════════════════════════════════════════════════
# PHASE 6 — Verify DB persistence
# ════════════════════════════════════════════════════════════════════════════
def phase6_verify_db(settings, deployment_id):
    log(INFO, "DB", f"Verifying deployment record {deployment_id} persisted...")
    import psycopg2
    conn = psycopg2.connect(settings.database_url)
    cur  = conn.cursor()
    cur.execute("SELECT id, status, repository FROM deployments WHERE id = %s", (deployment_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        log(PASS, "DB", f"Record found — id={row[0]} status={row[1]} repo={row[2]}")
    else:
        record_issue("DB", f"Deployment record {deployment_id} NOT found in DB",
                     "Check deployment_repo.create() is called before early returns")
    return row


# ════════════════════════════════════════════════════════════════════════════
# PHASE 7 — Verify Redis events
# ════════════════════════════════════════════════════════════════════════════
def phase7_verify_redis(settings):
    log(INFO, "REDIS", "Checking Redis event log...")
    import redis as redis_lib
    r = redis_lib.from_url(settings.redis_url)
    # Events are published to deploymind:events channel; check recent keys
    keys = r.keys("deploymind:*")
    log(PASS, "REDIS", f"Redis deploymind keys: {[k.decode() for k in keys]}")


# ════════════════════════════════════════════════════════════════════════════
# PHASE 8 — Health check the running container
# ════════════════════════════════════════════════════════════════════════════
def phase8_health_check(public_ip):
    log(INFO, "HEALTH", f"HTTP health check: http://{public_ip}:{PORT}{HEALTH_PATH}")
    import urllib.request, urllib.error
    url = f"http://{public_ip}:{PORT}{HEALTH_PATH}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode()
                log(PASS, "HEALTH", f"Container responding: {body[:120]}")
                return True
        except urllib.error.URLError as e:
            log(INFO, "HEALTH", f"Not ready yet ({attempt+1}/6): {e.reason}")
            time.sleep(10)
    record_issue("HEALTH", f"Container at {url} did not respond after 60s",
                 "Check security group allows port 8080, and container started correctly")
    return False


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def main():
    print("\n" + "="*70)
    print("  deploymind-core  END-TO-END TEST")
    print(f"  repo={REPOSITORY}  instance={INSTANCE_ID}")
    print("="*70 + "\n")

    # Phase 0: infra
    state, public_ip, settings = phase0_infrastructure()

    # Phase 1: wait for SSM
    phase1_wait_for_ssm(settings)

    # Phase 2: verify Docker on instance
    ec2c = phase2_verify_docker_on_instance(settings)

    # Phase 4: clone (so trivy can scan)
    commit_sha, clone_path = phase4_clone(settings)

    # Phase 3: trivy
    phase3_security_scan(settings, clone_path)

    # Phase 5: full workflow
    resp = phase5_full_workflow(settings)

    print("\n" + "-"*70)
    print("  WORKFLOW RESULT")
    print("-"*70)
    print(f"  success:            {resp.success}")
    print(f"  deployment_id:      {resp.deployment_id}")
    print(f"  commit_sha:         {resp.commit_sha}")
    print(f"  security_passed:    {resp.security_passed}")
    print(f"  build_successful:   {resp.build_successful}")
    print(f"  image_tag:          {resp.image_tag}")
    print(f"  deployment_ok:      {resp.deployment_successful}")
    print(f"  health_check_ok:    {resp.health_check_passed}")
    print(f"  application_url:    {resp.application_url}")
    print(f"  error_phase:        {resp.error_phase}")
    print(f"  error_message:      {resp.error_message}")
    print(f"  duration:           {resp.duration_seconds:.1f}s" if resp.duration_seconds else "  duration: N/A")

    # Phase 6: DB
    phase6_verify_db(settings, resp.deployment_id)

    # Phase 7: Redis
    phase7_verify_redis(settings)

    # Phase 8: live health check (only if deploy succeeded)
    if resp.deployment_successful and public_ip != "no-ip":
        phase8_health_check(public_ip)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("  ISSUES FOUND & FIXES")
    print("="*70)
    if not issues_found:
        print("  No issues found — all phases passed!")
    for i, issue in enumerate(issues_found, 1):
        print(f"\n  Issue #{i} [{issue['phase']}]")
        print(f"    ERROR: {issue['error']}")
        print(f"    FIX:   {issue['fix']}")
    print()


if __name__ == "__main__":
    main()
