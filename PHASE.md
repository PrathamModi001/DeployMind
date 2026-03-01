# DeployMind — Production Implementation Plan

> **Starting point audit**: Clean Architecture ✅ | Security Agent ✅ | Rolling Deployer ✅ |
> Deploy Agent tools ✅ (wired to RollingDeployer) | Build Agent ❌ (all stubs) |
> GitHub Webhooks ❌ | Kubernetes ❌ | Deployment Queue ❌ | Canary Strategy ❌ | CLI ❌

---

## Phase 1 — Fix What's Broken (Day 1, ~4–6 hours)

These are blocking bugs. Nothing else works until these are done.

### 1.1 Fix the Groq LLM Parameter Bug in `deploy_agent.py`

**File**: `deploymind-core/deploymind/agents/deploy_agent.py`

**Problem**: `create_deploy_agent()` (line 312) instantiates a raw `Groq` client and passes it as
`llm=` to CrewAI's `Agent`. CrewAI does not accept a raw Groq SDK object — it expects either a
string model identifier (`"groq/llama-3.1-70b-versatile"`) or a LangChain-compatible LLM.
This crashes at runtime when the agent is invoked.

**Fix**: Change the function signature to accept `groq_api_key: str` but pass a string model name
to `Agent`, matching the pattern used by the Security Agent:

```python
# Remove this:
from groq import Groq
llm = Groq(api_key=groq_api_key, model="llama-3.1-70b-versatile")
Agent(..., llm=llm)

# Replace with:
import os
os.environ["GROQ_API_KEY"] = groq_api_key
Agent(..., llm="groq/llama-3.1-70b-versatile")
```

**Also fix**: The `build_agent.py` `create_build_agent()` already uses a string, but passes
`llm: str = "llama-3.1-70b-versatile"` without the `groq/` prefix required by LiteLLM
(which CrewAI uses under the hood). Change the default to `"groq/llama-3.1-70b-versatile"`.

---

### 1.2 Fix the Security Agent Import

**File**: `deploymind-core/deploymind/agents/security_agent.py`

**Problem**: Line 6 imports `from core.logger import get_logger` — but the module is
`deploymind.shared.secure_logging`. This means `security_agent.py` crashes on import if
you're not running from a specific working directory. The deploy_agent.py imports it correctly.

**Fix**: Change to `from deploymind.shared.secure_logging import get_logger`

Same issue in `build_agent.py` line 6 — fix identically.

---

## Phase 2 — Complete the Build Agent (Day 1–2, ~8–10 hours)

**File**: `deploymind-core/deploymind/agents/build_agent.py`

The build agent is the single most critical gap. Every tool is `raise NotImplementedError`.
The full pipeline (Security → Build → Deploy) cannot run end-to-end without this.

### 2.1 Implement `detect_language`

Strategy: walk the repo directory and check for indicator files. Return a structured JSON string
so the LLM can parse it.

```
Indicator files to check (in priority order):
  Node.js   → package.json  (also check for express, fastapi, next, nest in dependencies)
  Python    → requirements.txt, pyproject.toml, setup.py, Pipfile
  Go        → go.mod
  Java      → pom.xml, build.gradle
  Ruby      → Gemfile
  Rust      → Cargo.toml
  PHP       → composer.json

Framework detection (secondary pass):
  Node: check package.json "dependencies" for express/fastapi/next/nest/hapi
  Python: check requirements.txt for flask/fastapi/django/tornado
  Go: check go.mod for gin/echo/fiber/chi

Return format (string for CrewAI):
  "Language: Python | Framework: FastAPI | Entry: main.py | Has Dockerfile: No"
```

Files to create:
- `deploymind-core/deploymind/infrastructure/build/language_detector.py`
  — `LanguageDetector` class with `detect(repo_path: str) -> DetectionResult`
  — `DetectionResult` dataclass: language, framework, entry_point, has_dockerfile, has_dockerignore

### 2.2 Implement `generate_dockerfile`

Strategy: template-based generation. Do NOT call the LLM to write a Dockerfile — that's
unreliable. Generate a known-good multi-stage template per language, then optionally pass it
to the LLM for review/optimization commentary.

Files to create:
- `deploymind-core/deploymind/infrastructure/build/dockerfile_generator.py`
  — `DockerfileGenerator` class with `generate(detection_result) -> str`
  — Templates (multi-stage, non-root user, minimal base image):

