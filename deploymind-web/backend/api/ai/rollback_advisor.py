"""AI-powered intelligent rollback advisor."""
import json
import logging
from typing import Dict, List
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

logger = logging.getLogger(__name__)


class RollbackAdvisor:
    """AI-powered rollback decision engine."""

    def __init__(self):
        """Initialize advisor with Groq client."""
        try:
            from deploymind.infrastructure.llm.groq.groq_client import GroqClient
            from deploymind.config.settings import Settings as CoreSettings
            settings = CoreSettings.load()
            self.llm = GroqClient(settings.groq_api_key)
            self.llm_available = True
        except (ImportError, Exception) as e:
            logger.warning(f"Groq LLM not available: {e}")
            self.llm = None
            self.llm_available = False

    async def should_rollback(
        self,
        deployment_id: str,
        failed_checks: int,
        total_checks: int,
        error_messages: List[str],
        deployment_age_minutes: int,
    ) -> Dict:
        """
        Analyze deployment health and recommend rollback if needed.

        Args:
            deployment_id: Deployment identifier
            failed_checks: Number of failed health checks
            total_checks: Total health checks performed
            error_messages: List of error messages
            deployment_age_minutes: Minutes since deployment

        Returns:
            Rollback recommendation with confidence and reasoning
        """
        failure_rate = (failed_checks / total_checks * 100) if total_checks > 0 else 0

        if not self.llm_available:
            return self._mock_rollback_decision(
                failure_rate, error_messages, deployment_age_minutes
            )

        prompt = f"""Analyze deployment health and recommend rollback decision:

Deployment ID: {deployment_id}
Failed health checks: {failed_checks}/{total_checks} ({failure_rate:.1f}%)
Deployment age: {deployment_age_minutes} minutes
Recent errors: {json.dumps(error_messages[:5])}

Consider:
- Failure rate threshold (>30% is concerning)
- Error patterns (consistent vs intermittent)
- Time since deployment (grace period for startup)
- Severity of errors

Return ONLY a JSON object:
{{
    "should_rollback": true or false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation (2-3 sentences)",
    "suggested_action": "specific action to take",
    "urgency": "low|medium|high|critical"
}}"""

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response)

        except Exception as e:
            logger.error(f"Rollback analysis failed: {e}")
            return self._mock_rollback_decision(
                failure_rate, error_messages, deployment_age_minutes
            )

    def _mock_rollback_decision(
        self,
        failure_rate: float,
        errors: List[str],
        age_minutes: int
    ) -> Dict:
        """Fallback rollback decision logic."""
        # Grace period for startup (first 5 minutes)
        if age_minutes < 5:
            return {
                "should_rollback": False,
                "confidence": 0.7,
                "reasoning": "Deployment is still in startup phase. "
                           "Allow more time for application initialization.",
                "suggested_action": "Monitor for 5 more minutes",
                "urgency": "low"
            }

        # Critical failure rate
        if failure_rate >= 70:
            return {
                "should_rollback": True,
                "confidence": 0.95,
                "reasoning": f"Severe failure rate ({failure_rate:.1f}%) indicates "
                           "critical issues. Immediate rollback recommended.",
                "suggested_action": "Rollback immediately to previous stable version",
                "urgency": "critical"
            }

        # High failure rate
        elif failure_rate >= 40:
            return {
                "should_rollback": True,
                "confidence": 0.85,
                "reasoning": f"High failure rate ({failure_rate:.1f}%) with "
                           "concerning error patterns. Rollback advised.",
                "suggested_action": "Rollback and investigate errors",
                "urgency": "high"
            }

        # Moderate failure rate
        elif failure_rate >= 20:
            return {
                "should_rollback": False,
                "confidence": 0.6,
                "reasoning": f"Moderate failure rate ({failure_rate:.1f}%). "
                           "Monitor closely before deciding.",
                "suggested_action": "Continue monitoring for 10 more minutes",
                "urgency": "medium"
            }

        # Low failure rate
        else:
            return {
                "should_rollback": False,
                "confidence": 0.9,
                "reasoning": f"Low failure rate ({failure_rate:.1f}%) is within "
                           "acceptable limits. Deployment appears healthy.",
                "suggested_action": "Continue normal monitoring",
                "urgency": "low"
            }
