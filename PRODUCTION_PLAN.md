# DeployMind — Production-Ready Roadmap

> **Audit date:** 2026-03-02
> **Core status:** ✅ 1225 tests passing, E2E verified on AWS EC2
> **Web status:** 🟡 UI complete, API routes exist, but 3 critical bugs break all deployments

---

## Current State Snapshot

### What Works
| Component | Status |
|-----------|--------|
| Core pipeline (security → build → deploy) | ✅ E2E verified |
| Frontend UI (all pages, animations, OAuth) | ✅ Complete |
| GitHub OAuth login | ✅ Working |
| Repository browser in wizard | ✅ Working |
| Analytics endpoint | ✅ Working |
| CLI commands | ✅ Working |

### What's Broken (Critical)
| Bug | Location | Impact |
|-----|----------|--------|
| Wrong `core_path` (4 parents, needs 5) | `deployment_service.py:13` | Silent: `DeploymentStatusEnum = None`, nothing writes to DB |
| Status enum case mismatch (`"deployed"` vs `"DEPLOYED"`) | `deployment_service.py:165` + `deployments.py:288` | All deployments stuck at PENDING |
| Dual deployment IDs (web generates one, core generates another) | `deployments.py:101` + `full_deployment_workflow.py` | Split-brain: two DB rows, web never sees core's updates |

### What's Stubbed (Non-Functional)
- Rollback endpoint updates status only, never calls `RollingDeployer.rollback()`
- Webhook handler logs event, returns fake JSON, never triggers deployment
- All monitoring metrics are `random.uniform()` (no real EC2 stats)
- All AI predictions (health, anomaly, scaling, cost, risk) return mock data
- AI action buttons (scale, stop, scan) don't execute anything
- Environment variables collected by wizard but never saved

---

## Phase 8 — Fix Critical Bugs (Estimated: 1 day)

> **Goal:** Deployments work end-to-end, status updates correctly in UI.

### 8.1 Fix `core_path` in `deployment_service.py`

**File:** `deploymind-web/backend/api/services/deployment_service.py:13`

```python
# WRONG (current) — resolves to deploymind-web/deploymind-core (doesn't exist)
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"

# FIX — match orchestration_service.py which correctly uses 5 parents
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
```

**Verify:** After fix, add a startup log:
```python
logger.info(f"core_path resolved to: {core_path}, exists: {core_path.exists()}")
```

### 8.2 Fix Status Enum Case Mismatch

**File:** `deploymind-web/backend/api/services/deployment_service.py`

The core stores uppercase enum values (`"PENDING"`, `"DEPLOYED"`, `"FAILED"`).
The web's `update_status()` must pass the raw string and let SQLAlchemy cast it:

```python
# WRONG
deployment.status = status.lower()           # "deployed" — SQLAlchemy rejects

# FIX — store the canonical enum value string
deployment.status = status.upper()           # "DEPLOYED" — matches enum
```

**File:** `deploymind-web/backend/api/routes/deployments.py` — Fix `_deployment_to_response()`:

```python
# WRONG — lowercase keys never match uppercase enum values
status_map = {
    "deployed": DeploymentStatus.DEPLOYED,
    "pending": DeploymentStatus.PENDING,
    ...
}
api_status = status_map.get(deployment.status.value)  # always misses → PENDING

# FIX — case-insensitive lookup
raw = deployment.status.value if hasattr(deployment.status, "value") else str(deployment.status)
api_status = status_map.get(raw.lower(), DeploymentStatus.PENDING)
```

### 8.3 Fix Dual Deployment ID (Single Source of Truth)

**Problem:** Web generates `deploy-{hex[:8]}` and core generates `str(uuid4())[:8]` independently.

**Fix strategy:** Web is the record creator. Pass its ID into core's workflow and make core use it.

**File:** `deploymind-web/backend/api/routes/deployments.py` — Pass `deployment_id` into request:

```python
# In create_deployment route, after creating the DB record:
workflow_request = FullDeploymentRequest(
    repository=deployment_data.repository,
    instance_id=deployment_data.instance_id,
    port=deployment_data.port,
    strategy=deployment_data.strategy,
    health_check_path=deployment_data.health_check_path,
    environment=deployment_data.environment,
    deployment_id=deployment_id,  # ← ADD THIS: force core to use web's ID
)
```

