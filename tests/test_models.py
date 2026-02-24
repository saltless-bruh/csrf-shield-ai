"""Unit tests for core data models.

Tests all 3 Enums and 4 dataclasses in src/input/models.py.

Ref:
    - spec/Design.md §3.1
    - .agent/instructions/testing_strategy.instructions.md §2.1
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from src.input.models import (
    AnalysisResult,
    AuthMechanism,
    Finding,
    HttpExchange,
    RiskLevel,
    SessionFlow,
    Severity,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestSeverity:
    """Tests for the Severity enum."""

    def test_all_members_exist(self) -> None:
        """Severity has exactly 5 members: CRITICAL, HIGH, MEDIUM, LOW, INFO."""
        assert len(Severity) == 5
        expected = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
        assert {s.value for s in Severity} == expected

    def test_string_comparison(self) -> None:
        """Severity members compare equal to their string values (str mixin)."""
        assert Severity.HIGH == "HIGH"
        assert Severity.INFO == "INFO"

    def test_construction_from_string(self) -> None:
        """Severity can be constructed from a string value."""
        assert Severity("CRITICAL") is Severity.CRITICAL

    def test_invalid_value_raises(self) -> None:
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError):
            Severity("UNKNOWN")


class TestRiskLevel:
    """Tests for the RiskLevel enum."""

    def test_all_members_exist(self) -> None:
        """RiskLevel has exactly 4 members: LOW, MEDIUM, HIGH, CRITICAL."""
        assert len(RiskLevel) == 4
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert {r.value for r in RiskLevel} == expected

    def test_string_comparison(self) -> None:
        """RiskLevel members compare equal to their string values."""
        assert RiskLevel.LOW == "LOW"
        assert RiskLevel.CRITICAL == "CRITICAL"


class TestAuthMechanism:
    """Tests for the AuthMechanism enum."""

    def test_all_members_exist(self) -> None:
        """AuthMechanism has exactly 4 members with lowercase values."""
        assert len(AuthMechanism) == 4
        expected = {"cookie", "header_only", "mixed", "none"}
        assert {a.value for a in AuthMechanism} == expected

    def test_string_comparison(self) -> None:
        """AuthMechanism members compare equal to their lowercase string values."""
        assert AuthMechanism.COOKIE == "cookie"
        assert AuthMechanism.HEADER_ONLY == "header_only"
        assert AuthMechanism.NONE == "none"

    def test_construction_from_string(self) -> None:
        """AuthMechanism can be constructed from a lowercase string value."""
        assert AuthMechanism("header_only") is AuthMechanism.HEADER_ONLY


# ---------------------------------------------------------------------------
# HttpExchange Tests
# ---------------------------------------------------------------------------


class TestHttpExchange:
    """Tests for the HttpExchange dataclass."""

    def test_basic_construction(self, sample_exchange: HttpExchange) -> None:
        """HttpExchange can be constructed with all required fields."""
        assert sample_exchange.request_method == "POST"
        assert sample_exchange.request_url == "https://example.com/profile/update"
        assert sample_exchange.response_status == 200

    def test_frozen_immutability(self, sample_exchange: HttpExchange) -> None:
        """HttpExchange fields cannot be modified after construction."""
        with pytest.raises(FrozenInstanceError):
            sample_exchange.request_method = "GET"  # type: ignore[misc]

    def test_optional_body_none(self) -> None:
        """HttpExchange accepts None for optional body fields."""
        exchange = HttpExchange(
            request_method="GET",
            request_url="https://example.com/",
            request_headers={},
            request_cookies={},
            request_body=None,
            request_content_type="",
            response_status=200,
            response_headers={},
            response_body=None,
            timestamp=datetime(2026, 1, 1),
        )
        assert exchange.request_body is None
        assert exchange.response_body is None

    def test_empty_headers_and_cookies(self) -> None:
        """HttpExchange works with empty header and cookie dicts."""
        exchange = HttpExchange(
            request_method="GET",
            request_url="https://example.com/",
            request_headers={},
            request_cookies={},
            request_body=None,
            request_content_type="",
            response_status=200,
            response_headers={},
            response_body=None,
            timestamp=datetime(2026, 1, 1),
        )
        assert exchange.request_headers == {}
        assert exchange.request_cookies == {}

    def test_equality(self) -> None:
        """Two HttpExchange objects with same data are equal."""
        ts = datetime(2026, 1, 1)
        kwargs = dict(
            request_method="GET",
            request_url="https://example.com/",
            request_headers={},
            request_cookies={},
            request_body=None,
            request_content_type="",
            response_status=200,
            response_headers={},
            response_body=None,
            timestamp=ts,
        )
        assert HttpExchange(**kwargs) == HttpExchange(**kwargs)


# ---------------------------------------------------------------------------
# SessionFlow Tests
# ---------------------------------------------------------------------------


class TestSessionFlow:
    """Tests for the SessionFlow dataclass."""

    def test_basic_construction(self, sample_session_flow: SessionFlow) -> None:
        """SessionFlow can be constructed with required fields."""
        assert sample_session_flow.session_id == "test-session"
        assert sample_session_flow.auth_mechanism == AuthMechanism.COOKIE
        assert len(sample_session_flow.exchanges) == 1

    def test_frozen_immutability(self, sample_session_flow: SessionFlow) -> None:
        """SessionFlow fields cannot be modified after construction."""
        with pytest.raises(FrozenInstanceError):
            sample_session_flow.session_id = "hacked"  # type: ignore[misc]

    def test_auth_mechanism_is_enum(self, sample_session_flow: SessionFlow) -> None:
        """auth_mechanism field is an AuthMechanism enum instance."""
        assert isinstance(sample_session_flow.auth_mechanism, AuthMechanism)

    def test_header_only_auth(self, bearer_session_flow: SessionFlow) -> None:
        """SessionFlow with header-only auth uses HEADER_ONLY enum."""
        assert bearer_session_flow.auth_mechanism == AuthMechanism.HEADER_ONLY
        assert bearer_session_flow.auth_mechanism == "header_only"


# ---------------------------------------------------------------------------
# Finding Tests
# ---------------------------------------------------------------------------


class TestFinding:
    """Tests for the Finding dataclass."""

    def test_basic_construction(self, sample_exchange: HttpExchange) -> None:
        """Finding can be constructed with all fields."""
        finding = Finding(
            rule_id="CSRF-001",
            rule_name="Missing CSRF Token in Form",
            severity=Severity.HIGH,
            description="No CSRF token found in POST body.",
            evidence="Body: name=test",
            exchange=sample_exchange,
        )
        assert finding.rule_id == "CSRF-001"
        assert finding.severity == Severity.HIGH
        assert finding.severity == "HIGH"

    def test_frozen_immutability(self, sample_exchange: HttpExchange) -> None:
        """Finding fields cannot be modified after construction."""
        finding = Finding(
            rule_id="CSRF-001",
            rule_name="Missing CSRF Token in Form",
            severity=Severity.HIGH,
            description="Test",
            evidence="Test",
            exchange=sample_exchange,
        )
        with pytest.raises(FrozenInstanceError):
            finding.severity = Severity.LOW  # type: ignore[misc]

    def test_info_severity_for_csrf_011(self, bearer_exchange: HttpExchange) -> None:
        """CSRF-011 finding uses INFO severity (short-circuit)."""
        finding = Finding(
            rule_id="CSRF-011",
            rule_name="Non-Cookie Auth (CSRF N/A)",
            severity=Severity.INFO,
            description="Bearer token auth detected — CSRF not applicable.",
            evidence="Authorization: Bearer eyJ...",
            exchange=bearer_exchange,
        )
        assert finding.severity == Severity.INFO


# ---------------------------------------------------------------------------
# AnalysisResult Tests
# ---------------------------------------------------------------------------


class TestAnalysisResult:
    """Tests for the AnalysisResult dataclass."""

    def test_full_pipeline_result(self, sample_exchange: HttpExchange) -> None:
        """AnalysisResult with ML probability (non-short-circuited)."""
        finding = Finding(
            rule_id="CSRF-001",
            rule_name="Missing CSRF Token in Form",
            severity=Severity.HIGH,
            description="Test finding",
            evidence="Test evidence",
            exchange=sample_exchange,
        )
        result = AnalysisResult(
            endpoint="/profile/update",
            http_method="POST",
            risk_score=65,
            risk_level=RiskLevel.HIGH,
            findings=[finding],
            recommendations=["Add CSRF token to forms."],
            ml_probability=0.82,
            feature_vector={"has_csrf_token": 0, "token_entropy": 0.0},
        )
        assert result.risk_score == 65
        assert result.risk_level == RiskLevel.HIGH
        assert result.ml_probability == 0.82
        assert result.feature_vector is not None

    def test_short_circuit_result(self, bearer_exchange: HttpExchange) -> None:
        """AnalysisResult for short-circuited flow (ml_probability=None).

        This is the critical test for the NoneType safety fix:
        ml_probability and feature_vector must be None when the ML
        pipeline is skipped due to header-only auth.
        """
        finding = Finding(
            rule_id="CSRF-011",
            rule_name="Non-Cookie Auth (CSRF N/A)",
            severity=Severity.INFO,
            description="Bearer auth — CSRF N/A.",
            evidence="Authorization: Bearer eyJ...",
            exchange=bearer_exchange,
        )
        result = AnalysisResult(
            endpoint="/users/me",
            http_method="GET",
            risk_score=5,
            risk_level=RiskLevel.LOW,
            findings=[finding],
            recommendations=["No action needed — CSRF not applicable."],
            # ml_probability and feature_vector default to None
        )
        assert result.risk_score == 5
        assert result.risk_level == RiskLevel.LOW
        assert result.ml_probability is None
        assert result.feature_vector is None

    def test_frozen_immutability(self, sample_exchange: HttpExchange) -> None:
        """AnalysisResult fields cannot be modified after construction."""
        result = AnalysisResult(
            endpoint="/test",
            http_method="GET",
            risk_score=10,
            risk_level=RiskLevel.LOW,
            findings=[],
            recommendations=[],
        )
        with pytest.raises(FrozenInstanceError):
            result.risk_score = 99  # type: ignore[misc]

    def test_empty_findings_and_recommendations(self) -> None:
        """AnalysisResult works with empty lists."""
        result = AnalysisResult(
            endpoint="/test",
            http_method="GET",
            risk_score=0,
            risk_level=RiskLevel.LOW,
            findings=[],
            recommendations=[],
        )
        assert result.findings == []
        assert result.recommendations == []
