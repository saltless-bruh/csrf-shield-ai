"""Unit tests for the feature extraction engine.

Tests cover all 14 features, categorical encoding, normalization,
and endpoint sensitivity scoring.

Ref:
    - src/analysis/feature_extractor.py
    - docs/proposal/PROPOSAL.md §9.3.2
    - spec/Tasks.md T-234
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional


from src.analysis.feature_extractor import (
    encode_categoricals,
    extract_features,
    normalize_features,
    _compute_endpoint_sensitivity,
    _simplify_content_type,
)
from src.input.models import (
    AuthMechanism,
    HttpExchange,
    SessionFlow,
)


# ===========================================================================
# Test Helpers
# ===========================================================================


def _ex(
    method: str = "POST",
    url: str = "https://example.com/api/update",
    request_headers: Optional[Dict[str, str]] = None,
    request_cookies: Optional[Dict[str, str]] = None,
    request_body: Optional[str] = None,
    content_type: str = "application/x-www-form-urlencoded",
    response_status: int = 200,
    response_headers: Optional[Dict[str, str]] = None,
) -> HttpExchange:
    return HttpExchange(
        request_method=method,
        request_url=url,
        request_headers=request_headers or {},
        request_cookies=request_cookies or {"session_id": "abc"},
        request_body=request_body,
        request_content_type=content_type,
        response_status=response_status,
        response_headers=response_headers or {},
        response_body=None,
        timestamp=datetime(2026, 2, 26, 12, 0, 0),
    )


def _flow(
    *exchanges: HttpExchange,
    auth: AuthMechanism = AuthMechanism.COOKIE,
) -> SessionFlow:
    return SessionFlow(
        session_id="test",
        exchanges=list(exchanges),
        auth_mechanism=auth,
    )


# ===========================================================================
# extract_features — all 14 features
# ===========================================================================


class TestExtractFeatures:
    """Tests for extract_features() returning the raw 14-feature dict."""

    def test_returns_exactly_14_keys(self) -> None:
        """Output dict has exactly 14 features."""
        ex = _ex(request_body="name=test&csrf_token=abc123")
        features = extract_features(ex, _flow(ex))
        assert len(features) == 14

    def test_expected_feature_keys(self) -> None:
        """All 14 expected keys are present."""
        ex = _ex(request_body="data=x")
        features = extract_features(ex, _flow(ex))
        expected = {
            "has_csrf_token_in_form",
            "has_csrf_token_in_header",
            "has_samesite_cookie",
            "has_origin_check",
            "has_referer_check",
            "http_method",
            "is_state_changing",
            "content_type",
            "requires_auth",
            "token_entropy",
            "token_changes_per_request",
            "response_sets_cookie",
            "auth_mechanism",
            "endpoint_sensitivity",
        }
        assert set(features.keys()) == expected

    def test_csrf_token_in_form_detected(self) -> None:
        """CSRF token in body → has_csrf_token_in_form = 1."""
        ex = _ex(request_body="csrf_token=randomvalue123456")
        f = extract_features(ex, _flow(ex))
        assert f["has_csrf_token_in_form"] == 1

    def test_csrf_token_in_form_absent(self) -> None:
        """No CSRF token → has_csrf_token_in_form = 0."""
        ex = _ex(request_body="username=alice&pass=secret")
        f = extract_features(ex, _flow(ex))
        assert f["has_csrf_token_in_form"] == 0

    def test_csrf_token_in_header_detected(self) -> None:
        """X-CSRF-Token header → has_csrf_token_in_header = 1."""
        ex = _ex(
            request_headers={"X-CSRF-Token": "tok123"},
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_csrf_token_in_header"] == 1

    def test_csrf_token_in_header_absent(self) -> None:
        """No anti-CSRF header → has_csrf_token_in_header = 0."""
        ex = _ex(request_headers={"Content-Type": "text/html"})
        f = extract_features(ex, _flow(ex))
        assert f["has_csrf_token_in_header"] == 0

    def test_token_entropy_calculated(self) -> None:
        """Token present → token_entropy > 0."""
        ex = _ex(request_body="csrf_token=aB3cD4eF5gH6iJ7k")
        f = extract_features(ex, _flow(ex))
        assert f["token_entropy"] > 0.0

    def test_token_entropy_zero_when_no_token(self) -> None:
        """No token → token_entropy = 0.0."""
        ex = _ex(request_body="data=hello")
        f = extract_features(ex, _flow(ex))
        assert f["token_entropy"] == 0.0

    def test_is_state_changing_post(self) -> None:
        ex = _ex(method="POST")
        f = extract_features(ex, _flow(ex))
        assert f["is_state_changing"] == 1

    def test_is_state_changing_get(self) -> None:
        ex = _ex(method="GET")
        f = extract_features(ex, _flow(ex))
        assert f["is_state_changing"] == 0

    def test_auth_mechanism_from_flow(self) -> None:
        """auth_mechanism comes from the flow, not the exchange."""
        ex = _ex()
        f = extract_features(
            ex, _flow(ex, auth=AuthMechanism.HEADER_ONLY)
        )
        assert f["auth_mechanism"] == "header_only"

    def test_requires_auth_with_session_cookie(self) -> None:
        """Session cookie present → requires_auth = 1."""
        ex = _ex(request_cookies={"session_id": "abc"})
        f = extract_features(ex, _flow(ex))
        assert f["requires_auth"] == 1

    def test_requires_auth_no_session_cookie(self) -> None:
        """No session cookie → requires_auth = 0."""
        ex = _ex(request_cookies={"theme": "dark"})
        f = extract_features(ex, _flow(ex))
        assert f["requires_auth"] == 0

    def test_response_sets_cookie(self) -> None:
        """Set-Cookie in response → response_sets_cookie = 1."""
        ex = _ex(
            response_headers={"Set-Cookie": "sid=xyz; Path=/"},
        )
        f = extract_features(ex, _flow(ex))
        assert f["response_sets_cookie"] == 1

    def test_response_no_set_cookie(self) -> None:
        """No Set-Cookie → response_sets_cookie = 0."""
        ex = _ex(response_headers={})
        f = extract_features(ex, _flow(ex))
        assert f["response_sets_cookie"] == 0


# ===========================================================================
# SameSite detection
# ===========================================================================


class TestSameSiteDetection:
    """SameSite feature extraction."""

    def test_samesite_lax(self) -> None:
        ex = _ex(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=Lax"
            },
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_samesite_cookie"] == "Lax"

    def test_samesite_strict(self) -> None:
        ex = _ex(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=Strict"
            },
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_samesite_cookie"] == "Strict"

    def test_samesite_none(self) -> None:
        ex = _ex(
            response_headers={
                "Set-Cookie": "session_id=abc; SameSite=None; Secure"
            },
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_samesite_cookie"] == "None"

    def test_samesite_absent(self) -> None:
        ex = _ex(
            response_headers={
                "Set-Cookie": "session_id=abc; Path=/"
            },
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_samesite_cookie"] == "absent"

    def test_no_set_cookie_returns_absent(self) -> None:
        ex = _ex(response_headers={})
        f = extract_features(ex, _flow(ex))
        assert f["has_samesite_cookie"] == "absent"


# ===========================================================================
# Token changes (cross-exchange)
# ===========================================================================


class TestTokenChanges:
    """token_changes_per_request cross-exchange detection."""

    def test_different_tokens_rotate(self) -> None:
        """Different token values → token_changes = 1."""
        ex1 = _ex(
            method="POST",
            url="https://example.com/update",
            request_body="csrf_token=unique_token_value_1",
        )
        ex2 = _ex(
            method="POST",
            url="https://example.com/delete",
            request_body="csrf_token=unique_token_value_2",
        )
        flow = _flow(ex1, ex2)
        f = extract_features(ex1, flow)
        assert f["token_changes_per_request"] == 1

    def test_same_token_static(self) -> None:
        """Same token value → token_changes = 0."""
        ex1 = _ex(
            method="POST",
            url="https://example.com/update",
            request_body="csrf_token=STATIC_TOKEN_VALUE_XYZ",
        )
        ex2 = _ex(
            method="POST",
            url="https://example.com/delete",
            request_body="csrf_token=STATIC_TOKEN_VALUE_XYZ",
        )
        flow = _flow(ex1, ex2)
        f = extract_features(ex1, flow)
        assert f["token_changes_per_request"] == 0

    def test_no_token_returns_zero(self) -> None:
        """No token → token_changes = 0."""
        ex = _ex(request_body="data=x")
        f = extract_features(ex, _flow(ex))
        assert f["token_changes_per_request"] == 0


# ===========================================================================
# Origin / Referer checks
# ===========================================================================


class TestOriginRefererChecks:
    """has_origin_check and has_referer_check features."""

    def test_vary_origin_detected(self) -> None:
        ex = _ex(response_headers={"Vary": "Origin"})
        f = extract_features(ex, _flow(ex))
        assert f["has_origin_check"] == 1

    def test_origin_403_detected(self) -> None:
        ex = _ex(
            request_headers={"Origin": "https://evil.com"},
            response_status=403,
        )
        f = extract_features(ex, _flow(ex))
        assert f["has_origin_check"] == 1

    def test_no_origin_evidence(self) -> None:
        ex = _ex(response_headers={})
        f = extract_features(ex, _flow(ex))
        assert f["has_origin_check"] == 0

    def test_vary_referer_detected(self) -> None:
        ex = _ex(response_headers={"Vary": "Referer"})
        f = extract_features(ex, _flow(ex))
        assert f["has_referer_check"] == 1

    def test_no_referer_evidence(self) -> None:
        ex = _ex(response_headers={})
        f = extract_features(ex, _flow(ex))
        assert f["has_referer_check"] == 0


# ===========================================================================
# Endpoint sensitivity
# ===========================================================================


class TestEndpointSensitivity:
    """_compute_endpoint_sensitivity URL scoring."""

    def test_admin_high(self) -> None:
        assert _compute_endpoint_sensitivity(
            "https://example.com/admin/users"
        ) == 0.9

    def test_transfer_max(self) -> None:
        assert _compute_endpoint_sensitivity(
            "https://bank.com/transfer/funds"
        ) == 1.0

    def test_search_low(self) -> None:
        assert _compute_endpoint_sensitivity(
            "https://example.com/search?q=test"
        ) == 0.1

    def test_unknown_default(self) -> None:
        assert _compute_endpoint_sensitivity(
            "https://example.com/foobar/xyz"
        ) == 0.3

    def test_profile_medium(self) -> None:
        assert _compute_endpoint_sensitivity(
            "https://example.com/profile/edit"
        ) == 0.5


# ===========================================================================
# Content type simplification
# ===========================================================================


class TestContentType:
    """_simplify_content_type helper."""

    def test_form_urlencoded(self) -> None:
        result = _simplify_content_type(
            "application/x-www-form-urlencoded; charset=utf-8"
        )
        assert result == "application/x-www-form-urlencoded"

    def test_json(self) -> None:
        result = _simplify_content_type("application/json")
        assert result == "application/json"

    def test_unknown_defaults_to_text(self) -> None:
        result = _simplify_content_type("image/png")
        assert result == "text/plain"


# ===========================================================================
# T-232: Categorical encoding
# ===========================================================================


class TestEncodeCategoricals:
    """One-hot encoding of categorical features."""

    def test_samesite_one_hot(self) -> None:
        raw = {"has_samesite_cookie": "Lax", "http_method": "POST",
               "content_type": "application/json",
               "auth_mechanism": "cookie", "token_entropy": 3.5}
        enc = encode_categoricals(raw)

        assert enc["samesite_lax"] == 1
        assert enc["samesite_none"] == 0
        assert enc["samesite_strict"] == 0
        assert enc["samesite_absent"] == 0
        assert "has_samesite_cookie" not in enc

    def test_method_one_hot(self) -> None:
        raw = {"has_samesite_cookie": "absent",
               "http_method": "DELETE",
               "content_type": "text/plain",
               "auth_mechanism": "none"}
        enc = encode_categoricals(raw)

        assert enc["method_DELETE"] == 1
        assert enc["method_POST"] == 0
        assert enc["method_GET"] == 0
        assert "http_method" not in enc

    def test_content_type_one_hot(self) -> None:
        raw = {"has_samesite_cookie": "absent",
               "http_method": "GET",
               "content_type": "multipart/form-data",
               "auth_mechanism": "none"}
        enc = encode_categoricals(raw)

        assert enc["ct_multipart"] == 1
        assert enc["ct_json"] == 0
        assert enc["ct_form_urlencoded"] == 0
        assert enc["ct_other"] == 0

    def test_auth_one_hot(self) -> None:
        raw = {"has_samesite_cookie": "absent",
               "http_method": "GET",
               "content_type": "text/plain",
               "auth_mechanism": "header_only"}
        enc = encode_categoricals(raw)

        assert enc["auth_header_only"] == 1
        assert enc["auth_cookie"] == 0

    def test_numeric_features_preserved(self) -> None:
        raw = {"has_samesite_cookie": "absent",
               "http_method": "GET",
               "content_type": "text/plain",
               "auth_mechanism": "none",
               "token_entropy": 4.2,
               "endpoint_sensitivity": 0.8}
        enc = encode_categoricals(raw)

        assert enc["token_entropy"] == 4.2
        assert enc["endpoint_sensitivity"] == 0.8


# ===========================================================================
# T-233: Normalization
# ===========================================================================


class TestNormalizeFeatures:
    """Feature normalization."""

    def test_entropy_normalized(self) -> None:
        """Entropy 3.0 / 6.0 = 0.5."""
        f = {"token_entropy": 3.0}
        norm = normalize_features(f)
        assert norm["token_entropy"] == 0.5

    def test_entropy_zero_stays_zero(self) -> None:
        f = {"token_entropy": 0.0}
        norm = normalize_features(f)
        assert norm["token_entropy"] == 0.0

    def test_entropy_capped_at_one(self) -> None:
        """Entropy above 6.0 → capped at 1.0."""
        f = {"token_entropy": 8.0}
        norm = normalize_features(f)
        assert norm["token_entropy"] == 1.0

    def test_other_features_untouched(self) -> None:
        f = {"token_entropy": 3.0, "endpoint_sensitivity": 0.7}
        norm = normalize_features(f)
        assert norm["endpoint_sensitivity"] == 0.7
