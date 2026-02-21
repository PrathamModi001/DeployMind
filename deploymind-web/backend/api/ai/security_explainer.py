"""AI-powered security vulnerability explainer."""
import json
import logging
from typing import Dict
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

logger = logging.getLogger(__name__)


class SecurityExplainer:
    """Natural language explanations of security vulnerabilities."""

    def __init__(self):
        """Initialize explainer with Groq client."""
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

    async def explain_vulnerability(
        self,
        cve_id: str,
        package: str,
        severity: str,
        description: str = "",
    ) -> Dict:
        """
        Explain security vulnerability in simple terms.

        Args:
            cve_id: CVE identifier
            package: Affected package name
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            description: Vulnerability description

        Returns:
            Explanation with remediation steps
        """
        if not self.llm_available:
            return self._mock_vulnerability_explanation(cve_id, package, severity)

        prompt = f"""Explain this security vulnerability in simple terms:

CVE ID: {cve_id}
Package: {package}
Severity: {severity}
Description: {description or 'Not provided'}

Provide:
1. Simple explanation (ELI5 style) - what the vulnerability is
2. Why it matters - potential impact
3. How to fix it - specific actionable steps
4. Urgency level with timeline

Return ONLY a JSON object:
{{
    "simple_explanation": "explain like I'm 5",
    "impact": "what could happen if exploited",
    "fix_steps": ["step 1", "step 2", "step 3"],
    "urgency": "low|medium|high|critical",
    "recommended_timeline": "when to fix by"
}}"""

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response)

        except Exception as e:
            logger.error(f"Vulnerability explanation failed: {e}")
            return self._mock_vulnerability_explanation(cve_id, package, severity)

    def _mock_vulnerability_explanation(
        self,
        cve_id: str,
        package: str,
        severity: str
    ) -> Dict:
        """Fallback vulnerability explanation."""
        severity_info = {
            "CRITICAL": {
                "urgency": "critical",
                "timeline": "Fix immediately (within 24 hours)",
                "impact": "Could allow attackers to completely compromise your system"
            },
            "HIGH": {
                "urgency": "high",
                "timeline": "Fix within 1 week",
                "impact": "Could allow attackers to access sensitive data or disrupt service"
            },
            "MEDIUM": {
                "urgency": "medium",
                "timeline": "Fix within 1 month",
                "impact": "Could allow limited unauthorized access or information disclosure"
            },
            "LOW": {
                "urgency": "low",
                "timeline": "Fix in next maintenance cycle",
                "impact": "Minor security concern with low exploitation risk"
            }
        }

        info = severity_info.get(severity, severity_info["MEDIUM"])

        return {
            "simple_explanation": f"The package '{package}' has a security issue ({cve_id}) "
                                f"that could be exploited by attackers. This is a {severity} "
                                "severity vulnerability that needs attention.",
            "impact": info["impact"],
            "fix_steps": [
                f"Update {package} to the latest patched version",
                "Run security scan again to verify fix",
                "Test application to ensure update doesn't break functionality",
                "Deploy updated version to production"
            ],
            "urgency": info["urgency"],
            "recommended_timeline": info["timeline"]
        }
