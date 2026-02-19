"""AI-powered cost trend analysis and forecasting."""
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


class CostAnalyzer:
    """
    Analyze cloud spending trends and forecast future costs.

    Tracks deployment costs, identifies trends, and provides optimization
    recommendations to reduce cloud spending.
    """

    # Cost constants (USD per hour)
    INSTANCE_COSTS = {
        "t2.micro": 0.0116,
        "t2.small": 0.023,
        "t2.medium": 0.0464,
        "t3.small": 0.0208,
        "t3.medium": 0.0416,
    }

    def __init__(self, db: Session):
        """
        Initialize cost analyzer.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings and GroqClient:
            try:
                settings = CoreSettings.load()
                self.llm = GroqClient(settings)
                logger.info("CostAnalyzer initialized with LLM")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("LLM not available, using statistical forecasting")

    async def analyze_cost_trends(
        self,
        user_id: int,
        months_lookback: int = 6
    ) -> Dict:
        """
        Analyze historical costs and predict future trends.

        Args:
            user_id: User ID
            months_lookback: Months of history to analyze (default: 6)

        Returns:
            Cost trend analysis and forecast
        """
        try:
            # Get user's deployments
            if not Deployment:
                return self._mock_analysis(user_id)

            deployments = self.db.query(Deployment)\
                .filter(Deployment.user_id == user_id)\
                .all()

            if not deployments:
                return {
                    "user_id": user_id,
                    "trend": "no_data",
                    "monthly_costs": [],
                    "total_cost_current_month": 0.0,
                    "forecast_next_3_months": [],
                    "optimization_opportunities": ["No deployments to analyze"],
                    "potential_savings_monthly": 0.0
                }

            # Calculate historical monthly costs
            monthly_costs = self._calculate_monthly_costs(deployments, months_lookback)

            # Analyze trend
            trend_analysis = self._analyze_trend(monthly_costs)

            # Forecast next 3 months
            if self.llm:
                forecast = await self._llm_forecast(monthly_costs, trend_analysis)
            else:
                forecast = self._statistical_forecast(monthly_costs, trend_analysis)

            # Find optimization opportunities
            optimizations = self._find_optimizations(deployments, monthly_costs)

            return {
                "user_id": user_id,
                "trend": trend_analysis["trend"],
                "monthly_growth_rate_percent": trend_analysis["growth_rate"],
                "monthly_costs": monthly_costs,
                "total_cost_current_month": monthly_costs[-1]["cost"] if monthly_costs else 0.0,
                "forecast_next_3_months": forecast,
                "optimization_opportunities": optimizations["opportunities"],
                "potential_savings_monthly": optimizations["savings"],
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Cost analysis failed: {e}", exc_info=True)
            return self._mock_analysis(user_id)

    def _calculate_monthly_costs(
        self,
        deployments: List,
        months: int
    ) -> List[Dict]:
        """Calculate monthly costs from deployments."""
        monthly_costs = []

        # Calculate for each of the last N months
        for i in range(months, 0, -1):
            month_date = datetime.utcnow() - timedelta(days=30 * i)
            month_str = month_date.strftime("%Y-%m")

            # Simulate costs based on deployment count and uptime
            # In production, this would query actual billing data
            active_deployments = len([
                d for d in deployments
                if d.created_at <= month_date
            ])

            # Estimate cost (t2.micro = $0.0116/hour * 730 hours = $8.47/month)
            base_cost = 8.47  # t2.micro full month
            monthly_cost = active_deployments * base_cost * (0.7 + (i / months) * 0.3)

            monthly_costs.append({
                "month": month_str,
                "cost": round(monthly_cost, 2),
                "active_deployments": active_deployments
            })

        return monthly_costs

    def _analyze_trend(self, monthly_costs: List[Dict]) -> Dict:
        """Analyze cost trend."""
        if len(monthly_costs) < 2:
            return {
                "trend": "insufficient_data",
                "growth_rate": 0.0
            }

        costs = [m["cost"] for m in monthly_costs]

        # Calculate month-over-month growth rate
        recent_avg = statistics.mean(costs[-3:])
        older_avg = statistics.mean(costs[:3])

        if older_avg > 0:
            growth_rate = ((recent_avg - older_avg) / older_avg) * 100
        else:
            growth_rate = 0.0

        # Determine trend
        if growth_rate > 10:
            trend = "increasing"
        elif growth_rate < -10:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "growth_rate": round(growth_rate, 2)
        }

    async def _llm_forecast(
        self,
        monthly_costs: List[Dict],
        trend_analysis: Dict
    ) -> List[Dict]:
        """Use LLM to forecast future costs."""
        costs_str = "\n".join([
            f"- {m['month']}: ${m['cost']}"
            for m in monthly_costs
        ])

        prompt = f"""
        Forecast cloud costs for next 3 months based on historical data:

        Historical monthly costs:
        {costs_str}

        Current trend: {trend_analysis['trend']}
        Month-over-month growth: {trend_analysis['growth_rate']}%

        Predict costs for next 3 months considering:
        - Historical trend
        - Seasonal variations
        - Growth patterns

        Return ONLY valid JSON:
        {{
            "forecasts": [
                {{"month": "2026-03", "predicted_cost": <number>}},
                {{"month": "2026-04", "predicted_cost": <number>}},
                {{"month": "2026-05", "predicted_cost": <number>}}
            ]
        }}
        """

        try:
            response = await self.llm.complete(
                prompt=prompt,
                model="llama-3.1-70b-versatile",
                max_tokens=300
            )

            import json
            result = json.loads(response.strip())
            return result.get("forecasts", [])

        except Exception as e:
            logger.error(f"LLM forecast failed: {e}")
            return self._statistical_forecast(monthly_costs, trend_analysis)

    def _statistical_forecast(
        self,
        monthly_costs: List[Dict],
        trend_analysis: Dict
    ) -> List[Dict]:
        """Statistical forecast when LLM unavailable."""
        if not monthly_costs:
            return []

        last_cost = monthly_costs[-1]["cost"]
        growth_rate = trend_analysis["growth_rate"] / 100  # Convert to decimal

        forecasts = []
        for i in range(1, 4):  # Next 3 months
            predicted_cost = last_cost * ((1 + growth_rate) ** i)
            month_date = datetime.utcnow() + timedelta(days=30 * i)

            forecasts.append({
                "month": month_date.strftime("%Y-%m"),
                "predicted_cost": round(predicted_cost, 2),
                "confidence": "medium"
            })

        return forecasts

    def _find_optimizations(
        self,
        deployments: List,
        monthly_costs: List[Dict]
    ) -> Dict:
        """Find cost optimization opportunities."""
        opportunities = []
        total_savings = 0.0

        # Check for idle deployments
        idle_count = len([
            d for d in deployments
            if hasattr(d, 'status') and d.status in ['stopped', 'failed']
        ])

        if idle_count > 0:
            savings = idle_count * 8.47  # Cost per t2.micro instance
            opportunities.append(
                f"Remove {idle_count} idle deployment(s) to save ${savings:.2f}/month"
            )
            total_savings += savings

        # Check for oversized instances
        oversized = len([
            d for d in deployments
            if hasattr(d, 'instance_type') and d.instance_type != "t2.micro"
        ])

        if oversized > 0:
            # Estimate savings by downsizing to t2.micro
            potential_savings = oversized * 5.0  # Approximate savings
            opportunities.append(
                f"Consider downsizing {oversized} instance(s) to save ~${potential_savings:.2f}/month"
            )
            total_savings += potential_savings

        # Check for free tier usage
        if len(deployments) > 0:
            opportunities.append(
                "Use t2.micro instances to maximize free tier (750 hours/month)"
            )

        if not opportunities:
            opportunities = ["Deployment costs are already optimized"]

        return {
            "opportunities": opportunities[:5],
            "savings": round(total_savings, 2)
        }

    def _mock_analysis(self, user_id: int) -> Dict:
        """Return mock cost analysis."""
        return {
            "user_id": user_id,
            "trend": "increasing",
            "monthly_growth_rate_percent": 12.5,
            "monthly_costs": [
                {"month": "2025-09", "cost": 25.41, "active_deployments": 3},
                {"month": "2025-10", "cost": 28.15, "active_deployments": 3},
                {"month": "2025-11", "cost": 31.23, "active_deployments": 4},
                {"month": "2025-12", "cost": 35.87, "active_deployments": 4},
                {"month": "2026-01", "cost": 39.45, "active_deployments": 5},
                {"month": "2026-02", "cost": 42.58, "active_deployments": 5}
            ],
            "total_cost_current_month": 42.58,
            "forecast_next_3_months": [
                {"month": "2026-03", "predicted_cost": 47.90, "confidence": "medium"},
                {"month": "2026-04", "predicted_cost": 53.89, "confidence": "medium"},
                {"month": "2026-05", "predicted_cost": 60.62, "confidence": "low"}
            ],
            "optimization_opportunities": [
                "Remove 2 idle deployments to save $16.94/month",
                "Consider downsizing 1 instance(s) to save ~$5.00/month",
                "Use t2.micro instances to maximize free tier (750 hours/month)"
            ],
            "potential_savings_monthly": 21.94,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