```
Node.js template:
  Stage 1: node:20-alpine AS builder → npm ci → npm run build
  Stage 2: node:20-alpine → copy node_modules + dist → USER node → EXPOSE 3000

Python template:
  Stage 1: python:3.12-slim AS builder → pip install --user -r requirements.txt
  Stage 2: python:3.12-slim → copy --from=builder ~/.local → RUN useradd app → EXPOSE 8000

Go template:
  Stage 1: golang:1.22-alpine AS builder → go mod download → go build -o app
  Stage 2: gcr.io/distroless/static → copy binary → EXPOSE 8080
  (Produces smallest possible image — great demo metric)

Java template:
  Stage 1: maven:3.9-eclipse-temurin-21 AS builder → mvn package -DskipTests
  Stage 2: eclipse-temurin:21-jre-alpine → copy jar → EXPOSE 8080
```

Also generate a `.dockerignore` file alongside the Dockerfile:
- Node: `node_modules`, `.git`, `.env`, `*.log`, `coverage`
- Python: `__pycache__`, `.git`, `.env`, `venv`, `*.pyc`, `.pytest_cache`
- Go: `.git`, `.env`, `*_test.go`

### 2.3 Implement `execute_docker_build`

Strategy: `subprocess.run(['docker', 'build', ...])` with streaming output. Capture image ID
and size from the output. Store build log in DB.

```python
# Command to run:
docker build -t {image_tag} -f {dockerfile_path} {context_path}

# Capture image size after build:
docker image inspect {image_tag} --format='{{.Size}}'

# Stream stdout/stderr line-by-line using subprocess.Popen (not subprocess.run)
# This lets us show build progress in real time
```

Key metrics to extract and return:
- Build success/failure
- Image size in MB
- Build duration in seconds
- Number of layers
- Any warnings from Docker (deprecated instructions etc.)

Files to create:
- `deploymind-core/deploymind/infrastructure/build/docker_builder.py`
  — `DockerBuilder` class with `build(image_tag, dockerfile_path, context_path) -> BuildResult`
  — `BuildResult` dataclass: success, image_tag, image_size_mb, duration_seconds, build_log, layers

### 2.4 Implement `optimize_dockerfile`

Strategy: rule-based checks first (no LLM dependency), then optionally pass to Groq for
natural language explanation. Rule-based is more reliable and testable.

Rules to check:
- Is a non-root USER set? (security)
- Is multi-stage build used? (size)
- Does `.dockerignore` exist? (build context size)
- Are `COPY` commands ordered by change frequency? (layer caching)
- Is the base image pinned to a specific digest/tag? (reproducibility)
- Is `apt-get` followed immediately by `rm -rf /var/lib/apt/lists/*`? (size)
- Is `pip install` using `--no-cache-dir`? (size)

Return: list of findings with severity (warning/info) and suggested fix.

### 2.5 Wire Build Agent Tools to Infrastructure

Update `build_agent.py` tools to call the new infrastructure classes:

```python
@tool("Detect Language")
def detect_language(repo_path: str) -> str:
    from deploymind.infrastructure.build.language_detector import LanguageDetector
    result = LanguageDetector().detect(repo_path)
    return f"Language: {result.language} | Framework: {result.framework} | ..."

@tool("Generate Dockerfile")
def generate_dockerfile(repo_path: str, language: str) -> str:
    from deploymind.infrastructure.build.dockerfile_generator import DockerfileGenerator
    from deploymind.infrastructure.build.language_detector import DetectionResult
    # Parse language string back to DetectionResult, generate dockerfile
    content = DockerfileGenerator().generate(detection)
    # Write to repo_path/Dockerfile
    return f"Dockerfile written to {dockerfile_path}\n\n{content}"

@tool("Build Docker Image")
def build_docker_image(dockerfile_path: str, image_tag: str) -> str:
    from deploymind.infrastructure.build.docker_builder import DockerBuilder
    result = DockerBuilder().build(image_tag, dockerfile_path, context_path)
    return f"Build {'succeeded' if result.success else 'failed'} | Size: {result.image_size_mb}MB | Duration: {result.duration_seconds}s"

@tool("Optimize Docker Image")
def optimize_docker_image(dockerfile_content: str) -> str:
    from deploymind.infrastructure.build.dockerfile_optimizer import DockerfileOptimizer
    findings = DockerfileOptimizer().analyze(dockerfile_content)
    return "\n".join(f"[{f.severity.upper()}] {f.message} → {f.suggestion}" for f in findings)
```

