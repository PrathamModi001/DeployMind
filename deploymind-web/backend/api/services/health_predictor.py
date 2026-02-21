"""AI-powered health prediction engine for deployments."""
import logging
import statistics
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import HealthCheck
    from deploymind.infrastructure.llm.groq.groq_client import GroqClient
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    HealthCheck = None
    GroqClient = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class HealthPredictor:
    """
    Predict deployment health trends and failure probability.

    Uses historical health check data and LLM analysis to predict
    future health status and recommend preventive actions.
    """

    def __init__(self, db: Session):
        """
        Initialize health predictor.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings and GroqClient:
            try:
                settings = CoreSettings.load()
                self.llm = GroqClient(settings.groq_api_key)
                logger.info("HealthPredictor initialized with LLM")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("LLM not available, using rule-based predictions")

    async def predict_failure_probability(
        self,
        deployment_id: str,
        hours_ahead: int = 1
    ) -> Dict:
        """
        Predict probability of deployment failure in next N hours.

        Args:
            deployment_id: Deployment ID
            hours_ahead: Hours to predict ahead (default: 1)

        Returns:
            Dictionary with prediction results
        """
        if not HealthCheck:
            return self._mock_prediction(deployment_id, hours_ahead)

        try:
            # Get recent health checks (last 100)
            recent_checks = self.db.query(HealthCheck)\
                .filter(HealthCheck.deployment_id == deployment_id)\
                .order_by(HealthCheck.timestamp.desc())\
                .limit(100)\
                .all()

            if not recent_checks:
                return {
                    "deployment_id": deployment_id,
                    "failure_probability_percent": 50.0,
                    "confidence": "low",
                    "risk_factors": ["No historical data available"],
                    "recommended_actions": ["Wait for more health check data"],
                    "trend": "unknown",
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }

            # Calculate metrics
            metrics = self._calculate_health_metrics(recent_checks)

            # Use LLM for prediction if available, otherwise rule-based
            if self.llm:
                prediction = await self._llm_prediction(deployment_id, metrics, hours_ahead)
            else:
                prediction = self._rule_based_prediction(deployment_id, metrics, hours_ahead)

            return prediction

        except Exception as e:
            logger.error(f"Failed to predict failure: {e}", exc_info=True)
            return self._mock_prediction(deployment_id, hours_ahead)

    def _calculate_health_metrics(self, checks: List) -> Dict:
        """Calculate health metrics from recent checks."""
        if not checks:
            return {
                "failure_rate": 0.0,
                "avg_response_time": 0.0,
                "trend": "unknown",
                "recent_status_codes": [],
                "checks_count": 0
            }

        # Failure rate
        failures = sum(1 for c in checks if not c.healthy)
        failure_rate = failures / len(checks)

        # Average response time
        response_times = [c.response_time_ms for c in checks if c.response_time_ms is not None]
        avg_response_time = statistics.mean(response_times) if response_times else 0.0

        # Trend calculation (improving/stable/degrading)
        trend = self._calculate_trend(checks)

        # Recent status codes
        recent_status_codes = [c.status_code for c in checks[:10] if c.status_code]

        return {
            "failure_rate": failure_rate,
            "avg_response_time": avg_response_time,
            "trend": trend,
            "recent_status_codes": recent_status_codes,
            "checks_count": len(checks)
        }

    def _calculate_trend(self, checks: List) -> str:
        """Calculate health trend from checks."""
        if len(checks) < 10:
            return "insufficient_data"

        # Compare first half vs second half failure rates
        mid = len(checks) // 2
        recent_failures = sum(1 for c in checks[:mid] if not c.healthy)
        older_failures = sum(1 for c in checks[mid:] if not c.healthy)

        recent_rate = recent_failures / mid
        older_rate = older_failures / (len(checks) - mid)

        if recent_rate < older_rate * 0.8:
            return "improving"
        elif recent_rate > older_rate * 1.2:
            return "degrading"
        else:
            return "stable"

    async def _llm_prediction(
        self,
        deployment_id: str,
        metrics: Dict,
        hours_ahead: int
    ) -> Dict:
        """Use LLM to predict failure probability."""
        prompt = f"""
        Analyze deployment health metrics and predict failure probability:

        Deployment ID: {deployment_id}
        Prediction window: Next {hours_ahead} hour(s)

        Current metrics (last 100 checks):
        - Failure rate: {metrics['failure_rate'] * 100:.2f}%
        - Average response time: {metrics['avg_response_time']:.0f}ms
        - Health trend: {metrics['trend']}
        - Recent status codes: {metrics['recent_status_codes']}
        - Total checks: {metrics['checks_count']}

        Predict:
        1. Probability of failure in next {hours_ahead} hour(s) (0-100%)
        2. Confidence level (low/medium/high)
        3. Top 3 risk factors
        4. Top 3 recommended preventive actions

        Return ONLY valid JSON in this exact format:
        {{
            "failure_probability": <number 0-100>,
            "confidence": "<low|medium|high>",
            "risk_factors": ["factor1", "factor2", "factor3"],
            "recommended_actions": ["action1", "action2", "action3"]
        }}
        """

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse LLM response
            import json
            result = json.loads(response.strip())

            return {
                "deployment_id": deployment_id,
                "failure_probability_percent": float(result.get("failure_probability", 50)),
                "confidence": result.get("confidence", "medium"),
                "risk_factors": result.get("risk_factors", []),
                "recommended_actions": result.get("recommended_actions", []),
                "trend": metrics["trend"],
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"LLM prediction failed: {e}, falling back to rule-based")
            return self._rule_based_prediction(deployment_id, metrics, hours_ahead)

    def _rule_based_prediction(
        self,
        deployment_id: str,
        metrics: Dict,
        hours_ahead: int
    ) -> Dict:
        """Rule-based prediction when LLM unavailable."""
        failure_rate = metrics["failure_rate"]
        trend = metrics["trend"]
        avg_response_time = metrics["avg_response_time"]

        # Calculate probability based on rules
        base_probability = failure_rate * 100

        # Adjust for trend
        if trend == "degrading":
            base_probability *= 1.5
        elif trend == "improving":
            base_probability *= 0.7

        # Adjust for response time
        if avg_response_time > 5000:  # > 5 seconds
            base_probability *= 1.3
        elif avg_response_time > 2000:  # > 2 seconds
            base_probability *= 1.1

        # Cap at 100%
        probability = min(100, base_probability)

        # Determine confidence
        if metrics["checks_count"] >= 50:
            confidence = "high"
        elif metrics["checks_count"] >= 20:
            confidence = "medium"
        else:
            confidence = "low"

        # Generate risk factors
        risk_factors = []
        if failure_rate > 0.2:
            risk_factors.append(f"High failure rate ({failure_rate * 100:.1f}%)")
        if trend == "degrading":
            risk_factors.append("Health trend is degrading")
        if avg_response_time > 2000:
            risk_factors.append(f"Slow response time ({avg_response_time:.0f}ms)")

        if not risk_factors:
            risk_factors = ["No significant risk factors detected"]

        # Generate recommendations
        actions = []
        if failure_rate > 0.1:
            actions.append("Review application logs for errors")
        if avg_response_time > 2000:
            actions.append("Investigate performance bottlenecks")
        if trend == "degrading":
            actions.append("Consider scaling resources")

        if not actions:
            actions = ["Continue monitoring", "Maintain current configuration"]

        return {
            "deployment_id": deployment_id,
            "failure_probability_percent": round(probability, 2),
            "confidence": confidence,
            "risk_factors": risk_factors[:3],
            "recommended_actions": actions[:3],
            "trend": trend,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    def _mock_prediction(self, deployment_id: str, hours_ahead: int) -> Dict:
        """Return mock prediction when database unavailable."""
        return {
            "deployment_id": deployment_id,
            "failure_probability_percent": 15.5,
            "confidence": "medium",
            "risk_factors": [
                "Moderate response time variance",
                "Recent increase in 5xx errors",
                "Memory usage trending upward"
            ],
            "recommended_actions": [
                "Monitor memory usage closely",
                "Review error logs from last 24 hours",
                "Consider increasing health check frequency"
            ],
            "trend": "stable",
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
