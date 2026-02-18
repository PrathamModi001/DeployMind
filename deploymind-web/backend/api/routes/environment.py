"""Environment variables management routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from ..services.database import get_db
from ..middleware.auth import get_current_active_user
from ..models.environment_variable import EnvironmentVariable

router = APIRouter(prefix="/api/deployments", tags=["Environment Variables"])


class EnvVarCreate(BaseModel):
    key: str
    value: str
    is_secret: bool = False


class EnvVarResponse(BaseModel):
    id: int
    key: str
    value: str
    is_secret: bool

    class Config:
        from_attributes = True


@router.get("/{deployment_id}/env", response_model=List[EnvVarResponse])
async def list_env_vars(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all environment variables for a deployment."""
    env_vars = (
        db.query(EnvironmentVariable)
        .filter(EnvironmentVariable.deployment_id == deployment_id)
        .all()
    )

    # Mask secret values
    result = []
    for env_var in env_vars:
        result.append(
            EnvVarResponse(
                id=env_var.id,
                key=env_var.key,
                value="••••••••" if env_var.is_secret else env_var.value,
                is_secret=env_var.is_secret,
            )
        )

    return result


@router.post("/{deployment_id}/env", response_model=EnvVarResponse, status_code=status.HTTP_201_CREATED)
async def create_env_var(
    deployment_id: str,
    env_var: EnvVarCreate,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new environment variable."""
    # Check if key already exists
    existing = (
        db.query(EnvironmentVariable)
        .filter(
            EnvironmentVariable.deployment_id == deployment_id,
            EnvironmentVariable.key == env_var.key,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Environment variable '{env_var.key}' already exists",
        )

    # Create new environment variable
    db_env_var = EnvironmentVariable(
        deployment_id=deployment_id,
        key=env_var.key,
        value=env_var.value,
        is_secret=env_var.is_secret,
    )

    db.add(db_env_var)
    db.commit()
    db.refresh(db_env_var)

    return EnvVarResponse(
        id=db_env_var.id,
        key=db_env_var.key,
        value="••••••••" if db_env_var.is_secret else db_env_var.value,
        is_secret=db_env_var.is_secret,
    )


@router.put("/{deployment_id}/env/{env_id}", response_model=EnvVarResponse)
async def update_env_var(
    deployment_id: str,
    env_id: int,
    env_var: EnvVarCreate,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update an environment variable."""
    db_env_var = (
        db.query(EnvironmentVariable)
        .filter(
            EnvironmentVariable.id == env_id,
            EnvironmentVariable.deployment_id == deployment_id,
        )
        .first()
    )

    if not db_env_var:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment variable not found",
        )

    # Update fields
    db_env_var.key = env_var.key
    db_env_var.value = env_var.value
    db_env_var.is_secret = env_var.is_secret

    db.commit()
    db.refresh(db_env_var)

    return EnvVarResponse(
        id=db_env_var.id,
        key=db_env_var.key,
        value="••••••••" if db_env_var.is_secret else db_env_var.value,
        is_secret=db_env_var.is_secret,
    )


@router.delete("/{deployment_id}/env/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_env_var(
    deployment_id: str,
    env_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete an environment variable."""
    db_env_var = (
        db.query(EnvironmentVariable)
        .filter(
            EnvironmentVariable.id == env_id,
            EnvironmentVariable.deployment_id == deployment_id,
        )
        .first()
    )

    if not db_env_var:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment variable not found",
        )

    db.delete(db_env_var)
    db.commit()

    return None