**File:** `deploymind-core/deploymind/application/use_cases/full_deployment_workflow.py` — Already accepts `deployment_id` in `FullDeploymentRequest`. Verify line ~129 uses it:
```python
deployment_id = request.deployment_id or str(uuid.uuid4())[:8]  # ← already correct!
```

So the fix is purely on the web side: pass the ID in the request.

### 8.4 Fix Web DB Init — Ensure Tables Exist Before First Request

**File:** `deploymind-web/backend/api/main.py`

Wrap `init_web_db()` in a proper startup event and add explicit error on failure:

```python
@app.on_event("startup")
async def startup():
    try:
        from .services.database import init_web_db
        init_web_db()
        logger.info("Web database tables initialized")
    except Exception as e:
        logger.error(f"FATAL: Could not initialize web database: {e}", exc_info=True)
        raise  # Fail fast — don't silently swallow DB init errors
```

**Verification:** After fix, `POST /api/deployments` + poll `GET /api/deployments/{id}` for 5 minutes should show status transitions: `PENDING → SECURITY_SCANNING → BUILDING → DEPLOYING → DEPLOYED`.

---

## Phase 9 — Real Rollback & Webhook Auto-Deploy (Estimated: 1 day)

> **Goal:** Rollback button actually rolls back. GitHub pushes auto-trigger deployments.

### 9.1 Implement Real Rollback

**File:** `deploymind-web/backend/api/routes/deployments.py`

Replace the stub with a real background task:

```python
import asyncio
from ..services.orchestration_service import OrchestrationService

@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = DeploymentRepository(db)
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        raise HTTPException(404, "Deployment not found")

    if not deployment.previous_image_tag:
        raise HTTPException(400, "No previous version to rollback to")

    # Mark as rolling back immediately
    repo.update_status(deployment_id, "ROLLING_BACK")

    # Run rollback in background
    background_tasks.add_task(
        OrchestrationService.run_rollback,
        deployment_id=deployment_id,
        instance_id=deployment.instance_id,
        previous_image_tag=deployment.previous_image_tag,
        port=deployment.port,
    )
    return {"message": "Rollback initiated", "deployment_id": deployment_id}
```

**File:** `deploymind-web/backend/api/services/orchestration_service.py`

Add `run_rollback()` method that calls core's `DeployApplicationUseCase` with rollback request.

### 9.2 Implement GitHub Webhook Auto-Deploy

**File:** `deploymind-web/backend/api/routes/webhooks.py`

Replace the stub with real deployment trigger:

```python
@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Verify HMAC signature
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(payload, signature):
        raise HTTPException(401, "Invalid signature")

    # 2. Parse event
    event_type = request.headers.get("X-GitHub-Event")
    if event_type != "push":
        return {"message": f"Ignoring {event_type} event"}

    data = await request.json()
    repo_full_name = data["repository"]["full_name"]
    ref = data["ref"]  # "refs/heads/main"
    branch = ref.split("/")[-1]

    # 3. Find auto-deploy configs for this repo+branch
    repo_orm = DeploymentRepository(db)
    active_deployments = repo_orm.find_by_repository(repo_full_name)

    for deployment in active_deployments:
        if deployment.auto_deploy_branch == branch:
            background_tasks.add_task(
                OrchestrationService.run_deployment_workflow,
                deployment_id=f"deploy-{uuid.uuid4().hex[:8]}",
                repository=repo_full_name,
                instance_id=deployment.instance_id,
                port=deployment.port,
                strategy=deployment.strategy,
            )

    return {"message": f"Triggered {len(active_deployments)} deployments"}
```

**Database change:** Add `auto_deploy_branch` column to `deployments` table (nullable string, default `None` = no auto-deploy).

---

## Phase 10 — Real-Time Metrics & WebSocket (Estimated: 2 days)

> **Goal:** Replace mock data with real EC2 metrics; switch from polling to WebSocket push.

### 10.1 Real EC2 Metrics via SSM

**File:** `deploymind-web/backend/api/routes/monitoring.py`

Replace `random.uniform()` with real SSH/SSM commands via the core's `EC2Client`:

```python
# For CPU/Memory/Disk — use `docker stats --no-stream`
# This is already tested in the core's e2e tests

def _get_real_metrics(instance_id: str, settings: Settings) -> dict:
    ec2 = EC2Client(settings)

    # Docker container stats
    result = ec2.run_command(
        instance_id,
        "docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemPerc}} {{.MemUsage}}' 2>/dev/null | head -5"
    )
    # Parse stdout → extract CPU%, Memory%

    # Disk usage
    disk_result = ec2.run_command(instance_id, "df -h / | tail -1 | awk '{print $5}'")

    # Network I/O (bytes from /proc/net/dev)
    net_result = ec2.run_command(
        instance_id,
        "cat /proc/net/dev | grep eth0 | awk '{print $2, $10}'"
    )

    return {
        "cpu_percent": parse_cpu(result["stdout"]),
        "memory_percent": parse_memory(result["stdout"]),
        "disk_percent": parse_disk(disk_result["stdout"]),
        "network_in_bytes": parse_network_in(net_result["stdout"]),
        "network_out_bytes": parse_network_out(net_result["stdout"]),
    }
```

**Caching:** Cache metrics in Redis with 15s TTL to avoid hammering SSM API:
```python
from deploymind.shared.cache import cached

@cached(ttl_seconds=15, prefix="metrics")
def get_instance_metrics(instance_id: str) -> dict: ...
```

### 10.2 WebSocket Live Deployment Updates

**File:** `deploymind-web/backend/api/routes/websocket.py` (new endpoint)

```python
@router.websocket("/ws/deployments/{deployment_id}")
async def deployment_websocket(
    websocket: WebSocket,
    deployment_id: str,
    token: str = Query(...),
):
    # Validate JWT token
    user = await validate_ws_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, deployment_id)

    try:
        # Subscribe to Redis Pub/Sub channel: "deploymind:events"
        redis = get_redis_client()
        pubsub = redis.pubsub()
        pubsub.subscribe(f"deploymind:deployment:{deployment_id}")

        for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        manager.disconnect(websocket, deployment_id)
```

**File:** `deploymind-web/frontend/lib/useDeploymentWebSocket.ts` (new hook)

```typescript
function useDeploymentWebSocket(deploymentId: string) {
  const [status, setStatus] = useState<DeploymentStatus>("PENDING");
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    const token = getAccessToken();
    const ws = new WebSocket(
      `${WS_URL}/ws/deployments/${deploymentId}?token=${token}`
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "status_update") setStatus(data.status);
      if (data.type === "log") setLogs(prev => [...prev, data.message]);
    };

    return () => ws.close();
  }, [deploymentId]);

  return { status, logs };
}
```

**Replace polling** in `deploy-step.tsx` and `deployments/[id]/page.tsx` with this hook.

---

## Phase 11 — Environment Variables & Settings (Estimated: 1 day)

> **Goal:** Env vars configured in wizard are actually passed to deployments.

### 11.1 Persist Env Vars to Database

**File:** `deploymind-web/backend/api/schemas/deployment.py`

Add `env_vars` to `DeploymentCreate`:
```python
class EnvVar(BaseModel):
    key: str
    value: str
    is_secret: bool = False

class DeploymentCreate(BaseModel):
    repository: str
    instance_id: str
    port: int = 8080
    strategy: str = "rolling"
    health_check_path: str = "/health"
    environment: str = "production"
    env_vars: list[EnvVar] = []        # ← ADD
    auto_deploy_branch: str | None = None  # ← ADD for webhooks
```

**File:** `deploymind-web/backend/api/routes/deployments.py`

After creating deployment record:
```python
# Save env vars
for env_var in deployment_data.env_vars:
    db.add(EnvironmentVariable(
        deployment_id=deployment_id,
        key=env_var.key,
        value=env_var.value,  # Encrypt secrets before storage
        is_secret=env_var.is_secret,
    ))
db.commit()
```

### 11.2 Pass Env Vars to Core's `FullDeploymentRequest`

**File:** `deploymind-core/deploymind/application/use_cases/full_deployment_workflow.py`

Add `env_vars: dict[str, str] = {}` to `FullDeploymentRequest`. Pass to `DeployRequest` which injects them via `docker run -e KEY=VALUE`.

### 11.3 Encrypt Secrets at Rest

**File:** `deploymind-web/backend/api/models/environment_variable.py`

Use `cryptography.fernet` with a key from `JWT_SECRET`:

```python
from cryptography.fernet import Fernet

def encrypt_value(value: str, key: str) -> str:
    f = Fernet(derive_fernet_key(key))
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted: str, key: str) -> str:
    f = Fernet(derive_fernet_key(key))
    return f.decrypt(encrypted.encode()).decode()
```

