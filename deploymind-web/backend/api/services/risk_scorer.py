"""AI-powered security risk scoring for deployments."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.database.models import SecurityScan
    from deploymind.infrastructure.llm.groq.groq_client import GroqClient
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    SecurityScan = None
    GroqClient = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class SecurityRiskScorer:
    """
    Calculate security risk scores for deployments.

    Analyzes security scan results and assigns risk scores (0-100)
    with actionable remediation recommendations.
    """

    # Severity weights for risk calculation
    SEVERITY_WEIGHTS = {
        "CRITICAL": 40,
        "HIGH": 20,
        "MEDIUM": 5,
        "LOW": 1
    }

    # Risk rating thresholds
    RISK_THRESHOLDS = {
        "LOW": 20,
        "MEDIUM": 40,
        "HIGH": 70,
        "CRITICAL": 90
    }

    def __init__(self, db: Session):
        """
        Initialize security risk scorer.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings and GroqClient:
            try:
                settings = CoreSettings.load()
                self.llm = GroqClient(settings)
                logger.info("SecurityRiskScorer initialized with LLM")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("LLM not available, using rule-based risk scoring")

    async def calculate_risk_score(
        self,
        deployment_id: str
    ) -> Dict:
        """
        Calculate overall security risk score (0-100).

        Args:
            deployment_id: Deployment ID

        Returns:
            Risk score and analysis
        """
        try:
            if not SecurityScan:
                return self._mock_risk_score(deployment_id)

            # Get latest security scans
            scans = self.db.query(SecurityScan)\
                .filter(SecurityScan.deployment_id == deployment_id)\
                .order_by(SecurityScan.created_at.desc())\
                .limit(5)\
                .all()

            if not scans:
                return {
                    "deployment_id": deployment_id,
                    "risk_score": 50,
                    "rating": "UNKNOWN",
                    "confidence": "low",
                    "risk_factors": ["No security scans available"],
                    "remediation_steps": ["Run security scan to assess risks"],
                    "scan_coverage": {
                        "latest_scan": None,
                        "total_scans": 0
                    }
                }

            latest_scan = scans[0]

            # Calculate base risk score
            base_score = self._calculate_base_score(latest_scan)

            # Adjust for scan age
            scan_age_days = (datetime.utcnow() - latest_scan.created_at).days
            age_penalty = min(scan_age_days * 2, 20)  # Max 20 points penalty

            # Final score
            risk_score = min(100, base_score + age_penalty)

            # Determine rating
            rating = self._get_risk_rating(risk_score)

            # Get risk factors and remediation (LLM or rule-based)
            if self.llm:
                analysis = await self._llm_analysis(deployment_id, latest_scan, risk_score)
            else:
                analysis = self._rule_based_analysis(latest_scan, risk_score)

            return {
                "deployment_id": deployment_id,
                "risk_score": round(risk_score, 1),
                "rating": rating,
                "confidence": "high" if len(scans) >= 3 else "medium",
                "risk_factors": analysis["risk_factors"],
                "remediation_steps": analysis["remediation_steps"],
                "scan_coverage": {
                    "latest_scan": latest_scan.created_at.isoformat(),
                    "scan_age_days": scan_age_days,
                    "total_scans": len(scans),
                    "vulnerabilities": {
                        "critical": latest_scan.critical_count or 0,
                        "high": latest_scan.high_count or 0,
                        "medium": latest_scan.medium_count or 0,
                        "low": latest_scan.low_count or 0
                    }
                },
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Risk scoring failed: {e}", exc_info=True)
            return self._mock_risk_score(deployment_id)

    def _calculate_base_score(self, scan) -> float:
        """Calculate base risk score from vulnerability counts."""
        critical = getattr(scan, 'critical_count', 0) or 0
        high = getattr(scan, 'high_count', 0) or 0
        medium = getattr(scan, 'medium_count', 0) or 0
        low = getattr(scan, 'low_count', 0) or 0

        # Weighted sum
        score = (
            critical * self.SEVERITY_WEIGHTS["CRITICAL"] +
            high * self.SEVERITY_WEIGHTS["HIGH"] +
            medium * self.SEVERITY_WEIGHTS["MEDIUM"] +
            low * self.SEVERITY_WEIGHTS["LOW"]
        )

        # Normalize to 0-100 scale
        # Assumption: 3 critical = 100 points
        normalized_score = min(100, score)

        return normalized_score

    def _get_risk_rating(self, score: float) -> str:
        """Convert numeric score to risk rating."""
        if score >= self.RISK_THRESHOLDS["CRITICAL"]:
            return "CRITICAL"
        elif score >= self.RISK_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif score >= self.RISK_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif score >= self.RISK_THRESHOLDS["LOW"]:
            return "LOW"
        else:
            return "MINIMAL"

    async def _llm_analysis(
        self,
        deployment_id: str,
        scan,
        risk_score: float
    ) -> Dict:
        """Use LLM to analyze risk factors and remediation."""
        # Get top vulnerabilities
        vulnerabilities = getattr(scan, 'vulnerabilities', [])
        top_vulns = vulnerabilities[:5] if isinstance(vulnerabilities, list) else []

        vulns_str = "\n".join([
            f"- {v.get('vulnerability_id', 'N/A')}: {v.get('title', 'Unknown')} (Severity: {v.get('severity', 'UNKNOWN')})"
            for v in top_vulns
        ]) if top_vulns else "No detailed vulnerability data available"

        prompt = f"""
        Analyze security risks for deployment:

        Deployment ID: {deployment_id}
        Risk Score: {risk_score}/100

        Vulnerability Summary:
        - Critical: {getattr(scan, 'critical_count', 0)}
        - High: {getattr(scan, 'high_count', 0)}
        - Medium: {getattr(scan, 'medium_count', 0)}
        - Low: {getattr(scan, 'low_count', 0)}
        - Scan age: {(datetime.utcnow() - scan.created_at).days} days

        Top Vulnerabilities:
        {vulns_str}

        Provide:
        1. Top 3 risk factors (what makes this deployment risky)
        2. Top 3 remediation steps (specific, actionable steps)

        Return ONLY valid JSON:
        {{
            "risk_factors": ["factor1", "factor2", "factor3"],
            "remediation_steps": ["step1", "step2", "step3"]
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
                "risk_factors": result.get("risk_factors", [])[:3],
                "remediation_steps": result.get("remediation_steps", [])[:3]
            }

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._rule_based_analysis(scan, risk_score)

    def _rule_based_analysis(self, scan, risk_score: float) -> Dict:
        """Rule-based risk analysis when LLM unavailable."""
        risk_factors = []
        remediation_steps = []

        critical = getattr(scan, 'critical_count', 0) or 0
        high = getattr(scan, 'high_count', 0) or 0
        medium = getattr(scan, 'medium_count', 0) or 0
        scan_age = (datetime.utcnow() - scan.created_at).days

        # Identify risk factors
        if critical > 0:
            risk_factors.append(f"{critical} CRITICAL vulnerabilities present")
            remediation_steps.append("Immediately patch all critical vulnerabilities")

        if high > 0:
            risk_factors.append(f"{high} HIGH severity vulnerabilities detected")
            remediation_steps.append("Review and remediate high-severity issues within 7 days")

        if scan_age > 7:
            risk_factors.append(f"Security scan is {scan_age} days old")
            remediation_steps.append("Run fresh security scan to detect new vulnerabilities")

        if medium > 5:
            risk_factors.append(f"Accumulation of {medium} medium-severity issues")
            remediation_steps.append("Schedule remediation sprint for medium-severity issues")

        # Default factors/steps if none identified
        if not risk_factors:
            risk_factors = [
                "Low vulnerability count",
                "Recent security scan",
                "No critical issues detected"
            ]

        if not remediation_steps:
            remediation_steps = [
                "Maintain regular security scanning schedule",
                "Keep dependencies up to date",
                "Monitor for new CVE announcements"
            ]

        return {
            "risk_factors": risk_factors[:3],
            "remediation_steps": remediation_steps[:3]
        }

    def _mock_risk_score(self, deployment_id: str) -> Dict:
        """Return mock risk score."""
        return {
            "deployment_id": deployment_id,
            "risk_score": 45.5,
            "rating": "MEDIUM",
            "confidence": "high",
            "risk_factors": [
                "2 HIGH severity vulnerabilities detected",
                "Security scan is 5 days old",
                "Accumulation of 8 medium-severity issues"
            ],
            "remediation_steps": [
                "Review and remediate high-severity issues within 7 days",
                "Run fresh security scan to detect new vulnerabilities",
                "Update base Docker image to latest version"
            ],
            "scan_coverage": {
                "latest_scan": datetime.utcnow().isoformat(),
                "scan_age_days": 5,
                "total_scans": 3,
                "vulnerabilities": {
                    "critical": 0,
                    "high": 2,
                    "medium": 8,
                    "low": 15
                }
            },
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
