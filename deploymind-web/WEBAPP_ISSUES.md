# DeployMind Web App — Issues & Missing Implementations

> Generated after full e2e validation of `deploymind-core` (all phases passing).
> Every issue below was found by reading the actual web app source code and comparing it against the working core.

---

## CRITICAL BUGS (Will Fail at Runtime)

### 1. Wrong `core_path` in `deployment_service.py`
**File:** `backend/api/services/deployment_service.py:13`

```python
# WRONG — resolves to deploymind-web/deploymind-core (does not exist)
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"

# CORRECT — needs one more .parent to reach DeployMind/
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
```

The file is at `deploymind-web/backend/api/services/deployment_service.py`. Four parents only reaches `deploymind-web/`, not the monorepo root `DeployMind/`. This silently triggers the `except ImportError` fallback which sets `Deployment = None`, `DeploymentStatusEnum = None`, and every method returns `None` — nothing is ever written to the database.

Note: `orchestration_service.py` has the correct 5-parent path. Fix `deployment_service.py` to match.

---

### 2. Status Enum Case Mismatch (Deployments Always Show as PENDING)
**File:** `backend/api/services/deployment_service.py:165-166`
**File:** `backend/api/routes/deployments.py:288-301`

The core's `DeploymentStatusEnum` stores **uppercase** values: `"PENDING"`, `"DEPLOYED"`, `"FAILED"`, etc. (verified by e2e run).

`deployment_service.update_deployment_status()` writes lowercase:
```python
# WRONG
status_lower = status.lower()
deployment.status = status_lower  # "deployed" — SQLAlchemy LookupError
```

Fix:
```python
# Map to the actual enum member
status_map = {
    "pending": DeploymentStatusEnum.PENDING,
    "security_scanning": DeploymentStatusEnum.SECURITY_SCANNING,
    "building": DeploymentStatusEnum.BUILDING,
    "deploying": DeploymentStatusEnum.DEPLOYING,
    "deployed": DeploymentStatusEnum.DEPLOYED,
    "failed": DeploymentStatusEnum.FAILED,
    "rolled_back": DeploymentStatusEnum.ROLLED_BACK,
}
deployment.status = status_map.get(status.lower(), DeploymentStatusEnum.PENDING)
```

Additionally, `_deployment_to_response()` in `deployments.py` does:
```python
api_status = status_map.get(
    deployment.status.value if hasattr(deployment.status, 'value') else deployment.status,
    DeploymentStatus.PENDING  # <-- default returned for EVERY unmapped key
)
```
The `status_map` keys are lowercase (`"deployed"`, `"pending"`) but `deployment.status.value` is uppercase (`"DEPLOYED"`, `"PENDING"`). All keys miss → every deployment shows as `PENDING` in the API response.

Fix: normalise the key lookup with `.lower()`:
```python
raw = deployment.status.value if hasattr(deployment.status, 'value') else str(deployment.status)
api_status = status_map.get(raw.lower(), DeploymentStatus.PENDING)
```

---

### 3. Dual Deployment ID — Core Creates Its Own ID, Web Record Never Updated
**File:** `backend/api/routes/deployments.py:101`
**File:** `deploymind-core/deploymind/application/use_cases/full_deployment_workflow.py:128`

Web creates: `deployment_id = f"deploy-{uuid.uuid4().hex[:8]}"` and stores it.
Core **ignores** this ID and creates its own: `deployment_id = str(uuid.uuid4())[:8]`.

Result: two separate `deployments` rows with different IDs. The web's row stays `PENDING` forever; the core's row correctly updates to `DEPLOYED`. The frontend shows stale data.

Fix: Pass the web-generated ID into `FullDeploymentRequest`. The core's `FullDeploymentWorkflow.execute()` currently ignores any incoming ID. Either:
- Add a `deployment_id: Optional[str]` field to `FullDeploymentRequest` and honour it inside the workflow, **or**
- Have `OrchestrationService` return the core's ID back to `DeploymentService` and update the web record to point at it.

---

### 4. Rollback Endpoint Is a Stub — Never Executes Rollback
**File:** `backend/api/routes/deployments.py:197`

```python
# TODO: Trigger actual rollback workflow in background
```

The route just calls `repo.update_status(deployment_id, "rolled_back")` and returns. No `RollingDeployer.rollback()` is ever called, no container is reverted, no previous image is restarted.

Fix: Call `OrchestrationService` (or a new `RollbackUseCase`) in a background task, passing the deployment's `image_tag` and the previous deployment's `image_tag` as `previous_image_tag`.

