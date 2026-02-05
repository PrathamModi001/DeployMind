"""Tests for Security Agent."""

import pytest
from unittest.mock import Mock, patch
from agents.security.security_agent import SecurityAgentService, SecurityDecision
from infrastructure.security.trivy_scanner import TrivyScanResult, Vulnerability


@pytest.fixture
def security_agent():
    """Create SecurityAgentService instance."""
    with patch('agents.security.security_agent.GroqClient'):
        agent = SecurityAgentService()
        return agent


@pytest.fixture
def clean_scan():
    """Scan with no vulnerabilities."""
    return TrivyScanResult(
        scan_type="image",
        target="alpine:latest",
        total_vulnerabilities=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        vulnerabilities=[]
    )


@pytest.fixture
def critical_scan():
    """Scan with critical vulnerabilities."""
    vulns = [
        Vulnerability(
            cve_id="CVE-2024-1234",
            severity="CRITICAL",
            package_name="openssl",
            installed_version="1.1.1",
            fixed_version="1.1.2",
            title="Critical vulnerability",
            description="Buffer overflow"
        )
    ]
    return TrivyScanResult(
        scan_type="image",
        target="python:3.11",
        total_vulnerabilities=1,
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
        vulnerabilities=vulns
    )


@pytest.fixture
def high_scan():
    """Scan with high vulnerabilities."""
    vulns = [
        Vulnerability(
            cve_id="CVE-2024-5678",
            severity="HIGH",
            package_name="curl",
            installed_version="7.68.0",
            fixed_version="7.70.0",
            title="High vulnerability",
            description="Memory leak"
        )
    ]
    return TrivyScanResult(
        scan_type="image",
        target="ubuntu:22.04",
        total_vulnerabilities=1,
        critical_count=0,
        high_count=1,
        medium_count=0,
        low_count=0,
        vulnerabilities=vulns
    )


@pytest.fixture
def medium_scan():
    """Scan with only medium vulnerabilities."""
    vulns = [
        Vulnerability(
            cve_id="CVE-2024-9012",
            severity="MEDIUM",
            package_name="libxml2",
            installed_version="2.9.10",
            fixed_version=None,
            title="Medium vulnerability",
            description="XML parsing issue"
        )
    ]
    return TrivyScanResult(
        scan_type="image",
        target="node:18",
        total_vulnerabilities=1,
        critical_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
        vulnerabilities=vulns
    )


class TestSecurityAgentRuleBasedDecisions:
    """Test rule-based decision making (no AI)."""

    def test_clean_scan_approved(self, security_agent, clean_scan):
        """Test that clean scans are approved."""
        decision = security_agent._rule_based_decision(clean_scan, "strict")

        assert decision.decision == "approve"
        assert decision.risk_score == 0
        assert len(decision.critical_issues) == 0

    def test_critical_vulnerabilities_rejected(self, security_agent, critical_scan):
        """Test that critical vulnerabilities are always rejected."""
        # Test all policies - should always reject
        for policy in ["strict", "balanced", "permissive"]:
            decision = security_agent._rule_based_decision(critical_scan, policy)

            assert decision.decision == "reject"
            assert decision.risk_score == 100
            assert len(decision.critical_issues) > 0
            assert "CRITICAL" in decision.critical_issues[0]

    def test_high_vulnerabilities_strict_policy(self, security_agent, high_scan):
        """Test HIGH vulnerabilities with strict policy."""
        decision = security_agent._rule_based_decision(high_scan, "strict")

        assert decision.decision == "reject"
        assert decision.risk_score == 75
        assert len(decision.critical_issues) > 0

    def test_high_vulnerabilities_balanced_policy(self, security_agent, high_scan):
        """Test HIGH vulnerabilities with balanced policy."""
        decision = security_agent._rule_based_decision(high_scan, "balanced")

        assert decision.decision == "warn"
        assert decision.risk_score == 60
        assert len(decision.critical_issues) > 0

    def test_high_vulnerabilities_permissive_policy(self, security_agent, high_scan):
        """Test HIGH vulnerabilities with permissive policy."""
        decision = security_agent._rule_based_decision(high_scan, "permissive")

        assert decision.decision == "approve"
        assert decision.risk_score == 40
        assert len(decision.critical_issues) > 0

    def test_medium_vulnerabilities_approved(self, security_agent, medium_scan):
        """Test that MEDIUM vulnerabilities are approved (all policies)."""
        for policy in ["strict", "balanced", "permissive"]:
            decision = security_agent._rule_based_decision(medium_scan, policy)

            assert decision.decision == "approve"
            assert decision.risk_score == 30
            assert len(decision.recommendations) > 0


class TestSecurityAgentAnalysisContext:
    """Test analysis context building."""

    def test_build_context_includes_summary(self, security_agent, critical_scan):
        """Test that context includes vulnerability summary."""
        context = security_agent._build_analysis_context(critical_scan, "strict")

        assert "Target: python:3.11" in context
        assert "Total: 1" in context
        assert "CRITICAL: 1" in context
        assert "CVE-2024-1234" in context
        assert "openssl" in context

    def test_build_context_includes_policy(self, security_agent, high_scan):
        """Test that context includes policy information."""
        context = security_agent._build_analysis_context(high_scan, "balanced")

        assert "Policy: balanced" in context
        assert "Security Policy:" in context

    def test_build_context_top_vulnerabilities(self, security_agent):
        """Test that context includes top 5 vulnerabilities."""
        # Create scan with 10 vulnerabilities
        vulns = [
            Vulnerability(
                cve_id=f"CVE-2024-{i}",
                severity=["CRITICAL", "HIGH", "MEDIUM"][i % 3],
                package_name=f"pkg{i}",
                installed_version="1.0.0",
                fixed_version="2.0.0",
                title=f"Vulnerability {i}",
                description=f"Description {i}"
            )
            for i in range(10)
        ]

        scan = TrivyScanResult(
            scan_type="image",
            target="test:latest",
            total_vulnerabilities=10,
            critical_count=4,
            high_count=3,
            medium_count=3,
            low_count=0,
            vulnerabilities=vulns
        )

        context = security_agent._build_analysis_context(scan, "strict")

        # Should include top vulnerabilities
        assert "CVE-2024-0" in context
        # Context should not be too long
        assert len(context) < 2000


