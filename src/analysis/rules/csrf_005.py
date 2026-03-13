"""CSRF-005: Missing SameSite Cookie.

Detects session cookies in Set-Cookie response headers that lack
the SameSite attribute entirely.

Ref:
    - spec/Requirements.md FR-206
    - config/rules.yaml CSRF-005
    - config/settings.yaml auth_detection.session_cookie_patterns
    - spec/Tasks.md T-215
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)

# Cookie names matching these substrings are considered session cookies.
# Mirrors config/settings.yaml auth_detection.session_cookie_patterns.
_SESSION_COOKIE_PATTERNS = ("session", "sid", "auth")


class Csrf005(BaseRule):
    """Missing SameSite Cookie.

    Inspects ``Set-Cookie`` response headers.  If a session-related
    cookie (name contains 'session', 'sid', or 'auth') is set
    without a ``SameSite`` attribute, this rule fires.

    ``SameSite`` (Lax or Strict) prevents cross-site cookie
    attachment, which is a key CSRF mitigation.
    """

    rule_id = "CSRF-005"
    rule_name = "Missing SameSite Cookie"
    severity = Severity.MEDIUM

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check Set-Cookie headers for missing SameSite."""
        findings: List[Finding] = []

        set_cookie_value = ""
        for k, v in exchange.response_headers.items():
            if k.lower() == "set-cookie":
                set_cookie_value = v
                break

        if not set_cookie_value:
            return []

        # A response may set multiple cookies via comma-separated
        # or multiple Set-Cookie headers; HAR parser joins them.
        # We also handle the single-cookie case.
        for cookie_str in _split_set_cookies(set_cookie_value):
            cookie_name = _extract_cookie_name(cookie_str)
            if not _is_session_cookie(cookie_name):
                continue

            if "samesite" not in cookie_str.lower():
                findings.append(
                    self._make_finding(
                        description=(
                            f"Session cookie '{cookie_name}' is set "
                            f"without a SameSite attribute."
                        ),
                        evidence=f"Set-Cookie: {cookie_str}",
                        exchange=exchange,
                    )
                )

        return findings


class Csrf006(BaseRule):
    """SameSite=None Without Secure.

    Triggers when a session cookie has ``SameSite=None`` but the
    ``Secure`` flag is missing.  Browsers reject ``SameSite=None``
    without ``Secure`` in modern implementations, but older browsers
    may accept it, creating a CSRF vector.

    Ref: spec/Requirements.md FR-207, config/rules.yaml CSRF-006,
         spec/Tasks.md T-216
    """

    rule_id = "CSRF-006"
    rule_name = "SameSite=None Without Secure"
    severity = Severity.HIGH

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check for SameSite=None without Secure flag."""
        findings: List[Finding] = []

        set_cookie_value = ""
        for k, v in exchange.response_headers.items():
            if k.lower() == "set-cookie":
                set_cookie_value = v
                break
                
        if not set_cookie_value:
            return []

        for cookie_str in _split_set_cookies(set_cookie_value):
            cookie_name = _extract_cookie_name(cookie_str)
            if not _is_session_cookie(cookie_name):
                continue

            lower = cookie_str.lower()
            if "samesite=none" in lower and "secure" not in lower:
                findings.append(
                    self._make_finding(
                        description=(
                            f"Session cookie '{cookie_name}' has "
                            f"SameSite=None but no Secure flag."
                        ),
                        evidence=f"Set-Cookie: {cookie_str}",
                        exchange=exchange,
                    )
                )

        return findings


# ------------------------------------------------------------------
# Shared helpers for cookie parsing (used by CSRF-005 and CSRF-006)
# ------------------------------------------------------------------


def _split_set_cookies(header_value: str) -> List[str]:
    """Split a Set-Cookie header value into individual cookie strings.

    har_parser.py separates multiple Set-Cookie headers with a newline.
    """
    parts: List[str] = []
    for line in header_value.split("\n"):
        line = line.strip()
        if line:
            parts.append(line)

    return parts


def _extract_cookie_name(cookie_str: str) -> str:
    """Extract the cookie name from a Set-Cookie string.

    e.g., ``"session_id=abc123; Path=/; SameSite=Lax"`` → ``"session_id"``
    """
    first_part = cookie_str.split(";")[0].strip()
    name = first_part.split("=")[0].strip()
    return name


def _is_session_cookie(name: str) -> bool:
    """Return True if the cookie name suggests a session cookie."""
    lower = name.lower()
    return any(pat in lower for pat in _SESSION_COOKIE_PATTERNS)
