"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta
import httpx

from ..schemas.auth import UserCreate, UserLogin, UserResponse, Token, GitHubOAuthRequest
from ..utils.jwt import create_access_token, get_password_hash, verify_password
from ..middleware.auth import get_current_active_user
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# Mock user database (replace with real database later)
_MOCK_USERS_CACHE = None


def get_mock_users():
    """Lazy initialize mock users to avoid bcrypt issues at import time."""
    global _MOCK_USERS_CACHE
    if _MOCK_USERS_CACHE is None:
        _MOCK_USERS_CACHE = {
            "admin@deploymind.io": {
                "id": 1,
                "email": "admin@deploymind.io",
                "username": "admin",
                "full_name": "Admin User",
                "hashed_password": get_password_hash("admin123"),  # Default password: admin123
                "is_active": True,
                "is_superuser": True,
            }
        }
    return _MOCK_USERS_CACHE


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """
    Register a new user.

    Creates a new user account with hashed password.
    """
    # Check if user already exists
    if user.email in get_mock_users():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    user_id = len(get_mock_users()) + 1
    hashed_password = get_password_hash(user.password)

    new_user = {
        "id": user_id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_superuser": False,
    }

    get_mock_users()[user.email] = new_user

    return UserResponse(
        id=new_user["id"],
        email=new_user["email"],
        username=new_user["username"],
        full_name=new_user["full_name"],
        is_active=new_user["is_active"],
        is_superuser=new_user["is_superuser"],
        created_at="2026-02-14T00:00:00"  # Mock timestamp
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """
    Login with email and password.

    Returns a JWT access token for authentication.
    """
    # Find user
    user = get_mock_users().get(credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "user_id": user["id"],
            "email": user["email"],
            "username": user["username"],
        },
        expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    Get current user information.

    Requires valid JWT token.
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user.get("full_name"),
        is_active=current_user["is_active"],
        is_superuser=current_user["is_superuser"],
        created_at="2026-02-14T00:00:00"  # Mock timestamp
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """
    Logout (client-side token removal).

    Note: JWT tokens are stateless, so logout is handled client-side by removing the token.
    """
    return {"message": "Successfully logged out"}


@router.get("/github")
async def github_oauth_url():
    """
    Get GitHub OAuth authorization URL.

    Returns the URL to redirect user to for GitHub OAuth.
    """
    # Build OAuth URL
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
async def github_oauth_callback(request: GitHubOAuthRequest):
    """
    GitHub OAuth callback.

    Exchanges authorization code for access token and creates user session.
    """
    try:
        # Step 1: Exchange authorization code for GitHub access token
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

            github_access_token = token_data.get("access_token")

            if not github_access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get access token from GitHub"
                )

            # Step 2: Fetch user data from GitHub API
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {github_access_token}",
                    "Accept": "application/json"
                }
            )

            github_user_data = user_response.json()

            # Step 3: Get user email if not public
            email = github_user_data.get("email")
            if not email:
                email_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {github_access_token}",
                        "Accept": "application/json"
                    }
                )
                emails = email_response.json()
                # Get primary email
                for email_data in emails:
                    if email_data.get("primary"):
                        email = email_data.get("email")
                        break
                if not email and emails:
                    email = emails[0].get("email")

        # Step 4: Create or update user in mock database
        user_email = email or f"{github_user_data['login']}@github.com"

        # Check if user exists
        existing_user = get_mock_users().get(user_email)

        if existing_user:
            # Update existing user
            mock_user = existing_user
            mock_user.update({
                "github_id": github_user_data["id"],
                "avatar_url": github_user_data.get("avatar_url"),
                "full_name": github_user_data.get("name") or github_user_data["login"],
            })
        else:
            # Create new user
            user_id = len(get_mock_users()) + 1
            mock_user = {
                "id": user_id,
                "email": user_email,
                "username": github_user_data["login"],
                "full_name": github_user_data.get("name") or github_user_data["login"],
                "is_active": True,
                "is_superuser": False,
                "github_id": github_user_data["id"],
                "avatar_url": github_user_data.get("avatar_url"),
            }
            get_mock_users()[user_email] = mock_user

        # Step 5: Create JWT access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={
                "user_id": mock_user["id"],
                "email": mock_user["email"],
                "username": mock_user["username"],
            },
            expires_delta=access_token_expires
        )

        return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth failed: {str(e)}"
        )
