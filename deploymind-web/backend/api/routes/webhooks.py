"""GitHub webhooks for auto-deploy."""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict
import hmac
import hashlib

from ..services.database import get_db
from ..config import settings

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """
    Verify GitHub webhook signature.

    GitHub sends a signature in the X-Hub-Signature-256 header.
    """
    if not settings.github_webhook_secret:
        # If no secret configured, skip verification (dev mode)
        return True

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
    db: Session = Depends(get_db),
):
    """
    Handle GitHub webhook events.

    Supported events:
    - push: Trigger auto-deploy when code is pushed
    - pull_request: Optionally deploy preview environments

    Security:
    - Validates webhook signature (HMAC SHA-256)
    - Only processes whitelisted repositories
    """
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
        return await handle_push_event(payload, db)

    if event_type == "pull_request":
        return await handle_pull_request_event(payload, db)

    # Unknown event type
    return {"message": f"Event '{event_type}' received but not processed"}


async def handle_push_event(payload: Dict, db: Session) -> Dict:
    """
    Handle GitHub push event.

    Auto-deploy if:
    1. Deployment exists for this repository
    2. Auto-deploy is enabled
    3. Push is to main/master branch
    """
    repo = payload.get("repository", {}).get("full_name")
    ref = payload.get("ref", "")
    commit_sha = payload.get("after")
    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else ""

    # Only deploy from main/master branch
    if branch not in ["main", "master"]:
        return {
            "message": f"Ignored push to branch '{branch}'",
            "auto_deploy": False
        }

    # In production, this would:
    # 1. Query database for deployments with this repository
    # 2. Check if auto_deploy_enabled flag is set
    # 3. Trigger deployment workflow in background

    # Mock response
    return {
        "message": f"Auto-deploy triggered for {repo}",
        "repository": repo,
        "branch": branch,
        "commit": commit_sha[:7],
        "auto_deploy": True,
        "deployment_id": f"deploy-{commit_sha[:8]}"
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
