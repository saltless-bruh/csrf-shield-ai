"""Shared pytest fixtures for CSRF Shield AI test suite.

Ref: .agent/instructions/testing_strategy.instructions.md §2.2

Provides reusable test data objects used across unit and integration tests.
All fixtures return real dataclass instances from src.input.models.
"""

from __future__ import annotations

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


@pytest.fixture
def sample_exchange() -> HttpExchange:
    """A basic POST exchange with cookie auth and a CSRF token in the body.

    Mirrors the typical state-changing request that the static analyzer
    would inspect for CSRF protections.
    """
    return HttpExchange(
        request_method="POST",
        request_url="https://example.com/profile/update",
        request_headers={"Content-Type": "application/x-www-form-urlencoded"},
        request_cookies={"session_id": "abc123"},
        request_body="name=test&csrf_token=randomtoken123456",
        request_content_type="application/x-www-form-urlencoded",
        response_status=200,
        response_headers={"Set-Cookie": "session_id=abc123; SameSite=Lax"},
        response_body="<html>OK</html>",
        timestamp=datetime(2026, 2, 24, 12, 0, 0),
    )


@pytest.fixture
def sample_session_flow(sample_exchange: HttpExchange) -> SessionFlow:
    """A session flow containing one exchange with cookie-based auth."""
    return SessionFlow(
        session_id="test-session",
        exchanges=[sample_exchange],
        auth_mechanism=AuthMechanism.COOKIE,
    )


@pytest.fixture
def bearer_exchange() -> HttpExchange:
    """An HTTP exchange using Bearer token auth (no cookies).

    Used for testing the auth short-circuit path (CSRF-011).
    """
    return HttpExchange(
        request_method="GET",
        request_url="https://api.example.com/users/me",
        request_headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        },
        request_cookies={},
        request_body=None,
        request_content_type="application/json",
        response_status=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"id": 1, "name": "Test User"}',
        timestamp=datetime(2026, 2, 24, 12, 0, 0),
    )


@pytest.fixture
def bearer_session_flow(bearer_exchange: HttpExchange) -> SessionFlow:
    """A session flow using header-only auth — triggers short-circuit."""
    return SessionFlow(
        session_id="bearer-session",
        exchanges=[bearer_exchange],
        auth_mechanism=AuthMechanism.HEADER_ONLY,
    )


@pytest.fixture
def sample_finding(sample_exchange: HttpExchange) -> Finding:
    """A HIGH-severity finding for missing CSRF token (CSRF-001)."""
    return Finding(
        rule_id="CSRF-001",
        rule_name="Missing CSRF Token in Form",
        severity=Severity.HIGH,
        description="State-changing POST request without CSRF token in form body.",
        evidence="Body contains no known CSRF token parameter.",
        exchange=sample_exchange,
    )


@pytest.fixture
def sample_analysis_result(sample_finding: Finding) -> AnalysisResult:
    """A complete analysis result with ML probability (non-short-circuited)."""
    return AnalysisResult(
        endpoint="/profile/update",
        http_method="POST",
        risk_score=65,
        risk_level=RiskLevel.HIGH,
        findings=[sample_finding],
        recommendations=["Add CSRF token to all state-changing forms."],
        ml_probability=0.82,
        feature_vector={"has_csrf_token": 0, "token_entropy": 0.0},
    )
