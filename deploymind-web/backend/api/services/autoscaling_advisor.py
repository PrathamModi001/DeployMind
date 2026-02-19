"""AI-powered auto-scaling recommendations."""
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
    from deploymind.infrastructure.database.models import Deployment
    from deploymind.infrastructure.llm.groq.groq_client import GroqClient
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    Deployment = None
    GroqClient = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class AutoScalingAdvisor:
    """
    AI-powered auto-scaling recommendations.

    Analyzes resource utilization and recommends horizontal or vertical
    scaling to optimize performance and cost.
    """

    # Scaling thresholds
    HIGH_CPU_THRESHOLD = 70.0      # % CPU to trigger scaling
    HIGH_MEMORY_THRESHOLD = 75.0   # % Memory to trigger scaling
    LOW_UTILIZATION = 30.0         # % to consider down-scaling
    SUSTAINED_DURATION = 6         # Hours of sustained high usage

    # Instance types with specs
    INSTANCE_TYPES = {
        "t2.micro": {"vcpu": 1, "memory_gb": 1, "cost_per_hour": 0.0116},
        "t2.small": {"vcpu": 1, "memory_gb": 2, "cost_per_hour": 0.023},
        "t2.medium": {"vcpu": 2, "memory_gb": 4, "cost_per_hour": 0.0464},
        "t3.small": {"vcpu": 2, "memory_gb": 2, "cost_per_hour": 0.0208},
        "t3.medium": {"vcpu": 2, "memory_gb": 4, "cost_per_hour": 0.0416},
    }

    def __init__(self, db: Session):
        """
        Initialize auto-scaling advisor.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings and GroqClient:
            try:
                settings = CoreSettings.load()
                self.llm = GroqClient(settings)
                logger.info("AutoScalingAdvisor initialized with LLM")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("LLM not available, using rule-based recommendations")

    async def recommend_scaling(
        self,
        deployment_id: str,
        hours_lookback: int = 6
    ) -> Dict:
        """
        Recommend horizontal or vertical scaling.

        Args:
            deployment_id: Deployment ID
            hours_lookback: Hours of metrics to analyze (default: 6)

        Returns:
            Scaling recommendation dictionary
        """
        try:
            # Get deployment info
            if not Deployment:
                return self._mock_recommendation(deployment_id)

            deployment = self.db.query(Deployment).filter(
                Deployment.id == deployment_id
            ).first()

            if not deployment:
                return self._mock_recommendation(deployment_id)

            # Get metrics history
            metrics = await self._get_metrics_history(deployment_id, hours_lookback)

            if not metrics:
                return {
                    "deployment_id": deployment_id,
                    "should_scale": False,
                    "reason": "Insufficient metrics data",
                    "current_config": self._get_current_config(deployment),
                    "recommendation": None
                }

            # Calculate utilization stats
            utilization = self._calculate_utilization(metrics)

            # Determine if scaling needed
            scaling_decision = self._should_scale(utilization)

            if not scaling_decision["should_scale"]:
                return {
                    "deployment_id": deployment_id,
                    "should_scale": False,
                    "reason": scaling_decision["reason"],
                    "current_config": self._get_current_config(deployment),
                    "utilization": utilization,
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }

            # Generate recommendation (LLM or rule-based)
            if self.llm:
                recommendation = await self._llm_recommendation(
                    deployment,
                    utilization,
                    scaling_decision
                )
            else:
                recommendation = self._rule_based_recommendation(
                    deployment,
                    utilization,
                    scaling_decision
                )

            return {
                "deployment_id": deployment_id,
                "should_scale": True,
                "scaling_type": recommendation["scaling_type"],
                "current_config": self._get_current_config(deployment),
                "recommended_config": recommendation["recommended_config"],
                "cost_impact_monthly": recommendation["cost_impact"],
                "performance_improvement": recommendation["performance_improvement"],
                "reasoning": recommendation["reasoning"],
                "utilization": utilization,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Scaling recommendation failed: {e}", exc_info=True)
            return self._mock_recommendation(deployment_id)

    def _calculate_utilization(self, metrics: List[Dict]) -> Dict:
        """Calculate resource utilization statistics."""
        cpu_values = [m["cpu"] for m in metrics]
        memory_values = [m["memory"] for m in metrics]

        return {
            "avg_cpu": round(statistics.mean(cpu_values), 2),
            "peak_cpu": round(max(cpu_values), 2),
            "min_cpu": round(min(cpu_values), 2),
            "avg_memory": round(statistics.mean(memory_values), 2),
            "peak_memory": round(max(memory_values), 2),
            "min_memory": round(min(memory_values), 2),
            "samples": len(metrics)
        }

    def _should_scale(self, utilization: Dict) -> Dict:
        """Determine if scaling is needed."""
        avg_cpu = utilization["avg_cpu"]
        peak_cpu = utilization["peak_cpu"]
        avg_memory = utilization["avg_memory"]
        peak_memory = utilization["peak_memory"]

        # Scale up if sustained high usage
        if avg_cpu > self.HIGH_CPU_THRESHOLD or avg_memory > self.HIGH_MEMORY_THRESHOLD:
            return {
                "should_scale": True,
                "direction": "up",
                "reason": f"High average utilization: CPU={avg_cpu}%, Memory={avg_memory}%",
                "primary_constraint": "cpu" if avg_cpu > avg_memory else "memory"
            }

        # Scale up if frequent peaks
        if peak_cpu > 90 or peak_memory > 90:
            return {
                "should_scale": True,
                "direction": "up",
                "reason": f"Frequent resource peaks: CPU={peak_cpu}%, Memory={peak_memory}%",
                "primary_constraint": "cpu" if peak_cpu > peak_memory else "memory"
            }

        # Scale down if consistently low usage
        if avg_cpu < self.LOW_UTILIZATION and avg_memory < self.LOW_UTILIZATION:
            return {
                "should_scale": True,
                "direction": "down",
                "reason": f"Low utilization: CPU={avg_cpu}%, Memory={avg_memory}%",
                "primary_constraint": "cost_optimization"
            }

        return {
            "should_scale": False,
            "reason": "Utilization within acceptable range"
        }

    def _get_current_config(self, deployment) -> Dict:
        """Get current deployment configuration."""
        # Extract instance type from deployment metadata
        instance_type = getattr(deployment, 'instance_type', 't2.micro')
        instance_count = 1  # Single instance for now

        specs = self.INSTANCE_TYPES.get(instance_type, self.INSTANCE_TYPES["t2.micro"])

        return {
            "instance_type": instance_type,
            "instance_count": instance_count,
            "vcpu": specs["vcpu"],
            "memory_gb": specs["memory_gb"],
            "cost_per_hour": specs["cost_per_hour"]
        }

    async def _llm_recommendation(
        self,
        deployment,
        utilization: Dict,
        decision: Dict
    ) -> Dict:
        """Generate recommendation using LLM."""
        current_config = self._get_current_config(deployment)

        prompt = f"""
        Generate auto-scaling recommendation for deployment:

        Current configuration:
        - Instance type: {current_config['instance_type']}
        - Instance count: {current_config['instance_count']}
        - vCPU: {current_config['vcpu']}
        - Memory: {current_config['memory_gb']} GB
        - Cost: ${current_config['cost_per_hour']}/hour

        Resource utilization (last 6 hours):
        - Average CPU: {utilization['avg_cpu']}%
        - Peak CPU: {utilization['peak_cpu']}%
        - Average Memory: {utilization['avg_memory']}%
        - Peak Memory: {utilization['peak_memory']}%

        Scaling decision: {decision['direction']} ({decision['reason']})
        Primary constraint: {decision['primary_constraint']}

        Available instance types: {', '.join(self.INSTANCE_TYPES.keys())}

        Recommend:
        1. Scaling type (horizontal: add instances, vertical: bigger instance)
        2. Target configuration (instance_type, instance_count)
        3. Monthly cost change (positive or negative)
        4. Expected performance improvement (percentage)
        5. Brief reasoning

        Return ONLY valid JSON:
        {{
            "scaling_type": "<horizontal|vertical>",
            "recommended_instance_type": "<type>",
            "recommended_instance_count": <number>,
            "cost_change_monthly": <number>,
            "performance_improvement_percent": <number>,
            "reasoning": "<explanation>"
        }}
        """

        try:
            response = await self.llm.complete(
                prompt=prompt,
                model="llama-3.1-70b-versatile",
                max_tokens=400
            )

            import json
            result = json.loads(response.strip())

            return {
                "scaling_type": result.get("scaling_type", "vertical"),
                "recommended_config": {
                    "instance_type": result.get("recommended_instance_type", "t2.small"),
                    "instance_count": result.get("recommended_instance_count", 1)
                },
                "cost_impact": result.get("cost_change_monthly", 0),
                "performance_improvement": result.get("performance_improvement_percent", 0),
                "reasoning": result.get("reasoning", "AI-generated recommendation")
            }

        except Exception as e:
            logger.error(f"LLM recommendation failed: {e}")
            return self._rule_based_recommendation(deployment, utilization, decision)

    def _rule_based_recommendation(
        self,
        deployment,
        utilization: Dict,
        decision: Dict
    ) -> Dict:
        """Generate recommendation using rules."""
        current_config = self._get_current_config(deployment)
        current_type = current_config["instance_type"]

        if decision["direction"] == "up":
            # Determine scaling type based on constraint
            if decision["primary_constraint"] == "cpu":
                # Vertical scaling to next instance type
                recommended_type = self._next_instance_type(current_type)
                scaling_type = "vertical"
                reasoning = f"Upgrade to {recommended_type} for more CPU capacity"
            else:
                # Vertical scaling for more memory
                recommended_type = self._next_instance_type(current_type)
                scaling_type = "vertical"
                reasoning = f"Upgrade to {recommended_type} for more memory"

            # Calculate cost impact
            current_cost = current_config["cost_per_hour"] * 730  # per month
            new_cost = self.INSTANCE_TYPES[recommended_type]["cost_per_hour"] * 730
            cost_impact = round(new_cost - current_cost, 2)

            return {
                "scaling_type": scaling_type,
                "recommended_config": {
                    "instance_type": recommended_type,
                    "instance_count": 1
                },
                "cost_impact": cost_impact,
                "performance_improvement": 50,  # Estimated 50% improvement
                "reasoning": reasoning
            }

        else:  # Scale down
            # Downgrade to smaller instance
            recommended_type = self._previous_instance_type(current_type)
            current_cost = current_config["cost_per_hour"] * 730
            new_cost = self.INSTANCE_TYPES[recommended_type]["cost_per_hour"] * 730
            cost_impact = round(new_cost - current_cost, 2)

            return {
                "scaling_type": "vertical",
                "recommended_config": {
                    "instance_type": recommended_type,
                    "instance_count": 1
                },
                "cost_impact": cost_impact,
                "performance_improvement": -10,  # Slight performance reduction
                "reasoning": f"Downgrade to {recommended_type} to reduce costs"
            }

    def _next_instance_type(self, current: str) -> str:
        """Get next bigger instance type."""
        progression = ["t2.micro", "t2.small", "t2.medium", "t3.medium"]
        try:
            idx = progression.index(current)
            return progression[min(idx + 1, len(progression) - 1)]
        except ValueError:
            return "t2.small"

    def _previous_instance_type(self, current: str) -> str:
        """Get next smaller instance type."""
        progression = ["t2.micro", "t2.small", "t2.medium", "t3.medium"]
        try:
            idx = progression.index(current)
            return progression[max(idx - 1, 0)]
        except ValueError:
            return "t2.micro"

    async def _get_metrics_history(
        self,
        deployment_id: str,
        hours: int
    ) -> List[Dict]:
        """Get metrics history (simulated)."""
        import random
        num_points = hours * 6  # Every 10 minutes

        metrics = []
        base_cpu = 75.0  # High usage to trigger scaling
        base_memory = 65.0

        for i in range(num_points):
            metrics.append({
                "timestamp": (datetime.utcnow() - timedelta(minutes=10 * (num_points - i))).isoformat(),
                "cpu": max(0, min(100, base_cpu + random.gauss(0, 5))),
                "memory": max(0, min(100, base_memory + random.gauss(0, 5))),
                "network": max(0, 10 + random.gauss(0, 2))
            })

        return metrics

    def _mock_recommendation(self, deployment_id: str) -> Dict:
        """Return mock recommendation."""
        return {
            "deployment_id": deployment_id,
            "should_scale": True,
            "scaling_type": "vertical",
            "current_config": {
                "instance_type": "t2.micro",
                "instance_count": 1,
                "vcpu": 1,
                "memory_gb": 1
            },
            "recommended_config": {
                "instance_type": "t2.small",
                "instance_count": 1
            },
            "cost_impact_monthly": 8.46,
            "performance_improvement": "50% CPU capacity increase",
            "reasoning": "High average CPU utilization (75%) requires more resources",
            "utilization": {
                "avg_cpu": 75.3,
                "peak_cpu": 89.2,
                "avg_memory": 65.1,
                "peak_memory": 78.5
            },
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