### 2.6 Write Tests for Build Agent

Files to create:
- `tests/unit/infrastructure/test_language_detector.py`
  — Test each language with fixture repo directories
  — Test framework detection within Node/Python
  — Test fallback when no indicators found

- `tests/unit/infrastructure/test_dockerfile_generator.py`
  — Test each language template generates valid Dockerfile syntax
  — Test non-root user is present in all templates
  — Test multi-stage build is present

- `tests/unit/infrastructure/test_docker_builder.py`
  — Mock `subprocess.Popen` — test success/failure paths
  — Test image size extraction from `docker inspect` output
  — Test build log capture

Target: 20+ new tests, all passing without Docker installed (via mocking).

---

## Phase 3 — GitHub Webhook Integration (Day 3, ~6–8 hours)

Auto-trigger deployments on push to `main`. Post deployment status back to PRs.
This makes DeployMind a real CD tool, not a manual deploy script.

### 3.1 Webhook Receiver

**File**: `deploymind-core/deploymind/presentation/api/routes/webhooks.py`

FastAPI router with one endpoint: `POST /webhooks/github`

```python
@router.post("/webhooks/github")
async def github_webhook(request: Request):
    # Step 1: Verify HMAC-SHA256 signature (X-Hub-Signature-256 header)
    # Step 2: Parse event type from X-GitHub-Event header
    # Step 3: Route to handler:
    #   "push" + ref=="refs/heads/main" → enqueue deployment
    #   "pull_request" + action=="opened"/"synchronize" → enqueue preview deploy
    #   "ping" → return 200 OK (GitHub sends this on webhook creation)
    # Step 4: Return 200 immediately (async — don't block on deployment)
```

HMAC verification (critical — without this, anyone can trigger deploys):
```python
import hashlib, hmac

def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)  # timing-safe comparison
```

New environment variable: `GITHUB_WEBHOOK_SECRET` — must match what's set in GitHub repo settings.

### 3.2 GitHub Status API Integration

**File**: `deploymind-core/deploymind/infrastructure/vcs/github/github_client.py`

Add three new methods:

```python
def post_deployment_status(
    repo: str, sha: str, state: str, description: str, target_url: str
) -> None:
    """Post commit status (pending/success/failure/error) to GitHub.
    Shows as a check on PRs and commits."""
    # POST /repos/{owner}/{repo}/statuses/{sha}
    # state: "pending" | "success" | "failure" | "error"

def create_pr_comment(repo: str, pr_number: int, body: str) -> None:
    """Post a comment on a PR with deployment result."""
    # POST /repos/{owner}/{repo}/issues/{pr_number}/comments

def get_pr_for_branch(repo: str, branch: str) -> Optional[int]:
    """Find open PR number for a branch, if one exists."""
    # GET /repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open
```

PR comment format (looks professional):
```
## DeployMind Deployment Report
| Field | Value |
|-------|-------|
| Status | ✅ Deployed |
| Commit | `abc1234` |
| Branch | `feature/auth` |
| Image | `myapp:abc1234` |
| Duration | 47s |
| Health | 12/12 checks passed |
| Strategy | Rolling |

[View deployment logs →](#)
```

### 3.3 Deployment Event Bus

**File**: `deploymind-core/deploymind/infrastructure/vcs/github/webhook_parser.py`

Parse the raw GitHub webhook JSON into a clean domain event:

```python
@dataclass
class PushEvent:
    repository: str   # "owner/repo"
    branch: str       # "main"
    commit_sha: str   # "abc1234..."
    commit_message: str
    pusher: str       # GitHub username
    compare_url: str  # Link to diff

@dataclass
class PullRequestEvent:
    repository: str
    pr_number: int
    branch: str       # head branch
    commit_sha: str
    action: str       # "opened" | "synchronize" | "closed"
    title: str
```

### 3.4 Register Webhook Router

**File**: `deploymind-core/deploymind/presentation/api/__init__.py` or the FastAPI app entrypoint.

Register the webhooks router:
```python
from deploymind.presentation.api.routes.webhooks import router as webhook_router
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])
```

---

## Phase 4 — Deployment Queue & Distributed Locking (Day 3–4, ~6 hours)

Prevent race conditions when multiple pushes happen in quick succession.
Without a queue, two concurrent deploys to the same instance will corrupt each other.

### 4.1 Deployment Queue