---

## Phase 12 — Real AI Features (Estimated: 3 days)

> **Goal:** Replace mock predictions with real AI powered by Groq LLM + actual metrics.

### 12.1 Health Predictor (Real Implementation)

Replace stub with LLM call + real metric history:

```python
class HealthPredictor:
    def __init__(self, groq_client: GroqClient):
        self.client = groq_client

    def predict(self, deployment_id: str, metric_history: list[dict]) -> HealthPrediction:
        # Build context from real metric history
        context = f"""
        Deployment: {deployment_id}
        Last 24h metrics (sampled every 15min):
        {json.dumps(metric_history[-96:], indent=2)}

        Analyze trends and predict health issues in next 2 hours.
        Return JSON: {{"risk_level": "low|medium|high", "issues": [], "recommendations": []}}
        """

        response = self.client.complete(context)
        return HealthPrediction.parse_raw(response)
```

### 12.2 Cost Analyzer (Real Implementation)

Use AWS Cost Explorer API (or estimate from EC2 instance type × uptime):

```python
class CostAnalyzer:
    def analyze(self, instance_type: str, uptime_hours: float) -> CostReport:
        # EC2 on-demand pricing (us-east-1)
        HOURLY_RATES = {
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            # ...
        }
        hourly_rate = HOURLY_RATES.get(instance_type, 0.05)
        total_cost = hourly_rate * uptime_hours

        # Ask Groq for optimization suggestions
        prompt = f"EC2 {instance_type} running {uptime_hours:.1f}h costs ${total_cost:.2f}. Suggest optimizations."
        suggestions = self.groq_client.complete(prompt)

        return CostReport(total_usd=total_cost, suggestions=suggestions)
```

### 12.3 Action Executor (Real Implementation)

**File:** `deploymind-web/backend/api/services/action_executor.py`

```python
class ActionExecutor:
    async def scale_instance(self, instance_id: str, new_type: str) -> ActionResult:
        # Use boto3 to stop → modify instance type → start
        ec2_boto = boto3.client("ec2", region_name=settings.aws_region)
        ec2_boto.stop_instances(InstanceIds=[instance_id])
        waiter = ec2_boto.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id])
        ec2_boto.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={"Value": new_type}
        )
        ec2_boto.start_instances(InstanceIds=[instance_id])
        return ActionResult(success=True, message=f"Scaled to {new_type}")

    async def trigger_security_scan(self, deployment_id: str) -> ActionResult:
        # Call core's ScanSecurityUseCase directly
        from deploymind.application.use_cases.scan_security import SecurityScanUseCase, SecurityScanRequest
        uc = SecurityScanUseCase(settings)
        result = uc.execute(SecurityScanRequest(
            deployment_id=deployment_id,
            target="/",
            scan_type="filesystem"
        ))
        return ActionResult(success=result.success, message=result.message)
```

### 12.4 Anomaly Detector (Metrics-Based)

Use statistical methods (Z-score on rolling window) instead of random:

```python
class AnomalyDetector:
    def detect(self, metric_history: list[float]) -> list[Anomaly]:
        import statistics
        if len(metric_history) < 10:
            return []

        mean = statistics.mean(metric_history)
        stdev = statistics.stdev(metric_history)

        anomalies = []
        for i, value in enumerate(metric_history):
            z_score = abs(value - mean) / stdev if stdev > 0 else 0
            if z_score > 2.5:
                anomalies.append(Anomaly(
                    timestamp=i,
                    value=value,
                    z_score=z_score,
                    severity="high" if z_score > 3.5 else "medium"
                ))
        return anomalies
```

---

## Phase 13 — Security Hardening (Estimated: 1 day)

> **Goal:** Ensure the app is safe for public deployment.

### 13.1 Fix HMAC Webhook Verification

**File:** `deploymind-web/backend/api/routes/webhooks.py`

Current code uses `hmac.new()` (valid but unusual). Standardize on `hmac.new()` → `hmac.new()`:

```python
import hmac
import hashlib

def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)  # constant-time comparison
```

### 13.2 Rate Limiting

Add rate limiting middleware to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/github")
@limiter.limit("100/minute")
async def github_webhook(...): ...

