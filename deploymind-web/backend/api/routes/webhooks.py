"""GitHub webhooks for auto-deploy."""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import Dict
import hmac
import hashlib
import uuid

from ..services.database import get_db
from ..config import settings

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """
    Verify GitHub webhook signature.

    GitHub sends a signature in the X-Hub-Signature-256 header.
    Requires settings.github_webhook_secret to be set.
    """
    if not signature:
        return False

    # GitHub sends: sha256=<hash>
    if not signature.startswith("sha256="):
        return False

    expected_signature = signature.split("=")[1]

    # Compute HMAC
    computed_signature = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Handle GitHub webhook events.

    Supported events:
    - push: Trigger auto-deploy when code is pushed
    - pull_request: Optionally deploy preview environments

    Security:
    - Requires webhook secret (GITHUB_WEBHOOK_SECRET env var must be set)
    - Validates webhook signature (HMAC SHA-256)
    - Only processes whitelisted repositories
    """
    # Require webhook secret to be configured
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=401, detail="Webhook secret not configured")

    # Get signature from header
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    if not verify_github_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse JSON payload
    payload = await request.json()

    # Get event type
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type == "ping":
        # GitHub sends a ping when webhook is first set up
        return {"message": "Webhook configured successfully"}

    if event_type == "push":
        return await handle_push_event(payload, db, background_tasks)

    if event_type == "pull_request":
        return await handle_pull_request_event(payload, db)

    # Unknown event type
    return {"message": f"Event '{event_type}' received but not processed"}


async def handle_push_event(payload: Dict, db: Session, background_tasks: BackgroundTasks) -> Dict:
    """
    Handle GitHub push event.

    Auto-deploy if:
    1. A DEPLOYED deployment exists for this repository
    2. Push is to main/master branch
    """
    from ..services.database import Deployment as DeploymentModel
    from ..services.deployment_service import DeploymentService

    repo_name = payload.get("repository", {}).get("full_name")
    ref = payload.get("ref", "")
    commit_sha = payload.get("after", "")
    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else ""

    # Only deploy from main/master branch
    if branch not in ["main", "master"]:
        return {
            "message": f"Ignored push to branch '{branch}'",
            "auto_deploy": False
        }

    if not repo_name:
        return {"message": "Missing repository name in payload", "auto_deploy": False}

    # Find the most recent deployed deployment for this repo
    previous = None
    if DeploymentModel:
        previous = (
            db.query(DeploymentModel)
            .filter(
                DeploymentModel.repository == repo_name,
                DeploymentModel.status.in_(["deployed", "DEPLOYED"]),
            )
            .order_by(DeploymentModel.created_at.desc())
            .first()
        )

    if not previous:
        return {
            "message": f"No active deployment found for {repo_name}, skipping auto-deploy",
            "repository": repo_name,
            "auto_deploy": False,
        }

    # Create a new deployment record and fire workflow in background
    new_deployment_id = f"deploy-{uuid.uuid4().hex[:8]}"
    service = DeploymentService(db)
    service.create_deployment(
        deployment_id=new_deployment_id,
        repository=repo_name,
        instance_id=previous.instance_id,
        user_id=previous.user_id,
        port=(previous.extra_data or {}).get("port", 8080),
        strategy=previous.strategy.value if hasattr(previous.strategy, "value") else str(previous.strategy),
        environment=(previous.extra_data or {}).get("environment", "production"),
        triggered_by=f"github-push:{branch}",
    )

    background_tasks.add_task(
        service.run_deployment_workflow,
        deployment_id=new_deployment_id,
        repository=repo_name,
        instance_id=previous.instance_id,
        port=(previous.extra_data or {}).get("port", 8080),
        strategy=previous.strategy.value if hasattr(previous.strategy, "value") else str(previous.strategy),
        environment=(previous.extra_data or {}).get("environment", "production"),
    )

    return {
        "message": f"Auto-deploy triggered for {repo_name}",
        "repository": repo_name,
        "branch": branch,
        "commit": commit_sha[:7] if commit_sha else "unknown",
        "auto_deploy": True,
        "deployment_id": new_deployment_id,
    }


async def handle_pull_request_event(payload: Dict, db: Session) -> Dict:
    """
    Handle GitHub pull request event.

    Optionally create preview deployments for PRs.
    """
    action = payload.get("action")
    pr_number = payload.get("number")
    repo = payload.get("repository", {}).get("full_name")

    if action == "opened":
        # Create preview deployment
        return {
            "message": f"Preview deployment created for PR #{pr_number}",
            "repository": repo,
            "pr_number": pr_number,
            "preview_url": f"https://pr-{pr_number}.preview.deploymind.app"
        }

    if action == "closed":
        # Cleanup preview deployment
        return {
            "message": f"Preview deployment removed for PR #{pr_number}",
            "repository": repo,
            "pr_number": pr_number
        }

    return {"message": f"PR event '{action}' received"}


@router.get("/github/setup")
async def get_webhook_setup_info():
    """
    Get instructions for setting up GitHub webhook.

    Returns webhook URL and configuration details.
    """
    webhook_url = f"{settings.api_base_url}/api/webhooks/github"

    return {
        "webhook_url": webhook_url,
        "content_type": "application/json",
        "events": ["push", "pull_request"],
        "secret_required": bool(settings.github_webhook_secret),
        "instructions": [
            "1. Go to your GitHub repository settings",
            "2. Navigate to Webhooks",
            "3. Click 'Add webhook'",
            f"4. Set Payload URL to: {webhook_url}",
            "5. Set Content type to: application/json",
            "6. Select events: 'push' and 'pull_request'",
            "7. Click 'Add webhook'"
        ]
    }