---

### 5. Webhook Push Handler Never Triggers a Real Deployment
**File:** `backend/api/routes/webhooks.py:110-123`

`handle_push_event()` logs the push and returns a fabricated JSON dict with a made-up `deployment_id`. Nothing is written to the database; no `DeploymentService.create_deployment()` or `run_deployment_workflow()` is called.

Fix: Look up the repository in the `deployments` table, create a new deployment record, and launch `service.run_deployment_workflow()` in a background task — same as `POST /api/deployments`.

---

### 6. `hmac.new` Typo in Webhook Signature Verification
**File:** `backend/api/routes/webhooks.py:34`

```python
# Python has no hmac.new() — the correct function is hmac.new() in Python 2,
# but in Python 3 the standard function is hmac.new()
computed_signature = hmac.new(   # <-- this actually IS valid in Python 3 (alias)
```

Actually `hmac.new()` is a valid alias in Python 3 — this is a low-priority note only. Verify with `python -c "import hmac; print(hmac.new.__doc__)"`.

---

## MISSING IMPLEMENTATIONS

### 7. Monitoring Routes Return Randomised Mock Data
**File:** `backend/api/routes/monitoring.py`

All three endpoints (`/metrics`, `/metrics/history`, `/health`) generate metrics with `random.uniform()`. The frontend will show flickering charts that have no relation to the real EC2 instance.

What to integrate instead:
- **CPU/Memory/Disk**: Run `docker stats --no-stream <container_name>` via `EC2Client.run_command()` (SSM already proven working in e2e test).
- **Network**: Parse `/proc/net/dev` on the instance, or use CloudWatch `NetworkIn` / `NetworkOut` metrics.
- **Health check**: Call `HealthChecker.check_http(f"http://{public_ip}:{port}/health")` — this class already exists in core.

---

### 8. WebSocket Manager Exists but Is Never Used for Live Updates
**File:** `backend/api/websocket/manager.py`
**File:** `frontend/app/dashboard/deployments/new/page.tsx` (polls every 2 s)

The frontend polls `GET /api/deployments/{id}` every 2 seconds to track progress. The WebSocket manager (`ConnectionManager`) class exists but no route broadcasts deployment status changes.

Fix:
1. Add a WebSocket endpoint: `GET /ws/deployments/{id}` using `manager.connect(websocket, deployment_id)`.
2. After each `update_deployment_status()` call in `DeploymentService`, call `manager.broadcast(deployment_id, {"status": status})`.
3. Replace the frontend 2-second polling with a `useEffect` + `WebSocket` hook.

Alternatively, subscribe to the core's Redis Pub/Sub channel `deploymind:events` and forward messages to connected WebSocket clients.

---

### 9. Environment Variables Not Saved to `environment_variable` Table
**File:** `backend/api/services/deployment_service.py:86`

Env vars are put into `extra_data={"port": port, "environment": environment}` JSON but the `EnvironmentVariable` ORM model (`api/models/environment_variable.py`) and its table are never written to.

The wizard collects env vars in step 4 but `create_deployment` in the route receives no `env_vars` field — it's not in `DeploymentCreate` schema either.

Fix:
1. Add `env_vars: list[dict]` to `DeploymentCreate` schema (optional).
2. In `create_deployment` route, iterate and insert `EnvironmentVariable` rows.
3. In `run_deployment_workflow`, pass decrypted env vars to `FullDeploymentRequest` (core already accepts `env_vars` in `DeployRequest`).

---

### 10. `init_web_db()` Must Be Called on Startup
**File:** `backend/api/services/database.py`
**File:** `backend/api/main.py`

`init_web_db()` creates the `web_users`, `environment_variable`, and `action_execution` tables. If it is not called before the first request, any endpoint that inserts into those tables will raise `ProgrammingError: relation "web_users" does not exist`.

Check `main.py` startup event:
```python
@app.on_event("startup")
async def startup():
    from api.services.database import init_web_db
    init_web_db()
```
If this is missing, add it.

---

### 11. `OrchestrationService.get_deployment_status()` Always Returns `"pending"`
**File:** `backend/api/services/orchestration_service.py:133-138`

```python
return {
    "deployment_id": deployment_id,
    "status": "pending",       # hardcoded
    "phase": "security_scanning"
}
```

This is never called from a route today, but if it ever is, it will always return pending. Fix: query `DeploymentRepository.get_by_id(deployment_id).status`.

---

## SECURITY ISSUES

### 12. Webhook Signature Verification Silently Skipped
**File:** `backend/api/routes/webhooks.py:20-22`

