"""AI-powered deployment recommendations using Groq LLM."""
import json
import logging
from typing import Dict, Optional
import sys
from pathlib import Path

# Add deploymind-core to path for Groq client
core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

logger = logging.getLogger(__name__)


class DeploymentRecommender:
    """AI-powered deployment recommendation engine."""

    def __init__(self):
        """Initialize recommender with Groq client."""
        try:
            from deploymind.infrastructure.llm.groq.groq_client import GroqClient
            from deploymind.config.settings import Settings as CoreSettings
            settings = CoreSettings.load()
            self.llm = GroqClient(settings.groq_api_key)
            self.llm_available = True
        except (ImportError, Exception) as e:
            logger.warning(f"Groq LLM not available: {e}. Using mock responses.")
            self.llm = None
            self.llm_available = False

    async def recommend_instance(
        self,
        repository: str,
        language: Optional[str] = None,
        traffic_estimate: str = "low",
    ) -> Dict:
        """
        Recommend optimal EC2 instance type.

        Args:
            repository: GitHub repository name
            language: Programming language (detected or provided)
            traffic_estimate: Expected traffic (low, medium, high)

        Returns:
            Recommendation with instance type, reasoning, cost estimate
        """
        if not self.llm_available:
            return self._mock_instance_recommendation(repository, language, traffic_estimate)

        prompt = f"""Analyze this deployment and recommend an AWS EC2 instance type:

Repository: {repository}
Language: {language or 'unknown'}
Expected traffic: {traffic_estimate}

Consider:
- CPU and memory requirements for {language or 'typical web'} applications
- Cost-effectiveness
- Traffic handling capacity
- Scalability

Return ONLY a JSON object with this exact structure:
{{
    "recommended_instance": "instance type (e.g., t2.small)",
    "reasoning": "brief explanation (2-3 sentences)",
    "estimated_cost_monthly_usd": numeric value,
    "alternatives": ["alternative1", "alternative2"]
}}"""

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            result = json.loads(response)
            return result

        except Exception as e:
            logger.error(f"LLM recommendation failed: {e}")
            return self._mock_instance_recommendation(repository, language, traffic_estimate)

    def _mock_instance_recommendation(
        self,
        repository: str,
        language: Optional[str],
        traffic_estimate: str
    ) -> Dict:
        """Fallback mock recommendation."""
        traffic_map = {
            "low": ("t2.micro", 8.50, ["t2.nano", "t2.small"]),
            "medium": ("t2.small", 16.79, ["t2.micro", "t2.medium"]),
            "high": ("t2.medium", 33.58, ["t2.small", "t2.large"]),
        }

        instance, cost, alternatives = traffic_map.get(
            traffic_estimate.lower(),
            traffic_map["medium"]
        )

        return {
            "recommended_instance": instance,
            "reasoning": f"Based on {traffic_estimate} traffic expectations, "
                        f"{instance} provides optimal cost-performance balance. "
                        f"Good fit for {language or 'web'} applications.",
            "estimated_cost_monthly_usd": cost,
            "alternatives": alternatives,
        }

    async def recommend_strategy(
        self,
        current_status: str,
        deployment_count: int,
        success_rate: float,
    ) -> Dict:
        """
        Recommend deployment strategy based on history.

        Args:
            current_status: Current deployment status
            deployment_count: Total deployments
            success_rate: Success rate percentage

        Returns:
            Strategy recommendation
        """
        if not self.llm_available:
            return self._mock_strategy_recommendation(success_rate)

        prompt = f"""Recommend a deployment strategy:

Current status: {current_status}
Total deployments: {deployment_count}
Success rate: {success_rate}%

Available strategies:
- rolling: Deploy gradually, replace instances one by one
- blue-green: Deploy to parallel environment, switch traffic
- canary: Deploy to small subset, monitor, then roll out

Return ONLY a JSON object:
{{
    "recommended_strategy": "strategy name",
    "reasoning": "why this strategy is best",
    "risk_level": "low|medium|high"
}}"""

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response)

        except Exception as e:
            logger.error(f"Strategy recommendation failed: {e}")
            return self._mock_strategy_recommendation(success_rate)

    def _mock_strategy_recommendation(self, success_rate: float) -> Dict:
        """Fallback strategy recommendation."""
        if success_rate >= 95:
            return {
                "recommended_strategy": "rolling",
                "reasoning": "High success rate indicates stable deployments. "
                           "Rolling strategy is efficient and safe.",
                "risk_level": "low"
            }
        elif success_rate >= 80:
            return {
                "recommended_strategy": "canary",
                "reasoning": "Moderate success rate suggests some risk. "
                           "Canary deployment allows early issue detection.",
                "risk_level": "medium"
            }
        else:
            return {
                "recommended_strategy": "blue-green",
                "reasoning": "Lower success rate indicates higher risk. "
                           "Blue-green deployment allows instant rollback.",
                "risk_level": "high"
            }
