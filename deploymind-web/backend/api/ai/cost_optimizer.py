"""AI-powered cost optimization advisor."""
import json
import logging
from typing import Dict, List
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

logger = logging.getLogger(__name__)


class CostOptimizer:
    """AI-powered cost optimization analyzer."""

    def __init__(self):
        """Initialize optimizer with Groq client."""
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

    async def analyze_costs(
        self,
        deployment_count: int,
        avg_duration_seconds: float,
        instance_types: Dict[str, int],
    ) -> Dict:
        """
        Analyze deployment costs and suggest optimizations.

        Args:
            deployment_count: Total number of deployments
            avg_duration_seconds: Average deployment duration
            instance_types: Dictionary of instance types and counts

        Returns:
            Cost analysis with optimization suggestions
        """
        if not self.llm_available:
            return self._mock_cost_analysis(deployment_count, avg_duration_seconds)

        prompt = f"""Analyze deployment costs and suggest optimizations:

Metrics:
- Total deployments: {deployment_count}
- Average deployment time: {avg_duration_seconds:.0f} seconds
- Instance distribution: {json.dumps(instance_types)}

Consider:
- Reserved instances vs on-demand
- Right-sizing opportunities
- Auto-scaling potential
- Spot instances for dev/staging

Return ONLY a JSON object:
{{
    "current_monthly_cost_usd": estimated number,
    "potential_savings_usd": estimated savings,
    "optimization_suggestions": [
        {{"action": "...", "impact": "...", "savings_usd": number}}
    ],
    "priority": "low|medium|high"
}}"""

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response)

        except Exception as e:
            logger.error(f"Cost analysis failed: {e}")
            return self._mock_cost_analysis(deployment_count, avg_duration_seconds)

    def _mock_cost_analysis(
        self,
        deployment_count: int,
        avg_duration: float
    ) -> Dict:
        """Fallback mock cost analysis."""
        # Estimate: $0.50 per deployment
        current_cost = deployment_count * 0.50
        potential_savings = current_cost * 0.25  # 25% savings potential

        return {
            "current_monthly_cost_usd": round(current_cost, 2),
            "potential_savings_usd": round(potential_savings, 2),
            "optimization_suggestions": [
                {
                    "action": "Use reserved instances for production workloads",
                    "impact": "Save up to 40% on compute costs",
                    "savings_usd": round(current_cost * 0.15, 2)
                },
                {
                    "action": "Enable auto-scaling for variable traffic",
                    "impact": "Reduce idle resource costs",
                    "savings_usd": round(current_cost * 0.10, 2)
                }
            ],
            "priority": "medium" if potential_savings > 10 else "low"
        }

    async def estimate_deployment_cost(
        self,
        instance_type: str,
        duration_hours: float,
        environment: str
    ) -> Dict:
        """
        Estimate cost for a specific deployment.

        Args:
            instance_type: EC2 instance type
            duration_hours: Expected deployment duration
            environment: Environment (dev, staging, production)

        Returns:
            Cost estimate breakdown
        """
        # EC2 pricing (simplified, actual pricing varies by region)
        pricing = {
            "t2.nano": 0.0058,
            "t2.micro": 0.0116,
            "t2.small": 0.0230,
            "t2.medium": 0.0464,
            "t2.large": 0.0928,
        }

        hourly_rate = pricing.get(instance_type, 0.0230)
        compute_cost = hourly_rate * duration_hours

        # Add data transfer (estimate)
        data_transfer_cost = 0.01 * duration_hours

        total_cost = compute_cost + data_transfer_cost

        return {
            "instance_type": instance_type,
            "duration_hours": duration_hours,
            "hourly_rate_usd": hourly_rate,
            "compute_cost_usd": round(compute_cost, 4),
            "data_transfer_cost_usd": round(data_transfer_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "environment": environment,
            "optimization_tip": "Consider using spot instances for dev/staging "
                              if environment != "production"
                              else "Monitor usage for reserved instance opportunities"
        }