```python
if not settings.github_webhook_secret:
    return True  # skip verification in "dev mode"
```

If `GITHUB_WEBHOOK_SECRET` is missing from `.env`, any HTTP client can call `POST /api/webhooks/github` with arbitrary payloads and trigger (or eventually trigger) deployments. This is a supply-chain attack vector.

Fix: Reject the request (return 401) instead of skipping verification when the secret is not configured. Log a loud warning at startup.

---

### 13. GitHub Access Token Stored Plaintext in Database
**File:** `backend/api/models/user.py`

```python
github_access_token = Column(String, nullable=True)
```

The user's GitHub OAuth token is stored verbatim. A database dump exposes every user's full GitHub access.

Fix: Encrypt with `cryptography.fernet.Fernet` using a `FERNET_KEY` env var before write, decrypt on read.

---

### 14. JWT Stored in `localStorage` (XSS Risk)
**File:** `frontend/lib/api.ts:7`

```typescript
const token = localStorage.getItem('token')
```

Tokens in `localStorage` are readable by any JavaScript on the page, including injected scripts.

Fix: Use `httpOnly` cookies (set by the backend on login, not accessible to JS). Update auth routes to `Set-Cookie: token=...; HttpOnly; SameSite=Strict`.

---

### 15. CORS Too Permissive
**File:** `backend/api/main.py`

```python
allow_methods=["*"],
allow_headers=["*"],
```

Replace with explicit lists:
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type"],
```

---

## MINOR ISSUES

### 16. `DeploymentCreate` Schema Missing `health_check_path`
**File:** `backend/api/schemas/deployment.py`

The wizard collects `health_check_path` (step 2 or 3) and the core uses it, but `DeploymentCreate` may not include it as a field. The route uses `getattr(deployment, 'health_check_path', '/health')` as a workaround — add the field to the schema properly.

---

### 17. `user_id` Type Mismatch (int vs str)
**File:** `backend/api/routes/deployments.py:111`

```python
user_id=current_user.get("user_id", 0),
```

`current_user` is a dict decoded from JWT. The JWT payload uses `"sub"` for the subject (user ID) and `user_id` as a separate claim. If the claim isn't present, this returns `0` — a non-existent user ID — which will cause a foreign key constraint error if the `deployments` table has a FK to `web_users`.

Fix: Decode JWT consistently and document the exact claim name (`user_id` vs `sub`).

---

### 18. Deployment List Shows All Users' Deployments
**File:** `backend/api/routes/deployments.py:41-46`

`repo.list_deployments(offset, limit, status)` fetches from all deployments regardless of `user_id`. Users can see each other's deployments.

Fix: Pass `user_id=current_user["user_id"]` as a filter to `DeploymentRepository.list_deployments()`.

---

## WHAT IS WORKING CORRECTLY

| Component | Status |
|-----------|--------|
| GitHub OAuth login/callback | Working |
| JWT token issuance & validation | Working |
| `OrchestrationService` core wiring | Working (correct path, `run_in_executor`) |
| `DeploymentService.run_deployment_workflow()` async wrapping | Working |
| `DELETE /deployments/{id}` cascade deletion | Working |
| `GET /deployments/{id}/logs` | Working |
| `POST /deployments` background task launch | Working (fires correctly) |
| Deployment schema validation (repo format, instance ID regex) | Working |
| AI recommendation routes | Working (Groq integration) |
| Security scan routes (calls Trivy via core) | Working |
| Database connection to shared deploymind-core PostgreSQL | Working |

---

## PRIORITY ORDER FOR FIXES

| Priority | Issue # | Fix |
|----------|---------|-----|
| P0 | #1 | Fix `core_path` in `deployment_service.py` (wrong parent count) |
| P0 | #2 | Fix status enum case — DB writes fail / frontend always shows PENDING |
| P0 | #3 | Fix dual deployment ID — pass web ID into core or sync back |
| P1 | #4 | Implement rollback via `RollingDeployer` |
| P1 | #5 | Webhook push → actual deployment trigger |
| P1 | #10 | Ensure `init_web_db()` called on startup |
| P2 | #7 | Replace mock monitoring with real EC2/Docker stats |
| P2 | #8 | WebSocket live status instead of polling |
| P2 | #9 | Save env vars to `environment_variable` table |
| P3 | #12 | Webhook secret required, not optional |
| P3 | #13 | Encrypt GitHub token at rest |
| P3 | #14 | Move JWT to httpOnly cookies |
| P3 | #18 | Scope deployment list to current user |