**File**: `deploymind-core/deploymind/infrastructure/queue/deployment_queue.py`

Use Redis lists as a simple, reliable FIFO queue (no extra dependencies beyond existing Redis):

```python
class DeploymentQueue:
    """Redis-backed queue for serializing deployments per environment."""

    QUEUE_KEY = "deploymind:queue:{environment}"  # one queue per environment
    PROCESSING_KEY = "deploymind:processing:{environment}"

    def enqueue(self, job: DeploymentJob) -> str:
        """Add deployment job to queue. Returns job ID."""
        job_id = str(uuid4())
        payload = json.dumps(dataclasses.asdict(job))
        self.redis.lpush(self.QUEUE_KEY.format(environment=job.environment), payload)
        return job_id

    def dequeue(self, environment: str, timeout: int = 30) -> Optional[DeploymentJob]:
        """Block until a job is available (BRPOPLPUSH for reliability)."""
        # BRPOPLPUSH moves job to processing list atomically
        # If worker crashes, job stays in processing list for recovery
        result = self.redis.brpoplpush(
            self.QUEUE_KEY.format(environment=environment),
            self.PROCESSING_KEY.format(environment=environment),
            timeout=timeout
        )
        return DeploymentJob(**json.loads(result)) if result else None

    def ack(self, environment: str, job: DeploymentJob) -> None:
        """Remove job from processing list after successful completion."""
        self.redis.lrem(self.PROCESSING_KEY.format(environment=environment), 1,
                        json.dumps(dataclasses.asdict(job)))

    def queue_depth(self, environment: str) -> int:
        """How many jobs are waiting."""
        return self.redis.llen(self.QUEUE_KEY.format(environment=environment))
```

`DeploymentJob` dataclass:
```python
@dataclass
class DeploymentJob:
    job_id: str
    repository: str      # "owner/repo"
    commit_sha: str
    branch: str
    instance_id: str
    environment: str     # "production" | "staging"
    strategy: str        # "rolling" | "canary"
    triggered_by: str    # "webhook" | "cli" | "api"
    created_at: str      # ISO 8601
    priority: int = 0    # Higher = processed first (for manual triggers)
```

### 4.2 Distributed Lock

**File**: `deploymind-core/deploymind/infrastructure/queue/distributed_lock.py`

Redis-based lock using `SET NX PX` (atomic set-if-not-exists with TTL).
Prevents two workers from deploying to the same instance simultaneously.

```python
class DistributedLock:
    """Redis-based distributed lock with automatic expiry.

    Implements the Redlock pattern for single-node Redis.
    The lock key is per-instance, so two different instances
    can be deployed to simultaneously.
    """

    LOCK_KEY = "deploymind:lock:instance:{instance_id}"
    DEFAULT_TTL_MS = 600_000  # 10 minutes max deployment time

    def acquire(self, instance_id: str, owner_id: str, ttl_ms: int = DEFAULT_TTL_MS) -> bool:
        """Try to acquire lock. Returns True if acquired, False if already locked."""
        key = self.LOCK_KEY.format(instance_id=instance_id)
        # SET key owner_id NX PX ttl_ms — atomic: only sets if key doesn't exist
        result = self.redis.set(key, owner_id, nx=True, px=ttl_ms)
        return result is not None

    def release(self, instance_id: str, owner_id: str) -> bool:
        """Release lock only if we own it (Lua script for atomicity)."""
        # Lua ensures check-and-delete is atomic
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        key = self.LOCK_KEY.format(instance_id=instance_id)
        return bool(self.redis.eval(lua_script, 1, key, owner_id))

    def extend(self, instance_id: str, owner_id: str, ttl_ms: int = DEFAULT_TTL_MS) -> bool:
        """Extend lock TTL if we still own it (heartbeat pattern)."""
        # Same Lua pattern: check owner then PEXPIRE
        ...

    @contextmanager
    def locked(self, instance_id: str):
        """Context manager: acquire → yield → release. Raises if can't acquire."""
        owner_id = str(uuid4())
        if not self.acquire(instance_id, owner_id):
            raise LockAcquisitionError(f"Instance {instance_id} is already being deployed to")
        try:
            yield
        finally:
            self.release(instance_id, owner_id)
```

Usage in the deployment pipeline:
```python
with distributed_lock.locked(instance_id):
    result = rolling_deployer.deploy(...)
```

### 4.3 Worker Process

**File**: `deploymind-core/deploymind/presentation/cli/worker.py`

