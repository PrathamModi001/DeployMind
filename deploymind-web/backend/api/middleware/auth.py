"""Authentication middleware and dependencies."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from ..utils.jwt import decode_access_token
from ..models.user import User

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    # db: Session = Depends(get_db)  # We'll add this when we integrate with database
) -> dict:
    """
    Get current user from JWT token.

    Returns user data from token payload.
    For now, returns mock data until database integration is complete.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: Optional[int] = payload.get("user_id")
    email: Optional[str] = payload.get("email")

    if user_id is None or email is None:
        raise credentials_exception

    # For now, return payload data
    # TODO: Query database to get full user object
    return {
        "id": user_id,
        "email": email,
        "username": payload.get("username", ""),
        "is_active": True,
        "is_superuser": False,
    }


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get current active user (must be active)."""
    if not current_user.get("is_active"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_superuser(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get current superuser (admin access required)."""
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
