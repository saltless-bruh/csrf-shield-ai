"""Unit tests for auth mechanism detector.

Tests all 5 auth scenarios, short-circuit result generation,
and flow auth updating.

Ref:
    - spec/Tasks.md T-144
    - .agent/instructions/testing_strategy.instructions.md §2.1
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pytest

from src.input.auth_detector import (
    build_short_circuit_result,
    detect_auth_mechanism,
    update_flow_auth,
)
from src.input.models import (
    AnalysisResult,
    AuthMechanism,
    HttpExchange,
    RiskLevel,
    SessionFlow,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exchange(
    cookies: Dict[str, str] | None = None,
    headers: Dict[str, str] | None = None,
    method: str = "GET",
    url: str = "https://example.com/",
) -> HttpExchange:
    """Helper to create an HttpExchange with minimal boilerplate."""
    return HttpExchange(
        request_method=method,
        request_url=url,
        request_headers=headers or {},
        request_cookies=cookies or {},
        request_body=None,
        request_content_type="",
        response_status=200,
        response_headers={},
        response_body=None,
        timestamp=datetime(2026, 1, 1),
    )


def _make_flow(
    exchanges: List[HttpExchange],
    session_id: str = "test-session",
) -> SessionFlow:
    """Helper to create a SessionFlow with NONE auth."""
    return SessionFlow(
        session_id=session_id,
        exchanges=exchanges,
        auth_mechanism=AuthMechanism.NONE,
    )


# ---------------------------------------------------------------------------
# Auth Detection — 5 Scenarios (T-141)
# ---------------------------------------------------------------------------


class TestDetectAuthMechanism:
    """Tests for detect_auth_mechanism() — all 5 auth scenarios."""

    def test_cookie_only(self) -> None:
        """Session with cookies but no auth headers → COOKIE."""
        flow = _make_flow([
            _make_exchange(cookies={"session_id": "abc123"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.COOKIE

    def test_bearer_token_no_cookies(self) -> None:
        """Session with Authorization header, no cookies → HEADER_ONLY."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_api_key_no_cookies(self) -> None:
        """Session with X-API-Key header, no cookies → HEADER_ONLY."""
        flow = _make_flow([
            _make_exchange(headers={"X-API-Key": "key_abc123"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_x_auth_token_no_cookies(self) -> None:
        """Session with X-Auth-Token header → HEADER_ONLY."""
        flow = _make_flow([
            _make_exchange(headers={"X-Auth-Token": "tok_xyz"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_api_key_alt_no_cookies(self) -> None:
        """Session with Api-Key header → HEADER_ONLY."""
        flow = _make_flow([
            _make_exchange(headers={"Api-Key": "ak_123"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_x_access_token_no_cookies(self) -> None:
        """Session with X-Access-Token header → HEADER_ONLY."""
        flow = _make_flow([
            _make_exchange(headers={"X-Access-Token": "at_456"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_mixed_cookies_and_auth_header(self) -> None:
        """Session with both cookies and auth header → MIXED."""
        flow = _make_flow([
            _make_exchange(
                cookies={"session_id": "abc123"},
                headers={"Authorization": "Bearer eyJ..."},
            ),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.MIXED

    def test_no_cookies_no_headers(self) -> None:
        """Session with neither cookies nor auth headers → NONE."""
        flow = _make_flow([
            _make_exchange(cookies={}, headers={}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.NONE

    def test_non_session_cookies_only(self) -> None:
        """Non-session cookies (e.g., tracking) → NONE."""
        flow = _make_flow([
            _make_exchange(cookies={"_ga": "GA1.2.123", "tracking": "xyz"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.NONE

    def test_multiple_exchanges_mixed(self) -> None:
        """Cookie in one exchange, auth header in another → MIXED."""
        flow = _make_flow([
            _make_exchange(cookies={"session_id": "abc123"}),
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.MIXED

    def test_case_insensitive_header_matching(self) -> None:
        """Auth header matching is case-insensitive."""
        flow = _make_flow([
            _make_exchange(headers={"authorization": "Bearer eyJ..."}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.HEADER_ONLY

    def test_jsessionid_recognized(self) -> None:
        """JSESSIONID cookie matches 'session' pattern → COOKIE."""
        flow = _make_flow([
            _make_exchange(cookies={"JSESSIONID": "jvm_abc"}),
        ])
        assert detect_auth_mechanism(flow) == AuthMechanism.COOKIE

    def test_custom_patterns(self) -> None:
        """Custom patterns override defaults."""
        flow = _make_flow([
            _make_exchange(cookies={"my_token": "tok123"}),
        ])
        # Default patterns won't match 'my_token'
        assert detect_auth_mechanism(flow) == AuthMechanism.NONE
        # Custom pattern matches
        assert detect_auth_mechanism(flow, cookie_patterns=["token"]) == AuthMechanism.COOKIE


# ---------------------------------------------------------------------------
# Short-Circuit Result (T-142, T-143)
# ---------------------------------------------------------------------------


class TestBuildShortCircuitResult:
    """Tests for build_short_circuit_result()."""

    def test_risk_score_is_5(self) -> None:
        """Short-circuit result has fixed risk score of 5."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert result.risk_score == 5

    def test_risk_level_is_low(self) -> None:
        """Short-circuit result has LOW risk level."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert result.risk_level == RiskLevel.LOW

    def test_ml_probability_is_none(self) -> None:
        """ML probability is None (ML pipeline skipped).

        This is the critical NoneType safety test: ml_probability must be
        None when the ML pipeline is skipped due to header-only auth.
        The risk scorer must handle this gracefully without TypeError.
        """
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert result.ml_probability is None

    def test_feature_vector_is_none(self) -> None:
        """Feature vector is None (feature extraction skipped)."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert result.feature_vector is None

    def test_csrf_011_finding_present(self) -> None:
        """Result contains exactly one CSRF-011 finding."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "CSRF-011"
        assert result.findings[0].severity == Severity.INFO

    def test_finding_has_evidence(self) -> None:
        """CSRF-011 finding includes auth header as evidence."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJtoken"}),
        ])
        result = build_short_circuit_result(flow)
        assert "Authorization" in result.findings[0].evidence

    def test_recommendation_present(self) -> None:
        """Result has a recommendation about CSRF not applicable."""
        flow = _make_flow([
            _make_exchange(headers={"Authorization": "Bearer eyJ..."}),
        ])
        result = build_short_circuit_result(flow)
        assert len(result.recommendations) == 1
        assert "not applicable" in result.recommendations[0].lower()

    def test_endpoint_from_first_exchange(self) -> None:
        """Endpoint is taken from the first exchange's URL."""
        flow = _make_flow([
            _make_exchange(
                headers={"Authorization": "Bearer eyJ..."},
                url="https://api.example.com/users/me",
            ),
        ])
        result = build_short_circuit_result(flow)
        assert result.endpoint == "https://api.example.com/users/me"


# ---------------------------------------------------------------------------
# Update Flow Auth
# ---------------------------------------------------------------------------


class TestUpdateFlowAuth:
    """Tests for update_flow_auth()."""

    def test_updates_mechanism(self) -> None:
        """update_flow_auth() detects and sets the auth mechanism."""
        flow = _make_flow([
            _make_exchange(cookies={"session_id": "abc123"}),
        ])
        assert flow.auth_mechanism == AuthMechanism.NONE

        updated = update_flow_auth(flow)
        assert updated.auth_mechanism == AuthMechanism.COOKIE

    def test_preserves_session_id(self) -> None:
        """Session ID is preserved in the updated flow."""
        flow = _make_flow(
            [_make_exchange(cookies={"session_id": "abc123"})],
            session_id="my-session",
        )
        updated = update_flow_auth(flow)
        assert updated.session_id == "my-session"

    def test_preserves_exchanges(self) -> None:
        """Exchanges are preserved in the updated flow."""
        ex = _make_exchange(cookies={"session_id": "abc123"})
        flow = _make_flow([ex])
        updated = update_flow_auth(flow)
        assert updated.exchanges == [ex]

    def test_returns_new_instance(self) -> None:
        """Returns a new SessionFlow (frozen, so cannot mutate)."""
        flow = _make_flow([_make_exchange()])
        updated = update_flow_auth(flow)
        assert updated is not flow