@router.post("/{deployment_id}/rollback")
@limiter.limit("5/minute")
async def rollback_deployment(...): ...
```

### 13.3 Secret Encryption in Transit

- All env vars marked `is_secret=True` must be encrypted at rest (Phase 11.3)
- Add `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` headers
- Enforce `HTTPS_ONLY=true` in production settings

### 13.4 JWT Token Refresh

Current JWT tokens never refresh. Add a refresh endpoint:

```python
@router.post("/auth/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):
    new_token = create_access_token({"sub": current_user.username})
    return {"access_token": new_token, "token_type": "bearer"}
```

---

## Phase 14 — Docker & Production Deployment (Estimated: 1 day)

> **Goal:** One-command production startup.

### 14.1 Docker Compose (Production)

Create `docker-compose.prod.yml`:

```yaml
version: "3.9"
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: deploymind
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  backend:
    build:
      context: deploymind-web/backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@db:5432/deploymind
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379
      GITHUB_CLIENT_ID: ${GITHUB_CLIENT_ID}
      GITHUB_CLIENT_SECRET: ${GITHUB_CLIENT_SECRET}
      JWT_SECRET: ${JWT_SECRET}
      GROQ_API_KEY: ${GROQ_API_KEY}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_REGION: ${AWS_REGION}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    ports:
      - "8000:8000"

  frontend:
    build:
      context: deploymind-web/frontend
      dockerfile: Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-https://api.yourdomain.com}
    ports:
      - "3000:3000"

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
```

### 14.2 Backend Dockerfile

**File:** `deploymind-web/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy core package
COPY ../../deploymind-core/deploymind ./deploymind_core/deploymind
COPY ../../deploymind-core/setup.py ./deploymind_core/
RUN pip install -e ./deploymind_core

# Copy backend
COPY . .

FROM python:3.11-slim
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /app .

RUN useradd -m appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 14.3 Frontend Dockerfile

**File:** `deploymind-web/frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json .
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json .

EXPOSE 3000
CMD ["npm", "start"]
```

### 14.4 Nginx Config

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

---

## Phase 15 — Integration Tests & E2E (Estimated: 2 days)

> **Goal:** Full confidence the web ↔ core integration works end-to-end.

### 15.1 Web Backend Integration Tests

**File:** `deploymind-web/backend/tests/test_deployment_workflow.py`

```python
@pytest.mark.integration
class TestDeploymentWorkflowIntegration:
    """Test web → core deployment pipeline."""

    def test_create_deployment_creates_single_db_record(self, client, auth_headers):
        """Verify no dual-ID split-brain."""
        response = client.post("/api/deployments", json={
            "repository": "testuser/testapp",
            "instance_id": "i-1234567890abcdef0",
            "port": 8080,
        }, headers=auth_headers)
        assert response.status_code == 201
        deployment_id = response.json()["id"]

        # Core should use same ID
        from deploymind.config.dependencies import container
        core_record = container.deployment_repo.get_by_id(deployment_id)
        assert core_record is not None
        assert core_record.id == deployment_id

    def test_status_updates_visible_in_api(self, client, auth_headers, deployment_id):
        """Verify status transitions visible through API."""
        # Poll for up to 30s (unit test with mocked core)
        for _ in range(30):
            resp = client.get(f"/api/deployments/{deployment_id}", headers=auth_headers)
            status = resp.json()["status"]
            if status != "PENDING":
                break
            time.sleep(1)

        assert status in ["DEPLOYED", "FAILED", "SECURITY_FAILED"]

    def test_rollback_changes_status(self, client, auth_headers, deployed_deployment):
        response = client.post(
            f"/api/deployments/{deployed_deployment}/rollback",
            headers=auth_headers
        )
        assert response.status_code == 200
        # Wait for status change
        time.sleep(2)
        status_resp = client.get(f"/api/deployments/{deployed_deployment}", headers=auth_headers)
        assert status_resp.json()["status"] in ["ROLLING_BACK", "DEPLOYED"]
```

### 15.2 WebSocket Test

```python
@pytest.mark.asyncio
async def test_websocket_receives_status_updates(deployment_id, token):
    async with websockets.connect(f"ws://localhost:8000/ws/deployments/{deployment_id}?token={token}") as ws:
        message = await asyncio.wait_for(ws.recv(), timeout=30)
        data = json.loads(message)
        assert "type" in data
        assert data["type"] in ["status_update", "log", "heartbeat"]
```

### 15.3 Frontend E2E (Playwright)

```typescript
test("deployment wizard creates deployment and shows progress", async ({ page }) => {
    await page.goto("/dashboard/deployments/new");

    // Step 1: Select repository
    await page.getByText("testuser/testapp").click();
    await page.getByRole("button", { name: "Next" }).click();

    // Step 2: Select instance
    await page.getByText("i-1234567890abcdef0").click();
    await page.getByRole("button", { name: "Next" }).click();

    // ... steps 3-4 ...

    // Step 5: Review + Deploy
    await page.getByRole("button", { name: "Deploy Now" }).click();

    // Step 6: Should show progress
    await expect(page.getByText("Security Scanning")).toBeVisible();
    await expect(page.getByText("Building")).toBeVisible({ timeout: 60000 });
});
```

---

## Phase 16 — Monitoring Dashboard & Observability (Estimated: 2 days)

> **Goal:** Operators can see system health at a glance.

### 16.1 Add Prometheus Metrics Endpoint

**File:** `deploymind-web/backend/api/main.py`

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

Exposes `/metrics` with:
- `http_requests_total` — requests by endpoint, status code
- `http_request_duration_seconds` — latency percentiles
- `deployments_total` — by status (success, failed)
- `active_deployments` — gauge

### 16.2 Grafana Dashboard

Add `grafana/` directory with a pre-built dashboard JSON for:
- Deployment success rate (last 24h)
- P50/P95/P99 API latency
- Active deployments by status
- EC2 metrics (CPU, memory, disk) per deployment

### 16.3 Structured Logging

Standardize all web backend logs to match core's structured format:

```python
import structlog

logger = structlog.get_logger()
logger.info("deployment.created",
    deployment_id=deployment_id,
    repository=repository,
    user=current_user.username
)
```

---

## Summary: Effort & Priority Matrix

| Phase | What | Days | Priority | Blocks |
|-------|------|------|----------|--------|
| **Phase 8** | Fix 3 critical bugs (path, enum, dual-ID) + DB init | 1 | 🔴 P0 | Everything |
| **Phase 9** | Real rollback + webhook auto-deploy | 1 | 🔴 P1 | User-facing features |
| **Phase 10** | Real EC2 metrics + WebSocket live updates | 2 | 🟠 P2 | Production usability |
| **Phase 11** | Env vars persist + pass to core | 1 | 🟠 P2 | Feature completeness |
| **Phase 12** | Real AI predictions + action execution | 3 | 🟡 P3 | AI features |
| **Phase 13** | Security hardening (rate limit, HMAC, JWT refresh) | 1 | 🟠 P2 | Production security |
| **Phase 14** | Docker + Nginx + production compose | 1 | 🟠 P2 | Production deployment |
| **Phase 15** | Integration tests + Playwright E2E | 2 | 🟡 P3 | Confidence / quality |
| **Phase 16** | Prometheus + Grafana + structured logs | 2 | 🟡 P3 | Observability |
| **Total** | | **~14 days** | | |

### Minimum Viable Production (Phases 8–11 + 13–14)
Completing only these phases yields a production-ready app where:
- ✅ Deployments actually work end-to-end
- ✅ Status updates visible in real-time
- ✅ Rollback works
- ✅ GitHub webhooks trigger auto-deploys
- ✅ Environment variables saved and used
- ✅ App securely containerized and behind Nginx
- **Estimated: 7 days**

### Full Production (All Phases)
- ✅ Everything above
- ✅ Real AI insights from Groq LLM
- ✅ Prometheus metrics + Grafana dashboards
- ✅ Full integration test coverage
- **Estimated: 14 days**

---

## Pre-Flight Checklist (Before Any Phase)

- [ ] Confirm `PHASE.md` Phase 1–7 are all marked ✅ (core is production-ready)
- [ ] Confirm `deploymind-core` tests: `1225 passed, 0 failed, 0 errors`
- [ ] `docker-compose up -d` successfully starts PostgreSQL + Redis
- [ ] `.env` files exist for both backend and frontend
- [ ] `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` configured in GitHub OAuth app
- [ ] AWS credentials valid: `aws sts get-caller-identity` succeeds
- [ ] Groq API key valid: `groq models list` returns models

---

*Plan generated: 2026-03-02. Supersedes old PHASE.md for Phases 8+.*
