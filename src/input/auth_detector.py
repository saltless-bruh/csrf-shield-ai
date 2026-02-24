"""Auth mechanism detector for CSRF Shield AI.

Detects the authentication mechanism used in a session flow and
implements the short-circuit path for header-only auth.

Detection truth table:
    | Cookies? | Auth Headers? | Result       |
    |----------|---------------|--------------|
    |    ✅    |      ❌       | COOKIE       |
    |    ❌    |      ✅       | HEADER_ONLY  |
    |    ✅    |      ✅       | MIXED        |
    |    ❌    |      ❌       | NONE         |

Ref:
    - spec/Design.md §2.3 (Short-Circuit Path)
    - coding_standards.instructions.md §1.3
    - config/settings.yaml — auth_detection section
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.input.models import (
    AnalysisResult,
    AuthMechanism,
    Finding,
    HttpExchange,
    RiskLevel,
    SessionFlow,
    Severity,
)

logger = logging.getLogger(__name__)

# Default auth headers — matches settings.yaml auth_detection.custom_headers
DEFAULT_AUTH_HEADERS: List[str] = [
    "Authorization",
    "X-API-Key",
    "X-Auth-Token",
    "Api-Key",
    "X-Access-Token",
]

# Default session cookie patterns — matches settings.yaml
DEFAULT_SESSION_COOKIE_PATTERNS: List[str] = ["session", "sid", "auth"]

# Short-circuit score — matches settings.yaml scoring.short_circuit_score
SHORT_CIRCUIT_SCORE: int = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_auth_mechanism(
    flow: SessionFlow,
    cookie_patterns: Optional[List[str]] = None,
    auth_headers: Optional[List[str]] = None,
) -> AuthMechanism:
    """Detect the authentication mechanism used in a session flow.

    Scans all exchanges in the flow for session cookies and auth headers.
    A single match across any exchange is sufficient to flag that category.

    Args:
        flow: The session flow to analyze.
        cookie_patterns: Substrings to match against cookie names
            (case-insensitive). Defaults to ``["session", "sid", "auth"]``.
        auth_headers: Header names to check for (case-insensitive).
            Defaults to the 5 custom auth headers from settings.yaml.

    Returns:
        The detected AuthMechanism enum value.

    Ref: FR-106, coding_standards.instructions.md §1.3
    """
    patterns = cookie_patterns or DEFAULT_SESSION_COOKIE_PATTERNS
    headers = auth_headers or DEFAULT_AUTH_HEADERS

    has_cookies = False
    has_auth_headers = False

    for exchange in flow.exchanges:
        if not has_cookies:
            has_cookies = _has_session_cookie(exchange, patterns)
        if not has_auth_headers:
            has_auth_headers = _has_auth_header(exchange, headers)
        # Early exit if both found
        if has_cookies and has_auth_headers:
            break

    if has_cookies and has_auth_headers:
        mechanism = AuthMechanism.MIXED
    elif has_cookies:
        mechanism = AuthMechanism.COOKIE
    elif has_auth_headers:
        mechanism = AuthMechanism.HEADER_ONLY
    else:
        mechanism = AuthMechanism.NONE

    logger.debug(
        "Flow %s: cookies=%s, auth_headers=%s → %s",
        flow.session_id,
        has_cookies,
        has_auth_headers,
        mechanism.value,
    )
    return mechanism


def update_flow_auth(
    flow: SessionFlow,
    cookie_patterns: Optional[List[str]] = None,
    auth_headers: Optional[List[str]] = None,
) -> SessionFlow:
    """Detect auth mechanism and return a new SessionFlow with it set.

    Since SessionFlow is frozen, this creates a new instance with the
    detected auth_mechanism replacing the placeholder ``AuthMechanism.NONE``.

    Args:
        flow: The original session flow (typically with NONE auth).
        cookie_patterns: Optional custom cookie patterns.
        auth_headers: Optional custom auth header names.

    Returns:
        New SessionFlow with the detected auth_mechanism.
    """
    mechanism = detect_auth_mechanism(flow, cookie_patterns, auth_headers)
    return SessionFlow(
        session_id=flow.session_id,
        exchanges=flow.exchanges,
        auth_mechanism=mechanism,
    )


def build_short_circuit_result(flow: SessionFlow) -> AnalysisResult:
    """Build an AnalysisResult for a short-circuited header-only flow.

    When auth detection returns HEADER_ONLY, the full analysis pipeline
    is skipped. This function produces the final result directly:

    - CSRF-011 finding with INFO severity
    - Fixed risk score of 5 (LOW)
    - ``ml_probability = None`` (ML pipeline skipped)
    - ``feature_vector = None`` (feature extraction skipped)

    Args:
        flow: The session flow with HEADER_ONLY auth mechanism.

    Returns:
        AnalysisResult with short-circuit values.

    Ref: spec/Design.md §2.3, FR-212, FR-404
    """
    # Use the first exchange as representative for the finding
    representative = flow.exchanges[0] if flow.exchanges else None

    # Build CSRF-011 finding
    csrf_011 = _build_csrf_011_finding(flow, representative)

    # Derive endpoint from representative exchange
    endpoint = representative.request_url if representative else "unknown"
    method = representative.request_method if representative else "GET"

    return AnalysisResult(
        endpoint=endpoint,
        http_method=method,
        risk_score=SHORT_CIRCUIT_SCORE,
        risk_level=RiskLevel.LOW,
        findings=[csrf_011],
        recommendations=["No action needed — CSRF is not applicable to header-only auth."],
        ml_probability=None,
        feature_vector=None,
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _has_session_cookie(
    exchange: HttpExchange,
    patterns: List[str],
) -> bool:
    """Check if an exchange has any session cookie.

    Args:
        exchange: The HTTP exchange to inspect.
        patterns: Substrings to match against cookie names.

    Returns:
        True if any cookie name contains a pattern (case-insensitive).
    """
    for cookie_name in exchange.request_cookies:
        cookie_lower = cookie_name.lower()
        for pattern in patterns:
            if pattern.lower() in cookie_lower:
                return True
    return False


def _has_auth_header(
    exchange: HttpExchange,
    auth_headers: List[str],
) -> bool:
    """Check if an exchange has any auth header.

    Args:
        exchange: The HTTP exchange to inspect.
        auth_headers: Header names to check for.

    Returns:
        True if any auth header is present (case-insensitive).
    """
    request_headers_lower = {k.lower(): v for k, v in exchange.request_headers.items()}
    for header in auth_headers:
        if header.lower() in request_headers_lower:
            return True
    return False


def _build_csrf_011_finding(
    flow: SessionFlow,
    exchange: Optional[HttpExchange],
) -> Finding:
    """Build the CSRF-011 finding for short-circuited flows.

    Args:
        flow: The session flow being short-circuited.
        exchange: Representative exchange (first in flow, or None).

    Returns:
        Finding with CSRF-011 rule data and INFO severity.
    """
    # Collect evidence from auth headers
    evidence_parts: List[str] = []
    if exchange:
        for header_name in DEFAULT_AUTH_HEADERS:
            for req_header, req_value in exchange.request_headers.items():
                if req_header.lower() == header_name.lower():
                    # Truncate long values (e.g., JWT tokens)
                    display_value = req_value[:50] + "..." if len(req_value) > 50 else req_value
                    evidence_parts.append(f"{req_header}: {display_value}")

    evidence = "; ".join(evidence_parts) if evidence_parts else "Header-only auth detected"

    # Create a minimal exchange if none provided
    if exchange is None:
        from datetime import datetime

        exchange = HttpExchange(
            request_method="GET",
            request_url="unknown",
            request_headers={},
            request_cookies={},
            request_body=None,
            request_content_type="",
            response_status=0,
            response_headers={},
            response_body=None,
            timestamp=datetime.now(),
        )

    return Finding(
        rule_id="CSRF-011",
        rule_name="Non-Cookie Auth (CSRF N/A)",
        severity=Severity.INFO,
        description=(
            f"Session '{flow.session_id}' uses header-only authentication. "
            "CSRF attacks require cookie-based auth to be exploitable. "
            "This flow is not vulnerable to CSRF."
        ),
        evidence=evidence,
        exchange=exchange,
    )
