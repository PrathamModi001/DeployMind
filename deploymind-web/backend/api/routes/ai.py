"""AI-powered features routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from ..middleware.auth import get_current_active_user
from ..ai import (
    DeploymentRecommender,
    CostOptimizer,
    RollbackAdvisor,
    SecurityExplainer,
)

router = APIRouter(prefix="/api/ai", tags=["AI Features"])


# Request/Response schemas
class InstanceRecommendationRequest(BaseModel):
    repository: str
    language: Optional[str] = None
    traffic_estimate: str = "medium"


class CostAnalysisRequest(BaseModel):
    deployment_count: int
    avg_duration_seconds: float
    instance_types: dict = {}


class RollbackAnalysisRequest(BaseModel):
    deployment_id: str
    failed_checks: int = 0
    total_checks: int = 1
    error_messages: List[str] = []
    deployment_age_minutes: int = 0


class VulnerabilityExplanationRequest(BaseModel):
    cve_id: str
    package: str
    severity: str
    description: str = ""


@router.post("/recommend/instance")
async def recommend_instance_type(
    request: InstanceRecommendationRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get AI-powered EC2 instance recommendation.

    Analyzes repository, language, and traffic to suggest optimal instance.
    """
    recommender = DeploymentRecommender()

    recommendation = await recommender.recommend_instance(
        repository=request.repository,
        language=request.language,
        traffic_estimate=request.traffic_estimate,
    )

    return recommendation


@router.post("/recommend/strategy")
async def recommend_deployment_strategy(
    current_status: str = Query(..., description="Current deployment status"),
    deployment_count: int = Query(0, description="Total deployments"),
    success_rate: float = Query(100.0, description="Success rate percentage"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get AI-powered deployment strategy recommendation.

    Analyzes deployment history to suggest best strategy.
    """
    recommender = DeploymentRecommender()

    recommendation = await recommender.recommend_strategy(
        current_status=current_status,
        deployment_count=deployment_count,
        success_rate=success_rate,
    )

    return recommendation


@router.post("/optimize/costs")
async def analyze_costs(
    request: CostAnalysisRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get AI-powered cost optimization suggestions.

    Analyzes deployment patterns and suggests cost savings.
    """
    optimizer = CostOptimizer()

    analysis = await optimizer.analyze_costs(
        deployment_count=request.deployment_count,
        avg_duration_seconds=request.avg_duration_seconds,
        instance_types=request.instance_types,
    )

    return analysis


@router.get("/optimize/estimate")
async def estimate_deployment_cost(
    instance_type: str = Query(..., description="EC2 instance type"),
    duration_hours: float = Query(..., description="Deployment duration in hours"),
    environment: str = Query("production", description="Environment"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Estimate cost for a specific deployment.

    Provides cost breakdown and optimization tips.
    """
    optimizer = CostOptimizer()

    estimate = await optimizer.estimate_deployment_cost(
        instance_type=instance_type,
        duration_hours=duration_hours,
        environment=environment,
    )

    return estimate


@router.post("/rollback/analyze")
async def analyze_rollback_decision(
    request: RollbackAnalysisRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get AI-powered rollback recommendation.

    Analyzes deployment health and recommends whether to rollback.
    """
    advisor = RollbackAdvisor()

    decision = await advisor.should_rollback(
        deployment_id=request.deployment_id,
        failed_checks=request.failed_checks,
        total_checks=request.total_checks,
        error_messages=request.error_messages,
        deployment_age_minutes=request.deployment_age_minutes,
    )

    return decision


@router.post("/security/explain")
async def explain_vulnerability(
    request: VulnerabilityExplanationRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get simple explanation of security vulnerability.

    Provides ELI5 explanation with actionable fix steps.
    """
    explainer = SecurityExplainer()

    explanation = await explainer.explain_vulnerability(
        cve_id=request.cve_id,
        package=request.package,
        severity=request.severity,
        description=request.description,
    )

    return explanation
