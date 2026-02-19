"""Advanced AI features routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from api.middleware.auth import get_current_active_user
from api.services.database import get_db
from api.services.health_predictor import HealthPredictor
from api.services.anomaly_detector import AnomalyDetector
from api.services.autoscaling_advisor import AutoScalingAdvisor
from api.services.cost_analyzer import CostAnalyzer
from api.services.risk_scorer import SecurityRiskScorer
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/ai/advanced", tags=["AI Advanced"])


# Response Models
class HealthPredictionResponse(BaseModel):
    """Health prediction response."""
    deployment_id: str
    failure_probability_percent: float
    confidence: str
    risk_factors: List[str]
    recommended_actions: List[str]
    trend: str
    analysis_timestamp: str


class AnomalyDetectionResponse(BaseModel):
    """Anomaly detection response."""
    deployment_id: str
    anomalies_detected: bool
    anomalies: List[Dict]
    severity: str
    root_cause_hypotheses: List[str]
    analysis_timestamp: str


class ScalingRecommendationResponse(BaseModel):
    """Auto-scaling recommendation response."""
    deployment_id: str
    should_scale: bool
    scaling_type: Optional[str] = None
    current_config: Dict
    recommended_config: Optional[Dict] = None
    cost_impact_monthly: Optional[float] = None
    performance_improvement: Optional[str] = None
    reasoning: Optional[str] = None
    analysis_timestamp: Optional[str] = None


class CostAnalysisResponse(BaseModel):
    """Cost trend analysis response."""
    user_id: int
    trend: str
    monthly_growth_rate_percent: float
    monthly_costs: List[Dict]
    total_cost_current_month: float
    forecast_next_3_months: List[Dict]
    optimization_opportunities: List[str]
    potential_savings_monthly: float
    analysis_timestamp: str


class RiskScoreResponse(BaseModel):
    """Security risk score response."""
    deployment_id: str
    risk_score: float
    rating: str
    confidence: str
    risk_factors: List[str]
    remediation_steps: List[str]
    scan_coverage: Dict
    analysis_timestamp: str


@router.post("/health-prediction/{deployment_id}", response_model=HealthPredictionResponse)
async def predict_health(
    deployment_id: str,
    hours_ahead: int = Query(default=1, ge=1, le=24, description="Hours to predict ahead"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Predict deployment failure probability.

    Analyzes historical health check data to predict the probability
    of deployment failure in the next N hours.

    Uses AI to identify risk factors and recommend preventive actions.
    """
    predictor = HealthPredictor(db)

    try:
        result = await predictor.predict_failure_probability(
            deployment_id=deployment_id,
            hours_ahead=hours_ahead
        )

        return HealthPredictionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health prediction failed: {str(e)}"
        )


@router.post("/anomaly-detection/{deployment_id}", response_model=AnomalyDetectionResponse)
async def detect_anomalies(
    deployment_id: str,
    hours_lookback: int = Query(default=24, ge=1, le=168, description="Hours of history to analyze"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Detect metric anomalies in deployment.

    Analyzes CPU, memory, and network metrics to identify unusual
    patterns that may indicate problems.

    Uses statistical analysis and AI to suggest root causes.
    """
    detector = AnomalyDetector(db)

    try:
        result = await detector.detect_metric_anomalies(
            deployment_id=deployment_id,
            hours_lookback=hours_lookback
        )

        return AnomalyDetectionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.post("/scaling-recommendation/{deployment_id}", response_model=ScalingRecommendationResponse)
async def recommend_scaling(
    deployment_id: str,
    hours_lookback: int = Query(default=6, ge=1, le=72, description="Hours to analyze"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get auto-scaling recommendations.

    Analyzes resource utilization and recommends horizontal or
    vertical scaling to optimize performance and cost.

    Provides detailed cost impact analysis and performance estimates.
    """
    advisor = AutoScalingAdvisor(db)

    try:
        result = await advisor.recommend_scaling(
            deployment_id=deployment_id,
            hours_lookback=hours_lookback
        )

        return ScalingRecommendationResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scaling recommendation failed: {str(e)}"
        )


@router.get("/cost-analysis", response_model=CostAnalysisResponse)
async def analyze_costs(
    months_lookback: int = Query(default=6, ge=1, le=12, description="Months of history"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Analyze cost trends and forecast future spending.

    Tracks deployment costs, identifies spending trends, and
    predicts future costs for the next 3 months.

    Provides optimization recommendations to reduce cloud spending.
    """
    analyzer = CostAnalyzer(db)
    user_id = current_user.get("id", 0)

    try:
        result = await analyzer.analyze_cost_trends(
            user_id=user_id,
            months_lookback=months_lookback
        )

        return CostAnalysisResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost analysis failed: {str(e)}"
        )


@router.post("/security-risk/{deployment_id}", response_model=RiskScoreResponse)
async def calculate_risk_score(
    deployment_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Calculate security risk score for deployment.

    Analyzes security scan results and assigns a risk score (0-100)
    with rating (LOW/MEDIUM/HIGH/CRITICAL).

    Provides specific risk factors and remediation steps.
    """
    scorer = SecurityRiskScorer(db)

    try:
        result = await scorer.calculate_risk_score(deployment_id=deployment_id)

        return RiskScoreResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk scoring failed: {str(e)}"
        )
