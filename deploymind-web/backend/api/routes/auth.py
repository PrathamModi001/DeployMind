"""Authentication routes - GitHub OAuth only."""
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta
import httpx
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..schemas.auth import UserResponse, Token, GitHubOAuthRequest
from ..utils.jwt import create_access_token
from ..middleware.auth import get_current_active_user
from ..config import settings
from ..services.database import get_db
from ..repositories.user_repo import UserRepository

logger = logging.getLogger("uvicorn.error")
logger.info("=" * 50)
logger.info("AUTH ROUTES LOADED (GitHub OAuth Only)")
logger.info("=" * 50)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user information. Requires valid JWT token."""
    repo = UserRepository(db)
    # Use .get() for safe access, try both "user_id" and "id"
    user_id = current_user.get("user_id") or current_user.get("id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user_id")

    user = repo.get_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """Logout (client-side token removal)."""
    return {"message": "Successfully logged out"}


@router.get("/github")
async def github_oauth_url():
    """Get GitHub OAuth authorization URL."""
    logger.info("[GET /github] Building OAuth URL")
    github_oauth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=user:email,read:user,repo"
    )

    return {
        "url": github_oauth_url,
        "client_id": settings.github_client_id,
    }


@router.post("/github/callback")
async def github_oauth_callback(
    request: GitHubOAuthRequest,
    db: Session = Depends(get_db)
):
    """GitHub OAuth callback. Creates user if doesn't exist."""
    try:
        logger.info("[OAUTH] Starting GitHub OAuth")

        # Exchange code for GitHub access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": request.code,
                    "redirect_uri": settings.github_redirect_uri,
                }
            )

            token_data = token_response.json()

            if "error" in token_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}"
                )

            github_token = token_data.get("access_token")
            if not github_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get access token from GitHub"
                )

            # Get GitHub user data
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/json"
                }
            )
            github_user = user_response.json()

            # Get email (may not be public)
            email = github_user.get("email")
            if not email:
                email_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {github_token}",
                        "Accept": "application/json"
                    }
                )
                emails = email_response.json()
                for email_data in emails:
                    if email_data.get("primary"):
                        email = email_data.get("email")
                        break
                if not email and emails:
                    email = emails[0].get("email")

        user_email = email or f"{github_user['login']}@github.com"
        github_id = str(github_user["id"])

        repo = UserRepository(db)

        # Check if user exists by GitHub ID
        db_user = repo.get_by_github_id(github_id)

        if db_user:
            logger.info(f"[OAUTH] Existing user: {user_email}")
            # Update user info
            db_user = repo.update_user(
                db_user.id,
                avatar_url=github_user.get("avatar_url"),
                full_name=github_user.get("name") or github_user["login"],
            )
        else:
            logger.info(f"[OAUTH] Creating new user: {user_email}")
            # Create new user (GitHub OAuth - no password)
            try:
                db_user = repo.create_user(
                    email=user_email,
                    username=github_user["login"],
                    github_id=github_id,
                    avatar_url=github_user.get("avatar_url"),
                    full_name=github_user.get("name") or github_user["login"],
                )
            except IntegrityError:
                # Email or username might be taken
                db_user = repo.get_by_email(user_email)
                if not db_user:
                    # Try by username
                    db_user = repo.get_by_username(github_user["login"])
                if not db_user:
                    raise HTTPException(
                        status_code=400,
                        detail="User creation failed"
                    )

        # Create JWT token
        access_token = create_access_token(
            data={
                "user_id": db_user.id,
                "email": db_user.email,
                "username": db_user.username,
            },
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
        )

        logger.info(f"[OAUTH] SUCCESS! Token for: {db_user.email}")
        return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OAUTH] ERROR: {str(e)}")
        import traceback
        logger.error(f"[OAUTH] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth failed: {str(e)}"
        )
