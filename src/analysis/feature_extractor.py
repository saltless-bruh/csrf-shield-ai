"""Feature extraction engine for CSRF Shield AI ML pipeline.

Extracts the 14 features defined in PROPOSAL.md §9.3.2 from
``HttpExchange`` / ``SessionFlow`` objects.  Output format matches
``scripts/generate_synthetic_data.py`` column names for ML
pipeline compatibility.

Features:
    1.  has_csrf_token_in_form      (0/1)
    2.  has_csrf_token_in_header    (0/1)
    3.  has_samesite_cookie         (str: None/Lax/Strict/absent)  # "absent" when not set
    4.  has_origin_check            (0/1)
    5.  has_referer_check           (0/1)
    6.  http_method                 (str: GET/POST/PUT/DELETE/PATCH)
    7.  is_state_changing           (0/1)
    8.  content_type                (str: simplified category)
    9.  requires_auth               (0/1)
    10. token_entropy               (float, 0.0 if no token)
    11. token_changes_per_request   (0/1)
    12. response_sets_cookie        (0/1)
    13. auth_mechanism              (str: cookie/header_only/mixed/none)
    14. endpoint_sensitivity        (float 0.0–1.0)

Ref:
    - docs/proposal/PROPOSAL.md §9.3.2
    - spec/Requirements.md FR-301
    - spec/Tasks.md T-231, T-232, T-233
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.analysis.rules.base_rule import BaseRule
from src.analysis.token_identifier import (
    TokenMatch,
    extract_token_from_body,
    identify_csrf_header,
    shannon_entropy,
)
from src.input.models import HttpExchange, SessionFlow

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Endpoint sensitivity patterns (T-231)
# ------------------------------------------------------------------

# URL path substrings → sensitivity score.
# Checked in order; first match wins.
_SENSITIVITY_PATTERNS: List[Tuple[str, float]] = [
    # High sensitivity (0.8–1.0): financial / destructive
    ("/admin", 0.9),
    ("/transfer", 1.0),
    ("/payment", 1.0),
    ("/checkout", 0.9),
    ("/delete", 0.9),
    ("/withdraw", 1.0),
    ("/password", 0.8),
    # Medium sensitivity (0.4–0.6): user data mutation
    ("/settings", 0.6),
    ("/profile", 0.5),
    ("/update", 0.5),
    ("/account", 0.6),
    ("/edit", 0.5),
    ("/change", 0.5),
    ("/add", 0.4),
    ("/remove", 0.6),
    # Low sensitivity (0.0–0.2): read-only / public
    ("/search", 0.1),
    ("/view", 0.1),
    ("/public", 0.0),
    ("/static", 0.0),
    ("/api", 0.3),
]

# Default when no pattern matches.
_DEFAULT_SENSITIVITY = 0.3

# Content-type simplification map.
_CONTENT_TYPE_MAP = {
    "application/x-www-form-urlencoded": (
        "application/x-www-form-urlencoded"
    ),
    "multipart/form-data": "multipart/form-data",
    "application/json": "application/json",
    "text/plain": "text/plain",
}

# Maximum theoretical Shannon entropy for normalization (T-233).
# log₂(64) ≈ 6.0 bits/char (base64url character set).
_MAX_ENTROPY = 6.0

# Session cookie name patterns (mirrors settings.yaml).
_SESSION_COOKIE_PATTERNS = ("session", "sid", "auth")


# ==================================================================
# T-231: Main Feature Extraction
# ==================================================================


def extract_features(
    exchange: HttpExchange,
    flow: SessionFlow,
) -> Dict[str, Any]:
    """Extract the 14 ML features from a single exchange.

    Args:
        exchange: The HTTP exchange to extract features from.
        flow: The enclosing session flow (needed for
            ``token_changes_per_request`` and ``auth_mechanism``).

    Returns:
        Dict with exactly 14 keys matching PROPOSAL.md §9.3.2
        column names.  Values are raw (not one-hot encoded);
        use :func:`encode_categoricals` for ML input.

    Ref: PROPOSAL.md §9.3.2, FR-301, T-231
    """
    # -- Token identification --
    form_token = extract_token_from_body(exchange.request_body)
    header_token = identify_csrf_header(
        exchange.request_headers
    )

    # -- SameSite detection --
    samesite = _extract_samesite(exchange)

    # -- Origin / Referer checks --
    has_origin_check = _detect_origin_check(exchange)
    has_referer_check = _detect_referer_check(exchange)

    # -- Token entropy --
    token_entropy = 0.0
    if form_token is not None:
        token_entropy = shannon_entropy(form_token.value)

    # -- Token rotation (cross-exchange) --
    token_changes = _detect_token_changes(
        exchange, flow, form_token
    )

    # -- Content type simplification --
    content_type = _simplify_content_type(
        exchange.request_content_type
    )

    # -- Auth / cookies --
    requires_auth = _detect_requires_auth(exchange)
    response_sets_cookie = int(
        any(
            k.lower() == "set-cookie"
            for k in exchange.response_headers
        )
    )

    # -- Endpoint sensitivity --
    sensitivity = _compute_endpoint_sensitivity(
        exchange.request_url
    )

    return {
        "has_csrf_token_in_form": int(form_token is not None),
        "has_csrf_token_in_header": int(
            header_token is not None
        ),
        "has_samesite_cookie": samesite,
        "has_origin_check": has_origin_check,
        "has_referer_check": has_referer_check,
        "http_method": exchange.request_method.upper(),
        "is_state_changing": int(
            BaseRule.is_state_changing(exchange.request_method)
        ),
        "content_type": content_type,
        "requires_auth": requires_auth,
        "token_entropy": round(token_entropy, 4),
        "token_changes_per_request": token_changes,
        "response_sets_cookie": response_sets_cookie,
        "auth_mechanism": flow.auth_mechanism.value,
        "endpoint_sensitivity": round(sensitivity, 4),
    }


# ==================================================================
# T-232: Categorical Feature Encoding
# ==================================================================


def encode_categoricals(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    """One-hot encode categorical features for ML input.

    Converts the 4 categorical string features into binary
    columns.  The original categorical keys are removed.

    Encoding:
        ``has_samesite_cookie`` → ``samesite_none``,
        ``samesite_lax``, ``samesite_strict``, ``samesite_absent``

        ``http_method`` → ``method_GET``, ``method_POST``,
        ``method_PUT``, ``method_DELETE``, ``method_PATCH``

        ``content_type`` → ``ct_form_urlencoded``,
        ``ct_multipart``, ``ct_json``, ``ct_other``

        ``auth_mechanism`` → ``auth_cookie``,
        ``auth_header_only``, ``auth_mixed``, ``auth_none``

    Args:
        features: Raw feature dict from :func:`extract_features`.

    Returns:
        New dict with categorical keys replaced by one-hot
        columns.  Numeric features are preserved as-is.

    Ref: PROPOSAL.md §9.3.2, T-232
    """
    encoded = dict(features)

    # -- SameSite --
    ss = encoded.pop("has_samesite_cookie", "absent").lower()
    encoded["samesite_none"] = int(ss == "none")
    encoded["samesite_lax"] = int(ss == "lax")
    encoded["samesite_strict"] = int(ss == "strict")
    encoded["samesite_absent"] = int(ss == "absent")

    # -- HTTP method --
    method = encoded.pop("http_method", "GET").upper()
    for m in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        encoded[f"method_{m}"] = int(method == m)

    # -- Content type --
    ct = encoded.pop("content_type", "text/plain").lower()
    encoded["ct_form_urlencoded"] = int(
        "form-urlencoded" in ct
    )
    encoded["ct_multipart"] = int("multipart" in ct)
    encoded["ct_json"] = int("json" in ct)
    encoded["ct_other"] = int(
        not any(
            k in ct
            for k in ("form-urlencoded", "multipart", "json")
        )
    )

    # -- Auth mechanism --
    auth = encoded.pop("auth_mechanism", "none").lower()
    encoded["auth_cookie"] = int(auth == "cookie")
    encoded["auth_header_only"] = int(auth == "header_only")
    encoded["auth_mixed"] = int(auth == "mixed")
    encoded["auth_none"] = int(auth == "none")

    return encoded


# ==================================================================
# T-233: Feature Normalization
# ==================================================================


def normalize_features(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize numeric features to ML-friendly ranges.

    Currently normalizes:
        - ``token_entropy``: divide by ``_MAX_ENTROPY`` (6.0)
          to scale to [0, 1].

    Other numeric features (``endpoint_sensitivity``) are
    already in [0, 1] and do not need normalization.

    Args:
        features: Feature dict (raw or already encoded).

    Returns:
        New dict with normalized values.

    Ref: T-233
    """
    normalized = dict(features)
    entropy = normalized.get("token_entropy", 0.0)
    normalized["token_entropy"] = round(
        min(entropy / _MAX_ENTROPY, 1.0), 4
    )
    return normalized


