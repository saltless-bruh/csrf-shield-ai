"""Unit tests for CSRF static analysis rules (CSRF-001 through CSRF-010).

Each rule gets a test class with positive (finding triggered) and
negative (no finding) tests, plus edge cases.

Ref:
    - src/analysis/rules/
    - spec/Tasks.md T-221
    - .agent/instructions/testing_strategy.instructions.md §6
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pytest

from src.analysis.rules.base_rule import BaseRule
from src.analysis.rules.csrf_001 import Csrf001
from src.analysis.rules.csrf_002 import Csrf002
from src.analysis.rules.csrf_003 import Csrf003
from src.analysis.rules.csrf_004 import Csrf004
from src.analysis.rules.csrf_005 import Csrf005
from src.analysis.rules.csrf_006 import Csrf006
from src.analysis.rules.csrf_007 import Csrf007
from src.analysis.rules.csrf_008 import Csrf008
from src.analysis.rules.csrf_009 import Csrf009
from src.analysis.rules.csrf_010 import Csrf010
from src.input.models import (
    AuthMechanism,
    Finding,
    HttpExchange,
    SessionFlow,
    Severity,
)


# ===========================================================================
# Test Helpers
# ===========================================================================


def _make_exchange(
    method: str = "POST",
    url: str = "https://example.com/api/update",
    request_headers: Optional[Dict[str, str]] = None,
    request_cookies: Optional[Dict[str, str]] = None,
    request_body: Optional[str] = None,
    content_type: str = "application/x-www-form-urlencoded",
    response_status: int = 200,
    response_headers: Optional[Dict[str, str]] = None,
    response_body: Optional[str] = None,
) -> HttpExchange:
    """Build an HttpExchange with sensible defaults."""
    return HttpExchange(
        request_method=method,
        request_url=url,
        request_headers=request_headers or {},
        request_cookies=request_cookies or {"session_id": "abc123"},
        request_body=request_body,
        request_content_type=content_type,
        response_status=response_status,
        response_headers=response_headers or {},
        response_body=response_body,
        timestamp=datetime(2026, 2, 26, 12, 0, 0),
    )


def _make_flow(
    *exchanges: HttpExchange,
) -> SessionFlow:
    """Build a SessionFlow from one or more exchanges."""
    return SessionFlow(
        session_id="test-session",
        exchanges=list(exchanges),
        auth_mechanism=AuthMechanism.COOKIE,
    )


# ===========================================================================
# BaseRule
# ===========================================================================


class TestBaseRule:
    """Tests for the BaseRule ABC and shared helpers."""

    def test_is_state_changing_post(self) -> None:
        assert BaseRule.is_state_changing("POST") is True

    def test_is_state_changing_put(self) -> None:
        assert BaseRule.is_state_changing("PUT") is True

    def test_is_state_changing_delete(self) -> None:
        assert BaseRule.is_state_changing("DELETE") is True

    def test_is_state_changing_patch(self) -> None:
        assert BaseRule.is_state_changing("PATCH") is True

    def test_is_state_changing_get_false(self) -> None:
        assert BaseRule.is_state_changing("GET") is False

    def test_is_state_changing_head_false(self) -> None:
        assert BaseRule.is_state_changing("HEAD") is False

    def test_is_state_changing_case_insensitive(self) -> None:
        assert BaseRule.is_state_changing("post") is True


# ===========================================================================
# CSRF-001: Missing CSRF Token in Form
# ===========================================================================


class TestCsrf001:
    """CSRF-001: Missing CSRF Token in Form."""

    rule = Csrf001()

    def test_post_form_no_token_triggers(self) -> None:
        """POST with form body lacking CSRF token → finding."""
        ex = _make_exchange(
            method="POST",
            request_body="username=alice&password=secret",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-001"
        assert findings[0].severity == Severity.HIGH

    def test_post_form_with_token_no_finding(self) -> None:
        """POST with csrf_token param → no finding."""
        ex = _make_exchange(
            method="POST",
            request_body="username=alice&csrf_token=abc123xyz456789",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        """GET requests are not state-changing → no finding."""
        ex = _make_exchange(
            method="GET",
            request_body=None,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_json_content_type_skipped(self) -> None:
        """JSON body requests are not checked by this rule."""
        ex = _make_exchange(
            method="POST",
            content_type="application/json",
            request_body='{"username": "alice"}',
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_empty_body_skipped(self) -> None:
        """POST with no body → no finding (nothing to check)."""
        ex = _make_exchange(
            method="POST",
            request_body=None,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-002: Missing CSRF Token in Header
# ===========================================================================


class TestCsrf002:
    """CSRF-002: Missing CSRF Token in Header."""

    rule = Csrf002()

    def test_post_no_csrf_header_triggers(self) -> None:
        """POST without anti-CSRF header → finding."""
        ex = _make_exchange(
            method="POST",
            request_headers={"Content-Type": "application/json"},
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-002"
        assert findings[0].severity == Severity.MEDIUM

    def test_post_with_x_csrf_token_no_finding(self) -> None:
        """POST with X-CSRF-Token header → no finding."""
        ex = _make_exchange(
            method="POST",
            request_headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": "abc123",
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_post_with_x_xsrf_token_no_finding(self) -> None:
        """POST with X-XSRF-Token (Angular) → no finding."""
        ex = _make_exchange(
            method="POST",
            request_headers={"X-XSRF-Token": "angular_token"},
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        """GET request → no finding."""
        ex = _make_exchange(method="GET")
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-003: Predictable CSRF Token
# ===========================================================================


class TestCsrf003:
    """CSRF-003: Predictable CSRF Token (low entropy)."""

    rule = Csrf003()

    def test_low_entropy_token_triggers(self) -> None:
        """Token with repeated chars (entropy < 3.0) → finding."""
        ex = _make_exchange(
            method="POST",
            request_body="data=foo&csrf_token=aaaaaaaaaaaaaaaa",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-003"
        assert "low entropy" in findings[0].description

    def test_high_entropy_token_no_finding(self) -> None:
        """Token with high entropy → no finding."""
        ex = _make_exchange(
            method="POST",
            request_body="data=foo&csrf_token=aB3cD4eF5gH6iJ7kL8mN9",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_no_token_no_finding(self) -> None:
        """No token found → not this rule's concern (CSRF-001)."""
        ex = _make_exchange(
            method="POST",
            request_body="data=foo&bar=baz",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        ex = _make_exchange(method="GET")
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-004: Static CSRF Token
# ===========================================================================


class TestCsrf004:
    """CSRF-004: Static CSRF Token (non-rotating)."""

    rule = Csrf004()

    def test_same_token_across_requests_triggers(self) -> None:
        """Same token value in 2 POSTs → finding on each."""
        ex1 = _make_exchange(
            method="POST",
            url="https://example.com/update",
            request_body="csrf_token=STATIC_TOKEN_VALUE_ABC123&data=1",
        )
        ex2 = _make_exchange(
            method="POST",
            url="https://example.com/delete",
            request_body="csrf_token=STATIC_TOKEN_VALUE_ABC123&data=2",
        )
        flow = _make_flow(ex1, ex2)

        f1 = self.rule.analyze(ex1, flow)
        f2 = self.rule.analyze(ex2, flow)
        assert len(f1) == 1
        assert len(f2) == 1
        assert f1[0].severity == Severity.CRITICAL
        assert "not rotating" in f1[0].description

    def test_different_tokens_no_finding(self) -> None:
        """Different tokens across requests → no finding."""
        ex1 = _make_exchange(
            method="POST",
            url="https://example.com/update",
            request_body="csrf_token=token_abc_123_unique_1&data=1",
        )
        ex2 = _make_exchange(
            method="POST",
            url="https://example.com/delete",
            request_body="csrf_token=token_xyz_789_unique_2&data=2",
        )
        flow = _make_flow(ex1, ex2)

        findings = self.rule.analyze(ex1, flow)
        assert len(findings) == 0

    def test_single_exchange_no_finding(self) -> None:
        """Only one exchange → can't detect reuse."""
        ex = _make_exchange(
            method="POST",
            request_body="csrf_token=single_token_value_here",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-005: Missing SameSite Cookie
# ===========================================================================


class TestCsrf005:
    """CSRF-005: Missing SameSite Cookie."""

    rule = Csrf005()

    def test_session_cookie_no_samesite_triggers(self) -> None:
        """Session cookie without SameSite → finding."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "session_id=abc123; Path=/; HttpOnly"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-005"
        assert findings[0].severity == Severity.MEDIUM

    def test_session_cookie_with_samesite_no_finding(self) -> None:
        """Session cookie with SameSite=Lax → no finding."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "session_id=abc123; Path=/; SameSite=Lax"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_non_session_cookie_ignored(self) -> None:
        """Non-session cookie (e.g., 'theme') → not checked."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "theme=dark; Path=/"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_no_set_cookie_header_no_finding(self) -> None:
        """No Set-Cookie header → nothing to check."""
        ex = _make_exchange(response_headers={})
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-006: SameSite=None Without Secure
# ===========================================================================


class TestCsrf006:
    """CSRF-006: SameSite=None Without Secure."""

    rule = Csrf006()

    def test_samesite_none_no_secure_triggers(self) -> None:
        """SameSite=None without Secure flag → finding."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=None; Path=/"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-006"
        assert findings[0].severity == Severity.HIGH

    def test_samesite_none_with_secure_no_finding(self) -> None:
        """SameSite=None with Secure → no finding."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=None; Secure; Path=/"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_samesite_lax_no_finding(self) -> None:
        """SameSite=Lax — not None, so no finding."""
        ex = _make_exchange(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=Lax; Path=/"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-007: No Origin Header Validation
# ===========================================================================


class TestCsrf007:
    """CSRF-007: No Origin Header Validation."""

    rule = Csrf007()

    def test_origin_present_200_response_triggers(self) -> None:
        """POST with Origin + 200 response → finding."""
        ex = _make_exchange(
            method="POST",
            request_headers={
                "Origin": "https://evil.com",
                "Content-Type": "application/json",
            },
            response_status=200,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-007"

    def test_origin_present_403_response_no_finding(self) -> None:
        """POST with Origin + 403 → server rejected → no finding."""
        ex = _make_exchange(
            method="POST",
            request_headers={"Origin": "https://evil.com"},
            response_status=403,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_vary_origin_present_no_finding(self) -> None:
        """POST with Vary: Origin → server is Origin-aware."""
        ex = _make_exchange(
            method="POST",
            request_headers={"Origin": "https://evil.com"},
            response_status=200,
            response_headers={"Vary": "Origin"},
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_no_origin_header_no_finding(self) -> None:
        """No Origin header → can't assess → no finding."""
        ex = _make_exchange(method="POST", request_headers={})
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        """GET requests are skipped."""
        ex = _make_exchange(
            method="GET",
            request_headers={"Origin": "https://evil.com"},
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-008: GET Request with Side Effects
# ===========================================================================


class TestCsrf008:
    """CSRF-008: GET Request with Side Effects."""

    rule = Csrf008()

    def test_get_delete_url_triggers(self) -> None:
        """GET with /delete in URL → finding."""
        ex = _make_exchange(
            method="GET",
            url="https://example.com/api/delete/123",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-008"

    def test_get_action_query_param_triggers(self) -> None:
        """GET with ?action=remove → finding."""
        ex = _make_exchange(
            method="GET",
            url="https://example.com/api?action=remove",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1

    def test_get_transfer_url_triggers(self) -> None:
        """GET with /transfer in URL → finding."""
        ex = _make_exchange(
            method="GET",
            url="https://example.com/transfer/funds",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1

    def test_get_safe_url_no_finding(self) -> None:
        """GET to a safe URL → no finding."""
        ex = _make_exchange(
            method="GET",
            url="https://example.com/api/profile",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_post_request_skipped(self) -> None:
        """POST with /delete URL — this rule only checks GET."""
        ex = _make_exchange(
            method="POST",
            url="https://example.com/api/delete/123",
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-009: Missing Referer Validation
# ===========================================================================


class TestCsrf009:
    """CSRF-009: Missing Referer Validation."""

    rule = Csrf009()

    def test_post_200_no_vary_referer_triggers(self) -> None:
        """POST → 200 with no Vary: Referer → finding."""
        ex = _make_exchange(
            method="POST",
            response_status=200,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-009"
        assert findings[0].severity == Severity.LOW

    def test_post_200_with_vary_referer_no_finding(self) -> None:
        """POST → 200 with Vary: Referer → no finding."""
        ex = _make_exchange(
            method="POST",
            response_status=200,
            response_headers={"Vary": "Referer"},
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_post_403_no_finding(self) -> None:
        """POST → 403 (server rejected) → no finding."""
        ex = _make_exchange(
            method="POST",
            response_status=403,
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        ex = _make_exchange(method="GET", response_status=200)
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0


# ===========================================================================
# CSRF-010: JSON Endpoint Without CORS
# ===========================================================================


class TestCsrf010:
    """CSRF-010: JSON Endpoint Without CORS."""

    rule = Csrf010()

    def test_json_no_acao_triggers(self) -> None:
        """JSON response with no ACAO → finding."""
        ex = _make_exchange(
            method="POST",
            response_headers={
                "Content-Type": "application/json; charset=utf-8"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1
        assert findings[0].rule_id == "CSRF-010"
        assert findings[0].severity == Severity.MEDIUM

    def test_json_acao_wildcard_triggers(self) -> None:
        """JSON response with ACAO: * → finding."""
        ex = _make_exchange(
            method="POST",
            response_headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 1

    def test_json_acao_specific_origin_no_finding(self) -> None:
        """JSON response with specific origin → no finding."""
        ex = _make_exchange(
            method="POST",
            response_headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "https://trusted.com",
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_non_json_response_skipped(self) -> None:
        """HTML response → not a JSON endpoint → no finding."""
        ex = _make_exchange(
            method="POST",
            response_headers={
                "Content-Type": "text/html"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0

    def test_get_request_skipped(self) -> None:
        """GET request → skipped by state-changing check."""
        ex = _make_exchange(
            method="GET",
            response_headers={
                "Content-Type": "application/json"
            },
        )
        findings = self.rule.analyze(ex, _make_flow(ex))
        assert len(findings) == 0
