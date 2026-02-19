"""User repository for database operations.

Handles CRUD operations for User model with clean separation of concerns.
GitHub OAuth only - no password authentication.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.user import User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.db.query(User).filter(User.username == username).first()

    def get_by_github_id(self, github_id: str) -> Optional[User]:
        """Get user by GitHub OAuth ID."""
        return self.db.query(User).filter(User.github_id == github_id).first()

    def create_user(
        self,
        email: str,
        username: str,
        github_id: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        github_access_token: Optional[str] = None,
    ) -> User:
        """
        Create new user (GitHub OAuth only).

        Args:
            email: User email (required)
            username: Username (required)
            github_id: GitHub OAuth ID (required)
            full_name: User's full name
            avatar_url: Profile picture URL
            github_access_token: User's GitHub OAuth access token

        Returns:
            User: Created user object

        Raises:
            IntegrityError: If email, username, or github_id already exists
        """
        user = User(
            email=email,
            username=username,
            github_id=github_id,
            full_name=full_name,
            avatar_url=avatar_url,
            github_access_token=github_access_token,
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """
        Update user fields.

        Args:
            user_id: User ID to update
            **kwargs: Fields to update

        Returns:
            Updated user or None if not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return None

        # Update allowed fields
        for key, value in kwargs.items():
            if hasattr(user, key) and key != "id":
                setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """
        Delete user by ID.

        Args:
            user_id: User ID to delete

        Returns:
            True if deleted, False if not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True