A long-running process that pulls jobs from the queue and executes deployments:

```python
# Start with: deploymind worker --environment production

@click.command()
@click.option("--environment", default="production")
def worker(environment: str):
    """Process deployment queue for an environment."""
    queue = DeploymentQueue(container.redis_client)
    lock = DistributedLock(container.redis_client)

    click.echo(f"Worker started for environment: {environment}")

    while True:
        job = queue.dequeue(environment, timeout=30)
        if job is None:
            continue  # timeout, loop again

        click.echo(f"Processing job {job.job_id}: {job.repository}@{job.commit_sha[:8]}")

        try:
            with lock.locked(job.instance_id):
                # Run full pipeline: Security → Build → Deploy
                orchestrator.run_pipeline(job)
                queue.ack(environment, job)
        except LockAcquisitionError:
            # Re-queue with delay (simple: push to back of queue)
            time.sleep(30)
            queue.enqueue(job)
```

### 4.4 Register in DependencyContainer

**File**: `deploymind-core/deploymind/config/dependencies.py`

```python
from deploymind.infrastructure.queue.deployment_queue import DeploymentQueue
from deploymind.infrastructure.queue.distributed_lock import DistributedLock

class DependencyContainer:
    def __init__(self):
        ...existing...
        self.deployment_queue = DeploymentQueue(self.redis_client)
        self.distributed_lock = DistributedLock(self.redis_client)
```

---

## Phase 5 — Canary Deployment Strategy (Day 4–5, ~8 hours)

The DB schema already has `strategy` and `canary_percentage` columns. The domain models
reference it. Zero infrastructure exists. This adds the second deployment strategy, making
"multi-strategy deployment platform" accurate on the resume.

### 5.1 Canary Deployer

**File**: `deploymind-core/deploymind/infrastructure/deployment/canary_deployer.py`

Canary without a load balancer: run canary container on a different port on the same instance,
use nginx upstream weighting to split traffic. Controlled via SSM commands.

```
Deployment flow:
  1. Pull new image on EC2 instance (docker pull)
  2. Start canary container on port 8081 (production on 8080)
  3. Update nginx upstream via SSM:
       upstream backend {
           server localhost:8080 weight=9;  # production (90%)
           server localhost:8081 weight=1;  # canary (10%)
       }
  4. Monitor error rate for 5 minutes:
       - HTTP check both ports every 30s
       - If canary error rate > 5%: rollback nginx config, stop canary
  5. If healthy: shift to 50% (weight=1 each), wait 5 min
  6. If still healthy: shift to 100% (stop old container, move canary to 8080)
```

```python
@dataclass
class CanaryResult:
    success: bool
    deployment_id: str
    stages_completed: int     # 0=failed at 10%, 1=failed at 50%, 2=full rollout
    final_percentage: int     # 0, 10, 50, or 100
    error_rate_at_failure: Optional[float]
    rollback_performed: bool
    duration_seconds: int

class CanaryDeployer:
    STAGES = [
        CanaryStage(percentage=10, duration_seconds=300),   # 5 min at 10%
        CanaryStage(percentage=50, duration_seconds=300),   # 5 min at 50%
        CanaryStage(percentage=100, duration_seconds=0),    # Full rollout
    ]

    def deploy(self, ...) -> CanaryResult: ...
    def _update_nginx_weights(self, instance_id, prod_weight, canary_weight): ...
    def _measure_error_rate(self, instance_id, port, duration_seconds) -> float: ...
    def _rollback_nginx(self, instance_id): ...
```

### 5.2 Strategy Factory

**File**: `deploymind-core/deploymind/infrastructure/deployment/strategy_factory.py`

```python
class DeploymentStrategyFactory:
    @staticmethod
    def create(strategy: str, ec2_client, health_checker) -> BaseDeployer:
        if strategy == "rolling":
            return RollingDeployer(ec2_client, health_checker)
        elif strategy == "canary":
            return CanaryDeployer(ec2_client, health_checker)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
```

Update `rolling_deployer.py` and `canary_deployer.py` to both inherit from a `BaseDeployer`
abstract class with a `deploy(...) -> DeploymentResult` method.

### 5.3 Update Orchestrator to Use Strategy Factory

**File**: `deploymind-core/deploymind/agents/orchestrator.py`