class TestSecurityDecisionDataclass:
    """Test SecurityDecision dataclass."""

    def test_security_decision_creation(self):
        """Test creating a SecurityDecision."""
        decision = SecurityDecision(
            decision="reject",
            reasoning="Critical vulnerabilities found",
            critical_issues=["CVE-2024-1234"],
            recommendations=["Fix OpenSSL"],
            risk_score=95
        )

        assert decision.decision == "reject"
        assert decision.risk_score == 95
        assert len(decision.critical_issues) == 1
        assert len(decision.recommendations) == 1


class TestSecurityAgentAnalyzeScan:
    """Test the main analyze_scan method."""

    def test_analyze_clean_scan(self, security_agent, clean_scan):
        """Test analyzing a clean scan (no vulnerabilities)."""
        # Should return immediately without AI
        decision = security_agent.analyze_scan(clean_scan)

        assert decision.decision == "approve"
        assert decision.risk_score == 0
        assert "No vulnerabilities" in decision.reasoning

    @patch('agents.security.security_agent.CREWAI_AVAILABLE', True)
    @patch('agents.security.security_agent.Crew')
    def test_analyze_scan_ai_success(self, mock_crew, security_agent, high_scan):
        """Test successful AI analysis (requires CrewAI)."""
        # Skip if CrewAI not available
        if not security_agent.agent:
            pytest.skip("CrewAI not available")

        # Mock AI response
        mock_crew_instance = Mock()
        mock_crew_instance.kickoff.return_value = '''
        {
            "decision": "warn",
            "reasoning": "HIGH vulnerabilities found but fixable",
            "critical_issues": ["curl vulnerability"],
            "recommendations": ["Update curl to 7.70.0"],
            "risk_score": 65
        }
        '''
        mock_crew.return_value = mock_crew_instance

        # Temporarily set agent to non-None for this test
        if security_agent.agent is None:
            from unittest.mock import Mock as MockAgent
            security_agent.agent = MockAgent()

        decision = security_agent.analyze_scan(high_scan, policy="balanced")

        assert decision.decision == "warn"
        assert 50 <= decision.risk_score <= 100  # Accept range
        assert len(decision.recommendations) > 0

    @patch('agents.security.security_agent.Crew')
    def test_analyze_scan_ai_failure_fallback(self, mock_crew, security_agent, critical_scan):
        """Test that AI failure falls back to rule-based."""
        # Mock AI failure
        mock_crew_instance = Mock()
        mock_crew_instance.kickoff.side_effect = Exception("AI service unavailable")
        mock_crew.return_value = mock_crew_instance

        decision = security_agent.analyze_scan(critical_scan, policy="strict")

        # Should fall back to rule-based
        assert decision.decision == "reject"
        assert decision.risk_score == 100

    @patch('agents.security.security_agent.Crew')
    def test_analyze_scan_logs_result(self, mock_crew, security_agent, high_scan):
        """Test that analysis is logged."""
        mock_crew_instance = Mock()
        mock_crew_instance.kickoff.return_value = "{}"
        mock_crew.return_value = mock_crew_instance

        with patch('agents.security.security_agent.logger') as mock_logger:
            security_agent.analyze_scan(high_scan)

            # Verify logging
            assert mock_logger.info.called


class TestSecurityAgentPolicies:
    """Test different security policies."""

    def test_strict_policy_blocks_high(self, security_agent, high_scan):
        """Test strict policy blocks HIGH vulnerabilities."""
        decision = security_agent._rule_based_decision(high_scan, "strict")
        assert decision.decision == "reject"

    def test_balanced_policy_warns_high(self, security_agent, high_scan):
        """Test balanced policy warns on HIGH vulnerabilities."""
        decision = security_agent._rule_based_decision(high_scan, "balanced")
        assert decision.decision == "warn"

    def test_permissive_policy_allows_high(self, security_agent, high_scan):
        """Test permissive policy allows HIGH vulnerabilities."""
        decision = security_agent._rule_based_decision(high_scan, "permissive")
        assert decision.decision == "approve"

    def test_all_policies_block_critical(self, security_agent, critical_scan):
        """Test all policies block CRITICAL vulnerabilities."""
        for policy in ["strict", "balanced", "permissive"]:
            decision = security_agent._rule_based_decision(critical_scan, policy)
            assert decision.decision == "reject"
            assert decision.risk_score == 100


# Integration test
@pytest.mark.integration
class TestSecurityAgentIntegration:
    """Integration tests for Security Agent."""

    def test_full_workflow_with_trivy(self):
        """Test complete workflow: scan + analysis (requires Trivy)."""
        from infrastructure.security.trivy_scanner import TrivyScanner

        try:
            # Scan a real image
            scanner = TrivyScanner()
            scan_result = scanner.scan_image("alpine:3.19", severity="CRITICAL")

            # Analyze with Security Agent
            with patch('agents.security.security_agent.GroqClient'):
                agent = SecurityAgentService()
                decision = agent.analyze_scan(scan_result, policy="strict")

            assert isinstance(decision, SecurityDecision)
            assert decision.decision in ["approve", "reject", "warn"]
            assert 0 <= decision.risk_score <= 100

        except RuntimeError as e:
            pytest.skip(f"Trivy not installed: {e}")
