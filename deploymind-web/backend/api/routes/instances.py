"""EC2 instance management routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from api.middleware.auth import get_current_active_user
from api.services.instance_service import InstanceService


router = APIRouter(prefix="/api/instances", tags=["Instances"])


class InstanceResponse(BaseModel):
    """EC2 instance response model."""
    instance_id: str
    instance_type: str
    state: str
    public_ip: Optional[str]
    private_ip: Optional[str]
    launch_time: Optional[str]
    tags: dict
    is_free_tier: bool


class InstanceDetailsResponse(InstanceResponse):
    """Detailed instance response."""
    availability_zone: Optional[str]
    vpc_id: Optional[str]
    subnet_id: Optional[str]
    security_groups: List[str]
    monitoring: Optional[str]


class ProvisionRequest(BaseModel):
    """Request to provision new instance."""
    name: str = Field(..., min_length=1, max_length=100, description="Instance name")
    instance_type: str = Field(default="t2.micro", description="Instance type")
    region: str = Field(default="us-east-1", description="AWS region")


class ProvisionResponse(BaseModel):
    """Provisioned instance response."""
    instance_id: str
    instance_type: str
    state: str
    name: str
    provisioned_at: str
    is_free_tier: bool
    estimated_monthly_cost: float
    region: str


class FreeTierUsageResponse(BaseModel):
    """Free tier usage response."""
    ec2_hours_used: int
    ec2_hours_limit: int
    ec2_hours_remaining: int
    percentage_used: float
    resets_in_days: int
    estimated_cost_if_exceeded: float
    recommendations: List[str]


class CostEstimateRequest(BaseModel):
    """Cost estimate request."""
    instance_type: str
    hours_per_month: int = Field(default=730, ge=1, le=744)


class CostEstimateResponse(BaseModel):
    """Cost estimate response."""
    instance_type: str
    hours_per_month: int
    free_tier_hours: int
    billable_hours: int
    hourly_rate: float
    free_tier_cost: float
    additional_cost: float
    total_monthly_cost: float
    is_within_free_tier: bool
    breakdown: dict


@router.get("", response_model=List[InstanceResponse])
async def list_instances(
    current_user: dict = Depends(get_current_active_user),
):
    """
    List all available EC2 instances.

    Returns list of instances with basic information.
    Filters to show only user's instances.
    """
    service = InstanceService()
    instances = await service.list_available_instances()

    return [
        InstanceResponse(
            instance_id=i["instance_id"],
            instance_type=i["instance_type"],
            state=i["state"],
            public_ip=i["public_ip"],
            private_ip=i["private_ip"],
            launch_time=i["launch_time"],
            tags=i["tags"],
            is_free_tier=i["is_free_tier"]
        )
        for i in instances
    ]


@router.get("/{instance_id}", response_model=InstanceDetailsResponse)
async def get_instance(
    instance_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get detailed information about a specific instance.

    Returns full instance details including network configuration.
    """
    service = InstanceService()
    instance = await service.get_instance_details(instance_id)

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found"
        )

    return InstanceDetailsResponse(**instance)


@router.post("", response_model=ProvisionResponse, status_code=status.HTTP_201_CREATED)
async def provision_instance(
    request: ProvisionRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Provision a new free tier EC2 instance.

    Creates a new t2.micro instance optimized for free tier usage.
    Instance will be automatically configured with:
    - Docker installed
    - Security groups for web traffic
    - SSH key pair for deployments
    """
    service = InstanceService()

    try:
        result = await service.provision_free_tier_instance(
            name=request.name,
            instance_type=request.instance_type,
            region=request.region
        )

        return ProvisionResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision instance: {str(e)}"
        )


@router.get("/free-tier/usage", response_model=FreeTierUsageResponse)
async def get_free_tier_usage(
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get current free tier usage statistics.

    Shows:
    - Hours used/remaining this month
    - Estimated cost if free tier exceeded
    - Recommendations for staying within free tier
    """
    service = InstanceService()
    user_id = current_user.get("user_id", 0)

    usage = await service.get_free_tier_usage(user_id)

    return FreeTierUsageResponse(**usage)


@router.post("/cost/estimate", response_model=CostEstimateResponse)
async def estimate_cost(
    request: CostEstimateRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Calculate estimated monthly cost for deployment.

    Provides detailed cost breakdown including:
    - Free tier hours coverage
    - Additional billable hours
    - Compute, storage, and network costs
    """
    service = InstanceService()

    result = await service.calculate_deployment_cost(
        instance_type=request.instance_type,
        hours_per_month=request.hours_per_month
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return CostEstimateResponse(**result)
