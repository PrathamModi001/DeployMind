"""
Security Agent - AI-powered vulnerability analysis.

Uses CrewAI + Groq LLM to analyze Trivy scan results and make security decisions.
"""

from dataclasses import dataclass
from typing import Optional
from infrastructure.security.trivy_scanner import TrivyScanResult
from config.settings import settings
from shared.secure_logging import get_logger

# Optional CrewAI imports (for AI-powered analysis)
try:
    from crewai import Agent, Task, Crew
    from crewai_tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    Agent = None
    Task = None
    Crew = None
    tool = lambda name: lambda func: func  # Dummy decorator

# Optional Groq client (for AI-powered analysis)
try:
    from infrastructure.llm.groq.groq_client import GroqClient
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    GroqClient = None

logger = get_logger(__name__)


@dataclass
class SecurityDecision:
    """Security scan decision from AI agent."""

    decision: str  # "approve", "reject", "warn"
    reasoning: str
    critical_issues: list[str]
    recommendations: list[str]
    risk_score: int  # 0-100


class SecurityAgentService:
    """
    Security Agent - analyzes vulnerability scans and makes decisions.

    Uses AI (Groq LLM via CrewAI) to:
    - Analyze CVE severity and impact
    - Provide remediation recommendations
    - Make approve/reject decisions
    """

    def __init__(self):
        """Initialize Security Agent with Groq LLM."""
        if GROQ_AVAILABLE:
            self.groq_client = GroqClient(settings.groq_api_key)
        else:
            self.groq_client = None

        if CREWAI_AVAILABLE:
            self.agent = self._create_agent()
        else:
            self.agent = None
            logger.warning("CrewAI not available, using rule-based decisions only")

    def _create_agent(self) -> Agent:
        """Create CrewAI Security Agent with tools."""

        @tool("Analyze CVE Severity")
        def analyze_cve_severity(cve_data: str) -> str:
            """
            Analyze CVE severity and determine risk level.

            Args:
                cve_data: JSON string with CVE details

            Returns:
                Risk analysis with severity assessment
            """
            # This tool is called by the agent to analyze individual CVEs
            # The LLM will reason about the CVE and provide analysis
            return f"Analyzing CVE: {cve_data}"

        @tool("Generate Remediation")
        def generate_remediation(vulnerability: str) -> str:
            """
            Generate remediation steps for a vulnerability.

            Args:
                vulnerability: Description of vulnerability

            Returns:
                Step-by-step remediation guide
            """
            return f"Generating remediation for: {vulnerability}"

        # Create Security Agent
        agent = Agent(
            role="Security Specialist",
            goal="Analyze vulnerability scans and make security decisions to protect deployments",
            backstory=(
                "You are an expert security engineer with deep knowledge of CVEs, "
                "OWASP Top 10, and container security. You analyze vulnerability "
                "scans and make informed decisions about deployment safety. "
                "You prioritize security but also understand business needs."
            ),
            tools=[analyze_cve_severity, generate_remediation],
            verbose=False,
            allow_delegation=False,
            llm=self._get_llm_config()
        )

        return agent

    def _get_llm_config(self) -> dict:
        """Get LLM configuration for CrewAI."""
        # CrewAI expects a dict with model name and API configuration
        # For Groq, we use their OpenAI-compatible API
        return {
            "model": settings.default_llm,
            "api_key": settings.groq_api_key,
            "base_url": "https://api.groq.com/openai/v1"
        }

    def analyze_scan(
        self,
        scan_result: TrivyScanResult,
        policy: str = "strict"
    ) -> SecurityDecision:
        """
        Analyze Trivy scan results using AI agent.

        Args:
            scan_result: Trivy scan results
            policy: Security policy ("strict", "balanced", "permissive")

        Returns:
            SecurityDecision with AI analysis and recommendation

        Policy definitions:
        - strict: Block on CRITICAL, reject on HIGH
        - balanced: Block on CRITICAL, warn on HIGH
        - permissive: Block on CRITICAL only
        """
        logger.info(
            "Analyzing security scan",
            target=scan_result.target,
            total_vulns=scan_result.total_vulnerabilities,
            critical=scan_result.critical_count,
            high=scan_result.high_count,
            policy=policy
        )

        # Quick decision for no vulnerabilities
        if scan_result.total_vulnerabilities == 0:
            return SecurityDecision(
                decision="approve",
                reasoning="No vulnerabilities found in scan",
                critical_issues=[],
                recommendations=["Continue monitoring for new vulnerabilities"],
                risk_score=0
            )

        # Check if CrewAI is available
        if not CREWAI_AVAILABLE or self.agent is None:
            logger.info("Using rule-based decision (CrewAI not available)")
            return self._rule_based_decision(scan_result, policy)

        # Build context for AI analysis
        context = self._build_analysis_context(scan_result, policy)

        # Create analysis task for the agent
        task = Task(
            description=context,
            agent=self.agent,
            expected_output=(
                "A JSON object with:\n"
                "- decision: 'approve', 'reject', or 'warn'\n"
                "- reasoning: detailed explanation\n"
                "- critical_issues: list of critical problems\n"
                "- recommendations: list of remediation steps\n"
                "- risk_score: 0-100 integer"
            )
        )

        # Execute analysis with CrewAI
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=False
        )

        try:
            # Run AI analysis
            result = crew.kickoff()

            # Parse AI response
            decision = self._parse_ai_response(result, scan_result, policy)

            logger.info(
                "Security analysis complete",
                decision=decision.decision,
                risk_score=decision.risk_score,
                critical_issues_count=len(decision.critical_issues)
            )

            return decision

        except Exception as e:
            logger.error("AI analysis failed, falling back to rule-based", error=str(e))
            # Fallback to rule-based decision
            return self._rule_based_decision(scan_result, policy)

    def _build_analysis_context(
        self,
        scan_result: TrivyScanResult,
        policy: str
    ) -> str:
        """Build analysis context for AI agent."""

        # Get top 5 most severe vulnerabilities
        top_vulns = sorted(
            scan_result.vulnerabilities,
            key=lambda v: {
                "CRITICAL": 4,
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1,
                "UNKNOWN": 0
            }.get(v.severity, 0),
            reverse=True
        )[:5]

        vuln_details = "\n".join([
            f"- {v.cve_id} ({v.severity}): {v.package_name} "
            f"v{v.installed_version} → {v.fixed_version or 'no fix'}"
            for v in top_vulns
        ])

        context = f"""
Analyze this vulnerability scan and make a security decision:

Target: {scan_result.target}
Scan Type: {scan_result.scan_type}
Policy: {policy}

Vulnerability Summary:
- Total: {scan_result.total_vulnerabilities}
- CRITICAL: {scan_result.critical_count}
- HIGH: {scan_result.high_count}
- MEDIUM: {scan_result.medium_count}
- LOW: {scan_result.low_count}

Top Vulnerabilities:
{vuln_details}

Security Policy:
- strict: Block CRITICAL, reject HIGH
- balanced: Block CRITICAL, warn HIGH
- permissive: Block CRITICAL only

Task: Analyze these vulnerabilities and provide:
1. Decision (approve/reject/warn)
2. Detailed reasoning
3. List of critical issues
4. Remediation recommendations
5. Risk score (0-100)

Consider:
- Exploitability of vulnerabilities
- Availability of fixes
- Business impact
- Compensating controls
"""
        return context

    def _parse_ai_response(
        self,
        ai_result: str,
        scan_result: TrivyScanResult,
        policy: str
    ) -> SecurityDecision:
        """Parse AI agent response into SecurityDecision."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', str(ai_result), re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                return SecurityDecision(
                    decision=data.get("decision", "warn"),
                    reasoning=data.get("reasoning", "AI analysis completed"),
                    critical_issues=data.get("critical_issues", []),
                    recommendations=data.get("recommendations", []),
                    risk_score=int(data.get("risk_score", 50))
                )
        except Exception as e:
            logger.warning("Failed to parse AI response", error=str(e))

        # Fallback to rule-based if parsing fails
        return self._rule_based_decision(scan_result, policy)

    def _rule_based_decision(
        self,
        scan_result: TrivyScanResult,
        policy: str
    ) -> SecurityDecision:
        """
        Fallback rule-based decision (no AI).

        Simple rules:
        - CRITICAL vulnerabilities → reject
        - HIGH vulnerabilities → depends on policy
        - Otherwise → approve
        """
        critical_issues = []
        recommendations = []
        decision = "approve"
        risk_score = 0

        # Check CRITICAL
        if scan_result.critical_count > 0:
            decision = "reject"
            risk_score = 100
            critical_issues.append(
                f"{scan_result.critical_count} CRITICAL vulnerabilities found"
            )
            recommendations.append("Fix all CRITICAL vulnerabilities before deploying")

        # Check HIGH (based on policy)
        elif scan_result.high_count > 0:
            if policy == "strict":
                decision = "reject"
                risk_score = 75
            elif policy == "balanced":
                decision = "warn"
                risk_score = 60
            else:  # permissive
                decision = "approve"
                risk_score = 40

            critical_issues.append(
                f"{scan_result.high_count} HIGH vulnerabilities found"
            )
            recommendations.append("Review and fix HIGH vulnerabilities")

        # Check MEDIUM
        elif scan_result.medium_count > 0:
            decision = "approve"
            risk_score = 30
            recommendations.append("Monitor MEDIUM vulnerabilities")

        reasoning = f"Rule-based decision: {scan_result.severity_summary}"

        return SecurityDecision(
            decision=decision,
            reasoning=reasoning,
            critical_issues=critical_issues,
            recommendations=recommendations,
            risk_score=risk_score
        )
