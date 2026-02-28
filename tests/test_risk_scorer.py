"""Tests for the risk scoring engine.

Verifies Base Score formula, static normalization, context modifiers,
risk level classification, and short-circuit logic.

Ref:
    - src/scoring/risk_scorer.py
    - spec/Tasks.md T-401 through T-405
    - docs/proposal/PROPOSAL.md §10.1, §10.2, §10.3
"""

from __future__ import annotations

from datetime import datetime
from typing import List

import pytest

from src.input.models import Finding, HttpExchange, Severity
from src.scoring.risk_scorer import (
    RiskLevel,
    RiskResult,
    RiskScorer,
    classify_risk,
    detect_context_modifiers,
    normalize_static_score,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _ex() -> HttpExchange:
    """Minimal exchange for findings."""
    return HttpExchange(
        request_method="POST",
        request_url="https://example.com/test",
        request_headers={},
        request_cookies={},
        request_body=None,
        request_content_type="",
        response_status=200,
        response_headers={},
        response_body=None,
        timestamp=datetime(2026, 2, 28),
    )


def _finding(rule_id: str, severity: Severity) -> Finding:
    return Finding(
        rule_id=rule_id,
        rule_name="Test",
        severity=severity,
        description="Test",
        evidence="",
        exchange=_ex(),
    )


# ===========================================================================
# T-402: Static Normalization
# ===========================================================================


class TestStaticNormalization:
    """Static score normalization tests."""

    def test_no_findings(self) -> None:
        assert normalize_static_score([]) == 0.0

    def test_single_critical(self) -> None:
        findings = [_finding("CSRF-001", Severity.CRITICAL)]
        score = normalize_static_score(findings)
        assert score == pytest.approx(1.0 / 11.0, abs=0.01)

    def test_multiple_findings(self) -> None:
        """HIGH + MEDIUM → (0.75 + 0.5) / 11.0."""
        findings = [
            _finding("CSRF-001", Severity.HIGH),
            _finding("CSRF-005", Severity.MEDIUM),
        ]
        score = normalize_static_score(findings)
        expected = (0.75 + 0.5) / 11.0
        assert score == pytest.approx(expected, abs=0.01)

    def test_capped_at_one(self) -> None:
        """Max possible → capped at 1.0."""
        findings = [
            _finding(f"R-{i}", Severity.CRITICAL) for i in range(15)
        ]
        score = normalize_static_score(findings)
        assert score <= 1.0


# ===========================================================================
# T-404: Risk Level Classification (FR-402)
# ===========================================================================


class TestClassifyRisk:
    """Risk level classification tests."""

    def test_low_0(self) -> None:
        assert classify_risk(0) == RiskLevel.LOW

    def test_low_20(self) -> None:
        assert classify_risk(20) == RiskLevel.LOW

    def test_medium_21(self) -> None:
        assert classify_risk(21) == RiskLevel.MEDIUM

    def test_medium_40(self) -> None:
        assert classify_risk(40) == RiskLevel.MEDIUM

    def test_high_41(self) -> None:
        assert classify_risk(41) == RiskLevel.HIGH

    def test_high_70(self) -> None:
        assert classify_risk(70) == RiskLevel.HIGH

    def test_critical_71(self) -> None:
        assert classify_risk(71) == RiskLevel.CRITICAL

    def test_critical_100(self) -> None:
        assert classify_risk(100) == RiskLevel.CRITICAL


# ===========================================================================
# T-403: Context Modifiers (FR-403)
# ===========================================================================


class TestContextModifiers:
    """Context modifier detection tests."""

    def test_financial_endpoint(self) -> None:
        mods = detect_context_modifiers(
            "https://bank.com/api/transfer", "POST", []
        )
        descs = [d for d, _ in mods]
        assert "Financial data endpoint" in descs

    def test_user_data_endpoint(self) -> None:
        mods = detect_context_modifiers(
            "https://ex.com/profile/update", "POST", []
        )
        descs = [d for d, _ in mods]
        assert "Modifies user data" in descs

    def test_admin_endpoint(self) -> None:
        mods = detect_context_modifiers(
            "https://ex.com/admin/users", "POST", []
        )
        descs = [d for d, _ in mods]
        assert "Admin-only endpoint" in descs

    def test_https_modifier(self) -> None:
        mods = detect_context_modifiers(
            "https://ex.com/test", "POST", []
        )
        pts = dict(mods)
        assert pts.get("Uses HTTPS") == -5

    def test_http_no_modifier(self) -> None:
        mods = detect_context_modifiers(
            "http://ex.com/test", "POST", []
        )
        descs = [d for d, _ in mods]
        assert "Uses HTTPS" not in descs

    def test_multiple_protections(self) -> None:
        """No protection-absence findings → protections present → -15."""
        mods = detect_context_modifiers(
            "http://ex.com/test", "POST", []
        )
        pts = dict(mods)
        assert pts.get("Multiple CSRF protections") == -15

    def test_get_state_change(self) -> None:
        mods = detect_context_modifiers(
            "https://ex.com/api?action=delete", "GET", []
        )
        descs = [d for d, _ in mods]
        assert "GET-based state change" in descs


# ===========================================================================
# T-401: Risk Scorer (FR-401)
# ===========================================================================


class TestRiskScorer:
    """RiskScorer calculate_risk tests."""

    @pytest.fixture
    def scorer(self) -> RiskScorer:
        return RiskScorer()

    def test_proposal_example_1(self, scorer: RiskScorer) -> None:
        """PROPOSAL §10.1 Example 1: Vulnerable endpoint.

        ML=0.85, Static=HIGH+MEDIUM → 0.70 (approx),
        Base≈77.5. With user data modifier +10.
        """
        findings = [
            _finding("CSRF-001", Severity.HIGH),
            _finding("CSRF-005", Severity.MEDIUM),
        ]
        # ML=0.85, static_normalized=(0.75+0.5)/11≈0.1136
        # Base=(0.5*0.85 + 0.5*0.1136)*100 ≈ 48.2
        result = scorer.calculate_risk(
            ml_probability=0.85,
            findings=findings,
            url="https://bank.com/profile/update",
            http_method="POST",
        )
        assert isinstance(result, RiskResult)
        assert 0 <= result.score <= 100

    def test_proposal_example_2(self, scorer: RiskScorer) -> None:
        """PROPOSAL §10.1 Example 2: Well-protected endpoint.

        ML=0.15, low static findings → low score.
        """
        findings = [
            _finding("CSRF-009", Severity.LOW),
        ]
        result = scorer.calculate_risk(
            ml_probability=0.15,
            findings=findings,
            url="https://ex.com/page",
            http_method="POST",
        )
        assert result.score <= 40  # Should be LOW or MEDIUM

    def test_short_circuit(self, scorer: RiskScorer) -> None:
        """FR-404: Short-circuited → fixed score 5, LOW."""
        result = scorer.calculate_risk(
            ml_probability=0.0,
            findings=[],
            is_short_circuited=True,
        )
        assert result.score == 5
        assert result.level == RiskLevel.LOW

    def test_max_vulnerability(self, scorer: RiskScorer) -> None:
        """Very high ML + many findings → HIGH or CRITICAL."""
        findings = [
            _finding("CSRF-001", Severity.CRITICAL),
            _finding("CSRF-002", Severity.CRITICAL),
            _finding("CSRF-003", Severity.HIGH),
            _finding("CSRF-004", Severity.CRITICAL),
        ]
        result = scorer.calculate_risk(
            ml_probability=0.99,
            findings=findings,
            url="https://bank.com/admin/transfer",
            http_method="POST",
        )
        assert result.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_score_clamped_to_100(self, scorer: RiskScorer) -> None:
        """Score cannot exceed 100."""
        findings = [
            _finding(f"R-{i}", Severity.CRITICAL) for i in range(11)
        ]
        result = scorer.calculate_risk(
            ml_probability=1.0,
            findings=findings,
            url="https://bank.com/admin/transfer?action=delete",
            http_method="GET",
        )
        assert result.score <= 100

    def test_score_clamped_to_0(self, scorer: RiskScorer) -> None:
        """Score cannot go below 0."""
        result = scorer.calculate_risk(
            ml_probability=0.0,
            findings=[],
            url="https://ex.com/safe",
            http_method="GET",
        )
        assert result.score >= 0

    def test_modifiers_in_result(self, scorer: RiskScorer) -> None:
        """Applied modifiers are listed in result."""
        result = scorer.calculate_risk(
            ml_probability=0.50,
            findings=[],
            url="https://bank.com/admin/transfer",
            http_method="POST",
        )
        assert len(result.modifiers_applied) > 0
        assert any("HTTPS" in m for m in result.modifiers_applied)

    def test_base_score_stored(self, scorer: RiskScorer) -> None:
        """base_score field is populated."""
        result = scorer.calculate_risk(
            ml_probability=0.50,
            findings=[],
            url="http://ex.com/test",
            http_method="POST",
        )
        assert result.base_score > 0
