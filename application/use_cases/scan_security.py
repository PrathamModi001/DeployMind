"""Security scan use case.

Application layer orchestration for security scanning workflow.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings
from config.logging import get_logger
from infrastructure.security.trivy_scanner import TrivyScanner, TrivyScanResult
from agents.security.security_agent import SecurityAgentService, SecurityDecision
from domain.repositories.deployment_repository import DeploymentRepository

logger = get_logger(__name__)


@dataclass
class SecurityScanRequest:
    """Request to perform security scan."""

    deployment_id: str
    target: str  # Docker image name or filesystem path
    scan_type: str = "image"  # "image" or "filesystem"
    policy: str = "strict"  # "strict", "balanced", or "permissive"


@dataclass
class SecurityScanResponse:
    """Response from security scan operation."""

    deployment_id: str
    scan_result: TrivyScanResult
    decision: SecurityDecision
    success: bool
    message: str


class SecurityScanUseCase:
    """Use case for performing security scans with AI analysis.

    Orchestrates:
    1. Trivy vulnerability scanning
    2. AI-powered decision making
    3. Deployment status updates
    4. Audit trail logging
    """

    def __init__(
        self,
        settings: Settings,
        deployment_repository: DeploymentRepository | None = None
    ):
        """Initialize security scan use case.

        Args:
            settings: Application settings
            deployment_repository: Optional repository for persisting scan results
        """
        self.settings = settings
        self.deployment_repository = deployment_repository
        self.trivy_scanner = TrivyScanner()
        self.security_agent = SecurityAgentService()

    def execute(self, request: SecurityScanRequest) -> SecurityScanResponse:
        """Execute security scan workflow.

        Args:
            request: Security scan request with target and policy

        Returns:
            SecurityScanResponse with scan results and AI decision
        """
        logger.info(
            "Starting security scan",
            extra={
                "deployment_id": request.deployment_id,
                "target": request.target,
                "scan_type": request.scan_type,
                "policy": request.policy
            }
        )

        try:
            # Step 1: Run Trivy scan
            if request.scan_type == "image":
                scan_result = self.trivy_scanner.scan_image(request.target)
            elif request.scan_type == "filesystem":
                scan_result = self.trivy_scanner.scan_filesystem(request.target)
            else:
                raise ValueError(f"Invalid scan_type: {request.scan_type}")

            logger.info(
                "Trivy scan completed",
                extra={
                    "deployment_id": request.deployment_id,
                    "total_vulns": scan_result.total_vulnerabilities,
                    "critical": scan_result.critical_count,
                    "high": scan_result.high_count
                }
            )

            # Step 2: AI-powered decision making
            decision = self.security_agent.analyze_scan(
                scan_result=scan_result,
                policy=request.policy
            )

            logger.info(
                "Security decision made",
                extra={
                    "deployment_id": request.deployment_id,
                    "decision": decision.decision,
                    "risk_score": decision.risk_score
                }
            )

            # Step 3: Persist results (if repository available)
            if self.deployment_repository:
                try:
                    self._save_scan_results(
                        request.deployment_id,
                        scan_result,
                        decision
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to persist scan results",
                        extra={
                            "deployment_id": request.deployment_id,
                            "error": str(e)
                        }
                    )

            # Step 4: Build response
            success = decision.decision == "approve"
            message = self._build_message(decision)

            return SecurityScanResponse(
                deployment_id=request.deployment_id,
                scan_result=scan_result,
                decision=decision,
                success=success,
                message=message
            )

        except Exception as e:
            logger.error(
                "Security scan failed",
                extra={
                    "deployment_id": request.deployment_id,
                    "error": str(e)
                },
                exc_info=True
            )

            # Return failure response
            return SecurityScanResponse(
                deployment_id=request.deployment_id,
                scan_result=None,  # type: ignore
                decision=SecurityDecision(
                    decision="reject",
                    reasoning=f"Scan failed: {str(e)}",
                    critical_issues=[str(e)],
                    recommendations=["Fix scanning infrastructure", "Check Trivy installation"],
                    risk_score=100
                ),
                success=False,
                message=f"Security scan failed: {str(e)}"
            )

    def _save_scan_results(
        self,
        deployment_id: str,
        scan_result: TrivyScanResult,
        decision: SecurityDecision
    ) -> None:
        """Save scan results to database.

        Args:
            deployment_id: Deployment identifier
            scan_result: Trivy scan results
            decision: Security decision from AI
        """
        if not self.deployment_repository:
            return

        # Note: This assumes deployment exists in database
        # In production, you'd create SecurityScan entity and persist it
        logger.debug(
            "Saving scan results",
            deployment_id=deployment_id,
            decision=decision.decision
        )

        # TODO: Implement proper entity creation and persistence
        # For now, just log that we would save
        logger.debug(
            "Would save scan results to database",
            extra={"deployment_id": deployment_id}
        )

    def _build_message(self, decision: SecurityDecision) -> str:
        """Build human-readable message from decision.

        Args:
            decision: Security decision from AI

        Returns:
            Formatted message string
        """
        if decision.decision == "approve":
            return (
                f"[PASS] Security scan passed (risk score: {decision.risk_score}/100). "
                f"Reasoning: {decision.reasoning}"
            )
        elif decision.decision == "warn":
            issues = ", ".join(decision.critical_issues[:3])
            return (
                f"[WARN] Security scan passed with warnings (risk score: {decision.risk_score}/100). "
                f"Issues: {issues}. {decision.reasoning}"
            )
        else:  # reject
            issues = ", ".join(decision.critical_issues[:3])
            return (
                f"[REJECT] Security scan rejected (risk score: {decision.risk_score}/100). "
                f"Critical issues: {issues}. {decision.reasoning}"
            )
