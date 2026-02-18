"""File upload endpoints for .env files."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import logging

from api.middleware.auth import get_current_active_user
from api.services.env_parser import EnvFileParser
from api.services.database import get_db
from api.models.environment_variable import EnvironmentVariable

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


class EnvUploadResponse(BaseModel):
    """Response after uploading .env file."""
    uploaded: int
    variables: List[dict]
    validation: dict


@router.post("/env/{deployment_id}", response_model=EnvUploadResponse)
async def upload_env_file(
    deployment_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload and parse .env file for deployment.

    Automatically detects secrets and creates environment variables.

    Args:
        deployment_id: ID of deployment to attach env vars to
        file: Uploaded .env file
        current_user: Authenticated user

    Returns:
        Upload results with parsed variables
    """
    # Validate file type
    if not file.filename.endswith('.env'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a .env file"
        )

    # Read file content
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file encoding. File must be UTF-8 encoded"
        )

    # Validate file size (max 1MB)
    if len(content) > 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 1MB"
        )

    # Parse and validate env file
    parser = EnvFileParser()
    validation = parser.validate_env_file(content_str)

    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid .env file format. {validation['invalid_lines']} invalid lines found"
        )

    # Parse env file
    variables = parser.parse_env_file(content_str)

    # Create environment variables in database
    created_vars = []

    # Check for duplicates and create
    for var in variables:
        # Check if key already exists for this deployment
        existing = db.query(EnvironmentVariable)\
            .filter(
                EnvironmentVariable.deployment_id == deployment_id,
                EnvironmentVariable.key == var["key"]
            )\
            .first()

        if existing:
            # Update existing variable
            existing.value = var["value"]
            existing.is_secret = var["is_secret"]
        else:
            # Create new variable
            env_var = EnvironmentVariable(
                deployment_id=deployment_id,
                key=var["key"],
                value=var["value"],
                is_secret=var["is_secret"]
            )
            db.add(env_var)

        created_vars.append({
            "key": var["key"],
            "is_secret": var["is_secret"],
            "value": "••••••••" if var["is_secret"] else var["value"]
        })

    db.commit()

    return {
        "uploaded": len(created_vars),
        "variables": created_vars,
        "validation": validation
    }


@router.post("/env/{deployment_id}/validate")
async def validate_env_file(
    deployment_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Validate .env file without uploading.

    Args:
        deployment_id: ID of deployment
        file: .env file to validate
        current_user: Authenticated user

    Returns:
        Validation results
    """
    # Read file content
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file encoding. File must be UTF-8 encoded"
        )

    # Validate
    parser = EnvFileParser()
    validation = parser.validate_env_file(content_str)

    # Parse to show what would be created
    variables = parser.parse_env_file(content_str)

    return {
        "validation": validation,
        "preview": [
            {
                "key": v["key"],
                "is_secret": v["is_secret"],
                "value": "••••••••" if v["is_secret"] else v["value"]
            }
            for v in variables
        ]
    }