The deploy task description passed to the Deploy Agent should include the strategy:
```python
deploy_task = Task(
    description=f"Deploy {image_tag} to {instance_id} using {strategy} strategy. "
                f"{'Use 10%→50%→100% traffic shifting.' if strategy=='canary' else 'Use zero-downtime rolling.'}"
)
```

---

## Phase 6 — Kubernetes Support (Day 5–7, ~12–16 hours)

Companies use Kubernetes, not raw EC2. This makes DeployMind enterprise-ready and is the
most impactful feature for SDE 2 interviews at mid-to-large companies.

### 6.1 Kubernetes Client

**File**: `deploymind-core/deploymind/infrastructure/cloud/kubernetes/k8s_client.py`

Use the official `kubernetes` Python client (already a common dependency). Supports both
EKS (AWS) and GKE (Google Cloud) — they both use the standard k8s API.

```python
from kubernetes import client, config

class KubernetesClient:
    """Kubernetes client supporting EKS and GKE via kubeconfig or in-cluster config."""

    def __init__(self, kubeconfig_path: Optional[str] = None, context: Optional[str] = None):
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path, context=context)
        else:
            config.load_incluster_config()  # For running inside k8s
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()

    def apply_deployment(self, namespace: str, manifest: dict) -> bool:
        """Create or update a Deployment via server-side apply."""

    def get_deployment_status(self, namespace: str, name: str) -> DeploymentStatus:
        """Get current rollout status: ready replicas, conditions, etc."""

    def rollout_restart(self, namespace: str, name: str) -> None:
        """Trigger rolling restart by patching deployment annotations."""

    def rollback_deployment(self, namespace: str, name: str) -> None:
        """Rollback to previous revision (kubectl rollout undo equivalent)."""

    def scale_deployment(self, namespace: str, name: str, replicas: int) -> None:
        """Scale deployment to N replicas."""

    def wait_for_rollout(self, namespace: str, name: str, timeout: int = 300) -> bool:
        """Poll until all replicas are ready or timeout."""

    def get_pod_logs(self, namespace: str, pod_name: str, tail: int = 100) -> str:
        """Get recent log lines from a pod."""

    def list_pods(self, namespace: str, label_selector: str) -> list[PodInfo]:
        """List pods matching a label selector."""
```

### 6.2 Kubernetes Manifest Generator

**File**: `deploymind-core/deploymind/infrastructure/cloud/kubernetes/resource_templates.py`

Generate production-ready k8s manifests. These are what the Build Agent's LLM reasoning
should produce — not hand-crafted YAML but generated from detected app metadata.

```python
class KubernetesManifestGenerator:
    def generate_deployment(
        self,
        app_name: str,
        image: str,
        replicas: int,
        port: int,
        env_vars: dict,
        resource_limits: ResourceLimits,
        strategy: str,       # "RollingUpdate" or "Recreate"
    ) -> dict:
        """Generate a Deployment manifest with sensible production defaults:
           - readinessProbe (HTTP check on /health, delay 10s, period 5s)
           - livenessProbe  (HTTP check on /health, delay 30s, period 10s)
           - resource requests AND limits (prevents OOM kills)
           - topologySpreadConstraints (spread across nodes/AZs)
           - securityContext (runAsNonRoot: true, readOnlyRootFilesystem: true)
           - terminationGracePeriodSeconds: 30
        """

    def generate_service(self, app_name: str, port: int, service_type: str = "ClusterIP") -> dict:
        """Generate Service manifest (ClusterIP for internal, LoadBalancer for external)."""

    def generate_hpa(self, app_name: str, min_replicas: int = 2, max_replicas: int = 10) -> dict:
        """Generate HorizontalPodAutoscaler (scale on CPU > 70%)."""

    def generate_pdb(self, app_name: str, min_available: int = 1) -> dict:
        """Generate PodDisruptionBudget (protect against node drains)."""

    def generate_configmap(self, app_name: str, env_vars: dict) -> dict:
        """Generate ConfigMap for non-secret environment variables."""
```

### 6.3 Kubernetes Deployment Strategies

**File**: `deploymind-core/deploymind/infrastructure/cloud/kubernetes/deployment_strategies.py`

K8s natively supports rolling updates. Canary and blue-green require additional resources:

```python
class K8sRollingDeployer:
    """Use k8s native RollingUpdate strategy.
       maxSurge: 1, maxUnavailable: 0 = true zero-downtime."""

    def deploy(self, namespace, app_name, new_image, ...) -> K8sDeployResult:
        # 1. Patch deployment image via apps_v1.patch
        # 2. Wait for rollout: poll until readyReplicas == desiredReplicas
        # 3. Return result with pod count, duration, etc.

class K8sCanaryDeployer:
    """Manual canary using two Deployments sharing a Service.
       canary-deployment: 1 replica (gets ~10% with 9 prod replicas)
       Production deployment is untouched during canary."""

    def deploy(self, namespace, app_name, new_image, ...) -> K8sDeployResult:
        # 1. Create {app}-canary Deployment with 1 replica, new image
        # 2. Monitor canary pod error rate (check pod logs for 5xx)
        # 3. If healthy: scale canary to 5, scale prod to 5 (50/50)
        # 4. If still healthy: update prod image, delete canary deployment
        # 5. If unhealthy: delete canary deployment (instant rollback)

class K8sBlueGreenDeployer:
    """Blue-green using two Deployments + Service selector switch.
       Green is live, Blue is the new version. Switch is instant."""

    def deploy(self, namespace, app_name, new_image, ...) -> K8sDeployResult:
        # 1. Deploy to blue slots (pods with label color=blue)
        # 2. Wait for blue to be fully ready
        # 3. Switch Service selector from color=green to color=blue (atomic)
        # 4. Monitor for 2 minutes
        # 5. If healthy: delete green pods
        # 6. If unhealthy: switch selector back to green (instant rollback)
```

### 6.4 Update Cloud Service Interface

**File**: `deploymind-core/deploymind/application/interfaces/cloud_service.py`