# ==================================================================
# Internal helpers
# ==================================================================


def _extract_samesite(exchange: HttpExchange) -> str:
    """Extract SameSite value from Set-Cookie response header.

    Returns one of: ``"None"``, ``"Lax"``, ``"Strict"``,
    ``"absent"`` (when the SameSite attribute is not present).
    Only inspects session cookies.

    Note:
        ``"absent"`` matches the training data column name
        ``has_samesite_cookie_absent`` in ``models/feature_columns.json``.
    """
    set_cookie = exchange.response_headers.get(
        "set-cookie", ""
    )
    if not set_cookie:
        return "absent"

    lower = set_cookie.lower()

    # Only care about session cookies
    cookie_name = set_cookie.split("=")[0].strip().lower()
    if not any(
        pat in cookie_name
        for pat in _SESSION_COOKIE_PATTERNS
    ):
        return "absent"

    if "samesite=strict" in lower:
        return "Strict"
    if "samesite=lax" in lower:
        return "Lax"
    if "samesite=none" in lower:
        return "None"
    return "absent"


def _detect_origin_check(exchange: HttpExchange) -> int:
    """Detect if the server validates the Origin header.

    Heuristic: ``Vary: Origin`` present, or response is 4xx
    when Origin header is present.
    """
    vary = exchange.response_headers.get("vary", "")
    if "origin" in vary.lower():
        return 1

    origin = exchange.request_headers.get("origin", "")
    if origin and 400 <= exchange.response_status < 500:
        return 1

    return 0


def _detect_referer_check(exchange: HttpExchange) -> int:
    """Detect if the server validates the Referer header."""
    vary = exchange.response_headers.get("vary", "")
    return int("referer" in vary.lower())


def _detect_token_changes(
    exchange: HttpExchange,
    flow: SessionFlow,
    current_token: Optional[TokenMatch],
) -> int:
    """Detect if CSRF tokens rotate across requests.

    Returns 1 if tokens change (good), 0 if static or no token.
    Requires ≥ 2 state-changing exchanges to compare.
    """
    if current_token is None:
        return 0

    for other in flow.exchanges:
        if other is exchange:
            continue
        if not BaseRule.is_state_changing(other.request_method):
            continue
        if not other.request_body:
            continue

        other_token = extract_token_from_body(other.request_body)

        if other_token is None:
            continue

        # Found another token — check if different
        if other_token.value != current_token.value:
            return 1  # Tokens rotate
        else:
            return 0  # Same token — static

    # Only one state-changing exchange — can't determine
    # rotation. Return 0 (conservative — treat unknown as
    # potentially static rather than giving false confidence).
    return 0


def _simplify_content_type(raw: str) -> str:
    """Simplify a Content-Type header to a canonical category."""
    lower = raw.lower().split(";")[0].strip()
    for key, value in _CONTENT_TYPE_MAP.items():
        if key in lower:
            return value
    return "text/plain"


def _compute_endpoint_sensitivity(url: str) -> float:
    """Score endpoint sensitivity from URL path patterns.

    Args:
        url: Full request URL.

    Returns:
        Float in [0.0, 1.0] where higher = more sensitive.
    """
    path = urlparse(url).path.lower()
    for pattern, score in _SENSITIVITY_PATTERNS:
        if pattern in path:
            return score
    return _DEFAULT_SENSITIVITY


def _detect_requires_auth(exchange: HttpExchange) -> int:
    """Detect if the exchange requires authentication.

    Heuristic: session cookies are present in the request.
    """
    for name in exchange.request_cookies:
        if any(
            pat in name.lower()
            for pat in _SESSION_COOKIE_PATTERNS
        ):
            return 1
    return 0