Add Kubernetes methods to the interface so the Application layer can use k8s via
dependency inversion (without knowing whether it's EKS, GKE, or local kind):

```python
class CloudService(ABC):
    # Existing EC2 methods...

    @abstractmethod
    def deploy_to_kubernetes(self, namespace: str, manifest: dict, strategy: str) -> bool: ...

    @abstractmethod
    def get_kubernetes_status(self, namespace: str, name: str) -> dict: ...

    @abstractmethod
    def rollback_kubernetes(self, namespace: str, name: str) -> bool: ...
```

### 6.5 Add k8s to DependencyContainer

**File**: `deploymind-core/deploymind/config/dependencies.py`

```python
from deploymind.infrastructure.cloud.kubernetes.k8s_client import KubernetesClient

class DependencyContainer:
    def __init__(self):
        ...
        # Optional: only if KUBECONFIG is set
        if settings.kubeconfig_path:
            self.k8s_client = KubernetesClient(settings.kubeconfig_path)
        else:
            self.k8s_client = None
```

New environment variable: `KUBECONFIG_PATH` (optional, falls back to EC2 if not set).

### 6.6 Add to Deploy Agent

Update the Deploy Agent's tools to include k8s:

```python
@tool("Deploy to Kubernetes")
def deploy_to_kubernetes(
    namespace: str,
    app_name: str,
    image_tag: str,
    strategy: str = "rolling",
    replicas: int = 3
) -> str:
    """Deploy a container to Kubernetes (EKS/GKE) using the specified strategy."""
    ...
```

---

## Phase 7 — Wire Up the CLI (Day 7, ~3–4 hours)

**File**: `deploymind-core/deploymind/presentation/cli/main.py`

Connect existing Click command stubs to the real DependencyContainer use cases.

### Commands to implement:

```bash
# Trigger a deployment manually
deploymind deploy owner/repo i-1234567890abcdef0 \
  --branch main \
  --strategy rolling \
  --port 8080

# Check deployment status
deploymind status <deployment-id>

# Rollback to previous version
deploymind rollback <deployment-id>

# Show recent deployments
deploymind list [--repository owner/repo] [--limit 10]

# Start the queue worker
deploymind worker --environment production

# Validate credentials and connectivity
deploymind validate
```

### Output formatting with Rich:

Use `rich.table.Table` for status output and `rich.progress.Progress` for live health check
progress. This makes the CLI demo-able — a good screenshot for the README.

```
╭──────────────────────────────────────────────────╮
│  DeployMind — Deployment Status                  │
├─────────────────┬────────────────────────────────┤
│ Deployment ID   │ dep-abc123                     │
│ Repository      │ owner/myapp                    │
│ Commit          │ abc1234 (fix: auth bug)        │
│ Status          │ ✅ deployed                    │
│ Strategy        │ rolling                        │
│ Duration        │ 47s                            │
│ Health Checks   │ 12/12 passed                   │
│ Image           │ myapp:abc1234 (142MB)          │
╰─────────────────┴────────────────────────────────╯
```

---

## Implementation Order (Day-by-Day)

| Day | Phase | Deliverable |
|-----|-------|-------------|
| 1   | 1 + start 2 | Fix 3 bugs (Groq param, imports) + language detector + dockerfile generator |
| 2   | 2 complete | Docker builder + optimizer + build agent wired + 20 tests passing |
| 3   | 3 + 4 | GitHub webhook with HMAC + deployment queue + distributed lock |
| 4   | 5 | Canary deployer + strategy factory + orchestrator update |
| 5   | 6.1–6.3 | k8s client + manifest generator + deployment strategies |
| 6   | 6.4–6.6 | k8s integrated into interface + DI container + deploy agent tool |
| 7   | 7 | CLI commands wired + Rich output formatting |

---

## Files to Create (Net New)

```
deploymind-core/deploymind/infrastructure/
├── build/
│   ├── __init__.py
│   ├── language_detector.py          # Phase 2.1
│   ├── dockerfile_generator.py       # Phase 2.2
│   ├── docker_builder.py             # Phase 2.3
│   └── dockerfile_optimizer.py       # Phase 2.4
├── queue/
│   ├── __init__.py
│   ├── deployment_queue.py           # Phase 4.1
│   └── distributed_lock.py          # Phase 4.2
├── deployment/
│   ├── canary_deployer.py            # Phase 5.1
│   └── strategy_factory.py          # Phase 5.2
└── cloud/
    └── kubernetes/
        ├── __init__.py
        ├── k8s_client.py             # Phase 6.1
        ├── resource_templates.py     # Phase 6.2
        └── deployment_strategies.py  # Phase 6.3

deploymind-core/deploymind/presentation/
└── api/
    └── routes/
        └── webhooks.py               # Phase 3.1
        └── github_integration.py     # Phase 3.2

tests/unit/infrastructure/
├── test_language_detector.py         # Phase 2.6
├── test_dockerfile_generator.py      # Phase 2.6
├── test_docker_builder.py            # Phase 2.6
├── test_deployment_queue.py          # Phase 4
├── test_distributed_lock.py          # Phase 4
└── test_k8s_manifest_generator.py    # Phase 6
```

## Files to Modify (Existing)

```
deploymind-core/deploymind/agents/
├── build_agent.py       — Wire 4 tools to infrastructure classes (Phase 2.5)
├── deploy_agent.py      — Fix Groq LLM param bug (Phase 1.1) + add k8s tool (Phase 6.6)
├── security_agent.py    — Fix import path (Phase 1.2)
└── orchestrator.py      — Pass strategy to deploy task (Phase 5.3)

deploymind-core/deploymind/application/interfaces/
└── cloud_service.py     — Add k8s abstract methods (Phase 6.4)

deploymind-core/deploymind/config/
└── dependencies.py      — Register queue, lock, k8s client (Phase 4.4 + 6.5)

deploymind-core/deploymind/infrastructure/vcs/github/
└── github_client.py     — Add 3 new methods: status API, PR comments (Phase 3.2)

deploymind-core/deploymind/presentation/cli/
└── main.py              — Wire 6 commands to use cases (Phase 7)
```

---

## What This Achieves on the Resume

After all phases:

```
• End-to-end GitOps pipeline: GitHub push → HMAC-verified webhook → deployment queue
  (Redis, serialized per-environment) → Security scan → AI-generated Dockerfile →
  Docker build → rolling/canary/blue-green deploy to EC2 or Kubernetes (EKS/GKE)

• Three deployment strategies: Rolling (zero-downtime), Canary (10%→50%→100% traffic
  shifting with auto-rollback on error rate threshold), Blue-Green (instant switch +
  2-minute observation window)

• Kubernetes-native deployments: auto-generated Deployments with readiness/liveness
  probes, HPA, PDB, topology spread constraints, and securityContext (runAsNonRoot)

• Distributed systems primitives: Redis-based deployment queue (BRPOPLPUSH reliability
  pattern) with per-instance distributed locking (Lua script atomic check-and-delete)

• Multi-agent orchestration (CrewAI): Security, Build, Deploy agents gate the pipeline
  sequentially; each agent can halt or modify the workflow based on LLM reasoning

• 200+ tests across unit, integration, and e2e; Clean Architecture with strict
  dependency inversion (Domain has zero external dependencies)
```
