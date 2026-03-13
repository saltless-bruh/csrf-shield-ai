"""CSRF token identification engine for CSRF Shield AI.

Implements the three-tier token identification strategy described in
PROPOSAL.md §9.3.1 (FR-302). This module is a prerequisite for:

  - CSRF-001: Missing CSRF Token in Form (needs ``identify_csrf_token``)
  - CSRF-003: Predictable Token (needs ``shannon_entropy``)
  - CSRF-004: Static Token (needs ``identify_csrf_token`` across exchanges)
  - Feature extraction: ``token_entropy`` and ``has_csrf_token_in_form``
    features (FR-301)

Strategy overview (Tier 1 → Tier 2 → Tier 3):
  1. **Exact match** — param name matches a known framework token name
     (Django, Laravel, Rails, ASP.NET, Spring generic).
  2. **Fuzzy match** — param name contains a CSRF/forgery keyword.
  3. **Entropy detection** — value is long (≥ 16 chars) and high-entropy
     (≥ 3.5 bits/char), suggesting a cryptographic secret.

Thresholds for Tier 3 are configurable via ``config/settings.yaml``
under ``token_identification:`` (see ``coding_standards.instructions.md``
§2.3).

Ref:
    - docs/proposal/PROPOSAL.md §9.3.1
    - spec/Requirements.md FR-302
    - spec/Tasks.md T-201, T-202, T-203
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Final, FrozenSet, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# T-203: Known Token Name Registry
# ---------------------------------------------------------------------------

# Tier 1: Exact-match registry for well-known CSRF token parameter names.
# All names are stored in lowercase; the identification function performs
# case-insensitive matching via ``name.lower()``.
#
# Framework coverage:
#   Django              → csrfmiddlewaretoken
#   Laravel             → _token
#   Rails               → authenticity_token
#   ASP.NET             → __RequestVerificationToken, RequestVerificationToken
#   Spring (generic)    → _csrf, csrf
#   Generic / OWASP     → csrf_token, xsrf_token, anti_forgery_token, xsrf
CSRF_TOKEN_NAMES: Final[FrozenSet[str]] = frozenset(
    {
        "csrf_token",
        "csrfmiddlewaretoken",  # Django
        "_token",  # Laravel
        "_csrf",  # generic / Express.js csurf
        "authenticity_token",  # Rails
        "__requestverificationtoken",  # ASP.NET MVC / Razor
        "requestverificationtoken",  # ASP.NET alternative casing
        "xsrf_token",  # generic
        "anti_forgery_token",  # generic
        "csrf",  # minimalist naming
        "xsrf",  # minimalist naming
    }
)

# Tier 2: Substring keywords that strongly suggest a CSRF token parameter
# even when the full name is custom (e.g., ``my_csrf_field``, ``xsrf_val``).
CSRF_TOKEN_KEYWORDS: Final[Tuple[str, ...]] = ("csrf", "xsrf", "forgery")

# Known request headers used as anti-CSRF (double-submit pattern).
# These are *not* the ``Authorization`` header (that is auth detection);
# these are explicit anti-CSRF headers added by JS frameworks.
CSRF_HEADER_NAMES: Final[FrozenSet[str]] = frozenset(
    {
        "x-csrf-token",  # Sinatra, Express csurf, Angular
        "x-xsrf-token",  # Angular default
        "x-csrftoken",  # Django AJAX convention
        "x-requested-with",  # jQuery AJAX double-submit
    }
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenMatch:
    """Result of a successful CSRF token identification.

    Attributes:
        name: The parameter or header name that was identified as the token.
        value: The raw token value (may be empty string if header is present
            but carries no value, though that is unusual).
        tier: Which identification tier produced the match (1, 2, or 3),
            or 0 for a header match (separate flow).
        source: Where the token was found — ``"form"`` for body parameters,
            ``"header"`` for request headers.

    Ref: docs/proposal/PROPOSAL.md §9.3.1, spec/Tasks.md T-201
    """

    name: str
    value: str
    tier: int  # 0 = header, 1 = exact, 2 = fuzzy, 3 = entropy
    source: str  # "form" | "header"


# ---------------------------------------------------------------------------
# T-202: Shannon Entropy Calculation
# ---------------------------------------------------------------------------


def shannon_entropy(value: str) -> float:
    """Calculate the per-character Shannon entropy of a string.

    Uses the standard formula:
        H = -∑ p(x) × log₂(p(x))  for each unique character x.

    A value with all identical characters has H = 0.0.
    A uniformly distributed value over 64 symbols (e.g., base64url) has
    H ≈ 6.0 bits/char.

    Args:
        value: The string whose entropy is to be calculated.

    Returns:
        Shannon entropy in bits per character.  Returns ``0.0`` for an
        empty string or a string containing only one unique character.

    Ref: docs/proposal/PROPOSAL.md §9.3.1 (Tier 3), spec/Tasks.md T-202
    """
    if not value:
        return 0.0

    length = len(value)
    # Count occurrences of each character.
    counts: Dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1

    entropy = 0.0
    for count in counts.values():
        probability = count / length
        entropy -= probability * math.log2(probability)

    return entropy


# ---------------------------------------------------------------------------
# T-201: Three-Tier Token Identification
# ---------------------------------------------------------------------------


def identify_csrf_token(
    params: Dict[str, str],
    *,
    entropy_threshold: Optional[float] = None,
    min_token_length: Optional[int] = None,
) -> Optional[TokenMatch]:
    """Identify the CSRF token parameter from form body parameters.

    Implements the 3-tier identification strategy from PROPOSAL.md §9.3.1
    (FR-302).  Returns the *first* match found, preferring lower tier numbers
    (higher confidence).  Returns ``None`` if no CSRF token is detected.

    Strategy:
        **Tier 1 — Exact name match** (highest confidence)
            The parameter name (lowercased) matches a known framework CSRF
            token name in ``CSRF_TOKEN_NAMES``.  Covers Django, Laravel,
            Rails, ASP.NET, Spring, and generic naming conventions (T-203).

        **Tier 2 — Fuzzy keyword match** (medium confidence)
            The parameter name (lowercased) contains one of the keywords in
            ``CSRF_TOKEN_KEYWORDS`` (``"csrf"``, ``"xsrf"``, ``"forgery"``).
            Catches custom field names such as ``my_csrf_field``.

        **Tier 3 — High-entropy string detection** (fallback)
            The parameter value is at least ``min_token_length`` characters
            long *and* its Shannon entropy is at least ``entropy_threshold``
            bits per character.  This catches custom implementations where
            the field name gives no hint (e.g., ``hidden_val``).

    Args:
        params: Dict mapping form parameter names to their values, as
            produced by the HAR parser's body parsing utilities.
        entropy_threshold: Minimum Shannon entropy (bits/char) required
            for a Tier 3 match.  Configurable via ``settings.yaml``
            ``token_identification.entropy_threshold``.  Default: 3.5.
        min_token_length: Minimum value length (characters) required before
            Tier 3 entropy is considered.  Configurable via ``settings.yaml``
            ``token_identification.min_token_length``.  Default: 16.

    Returns:
        A :class:`TokenMatch` if a token is found, else ``None``.
        When ``None`` is returned:
            - ``has_csrf_token_in_form`` feature → ``False``
            - ``token_entropy`` feature → ``0.0``

    Ref: docs/proposal/PROPOSAL.md §9.3.1, spec/Requirements.md FR-302,
         spec/Tasks.md T-201
    """
    if not params:
        return None

    from src.config import SETTINGS
    token_settings = SETTINGS.get("token_identification", {})
    if entropy_threshold is None:
        entropy_threshold = token_settings.get("entropy_threshold", 3.5)
    if min_token_length is None:
        min_token_length = token_settings.get("min_token_length", 16)

    # ------------------------------------------------------------------
    # Tier 1: Exact name match
    # ------------------------------------------------------------------
    for name, value in params.items():
        if name.lower() in CSRF_TOKEN_NAMES:
            logger.debug("Token identified via Tier 1 (exact): %s", name)
            return TokenMatch(name=name, value=value, tier=1, source="form")

    # ------------------------------------------------------------------
    # Tier 2: Fuzzy keyword match
    # ------------------------------------------------------------------
    for name, value in params.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in CSRF_TOKEN_KEYWORDS):
            logger.debug("Token identified via Tier 2 (fuzzy): %s", name)
            return TokenMatch(name=name, value=value, tier=2, source="form")

    # ------------------------------------------------------------------
    # Tier 3: High-entropy string detection
    # ------------------------------------------------------------------
    for name, value in params.items():
        if (len(value) >= min_token_length
                and shannon_entropy(value) >= entropy_threshold):
            logger.debug(
                "Token identified via Tier 3 (entropy=%.2f): %s",
                shannon_entropy(value),
                name,
            )
            return TokenMatch(name=name, value=value, tier=3, source="form")

    return None


def identify_csrf_header(headers: Dict[str, str]) -> Optional[TokenMatch]:
    """Identify anti-CSRF tokens delivered via request headers.

    Checks for the presence of known anti-CSRF headers (double-submit
    header pattern).  Header matching is case-insensitive.

    Common headers:
        - ``X-CSRF-Token``   — Sinatra, Express csurf, Angular (pre-v4)
        - ``X-XSRF-Token``   — Angular (default HttpClient header)
        - ``X-CSRFToken``    — Django AJAX convention
        - ``X-Requested-With`` — jQuery AJAX double-submit (weaker signal)

    Args:
        headers: Dict of request header names → values (case may vary).

    Returns:
        A :class:`TokenMatch` with ``source="header"`` and ``tier=0`` if a
        known anti-CSRF header is found, else ``None``.

    Ref: docs/proposal/PROPOSAL.md §9.3.1, spec/Requirements.md FR-302
    """
    for name, value in headers.items():
        if name.lower() in CSRF_HEADER_NAMES:
            logger.debug("CSRF header identified: %s", name)
            return TokenMatch(name=name, value=value, tier=0, source="header")

    return None


# ---------------------------------------------------------------------------
# Convenience: cached parsing for performance
# ---------------------------------------------------------------------------


@lru_cache(maxsize=2048)
def extract_token_from_body(body: Optional[str]) -> Optional[TokenMatch]:
    """Extract a CSRF token from a raw request body with caching.

    Solves the O(N^2) performance issue in cross-exchange rules (CSRF-004)
    and feature extraction by caching the (expensive) entropy calculation and
    parsing for identical request bodies.
    """
    if not body:
        return None
    params = parse_form_params(body)
    return identify_csrf_token(params)


# ---------------------------------------------------------------------------
# Convenience: parse form body into params dict
# ---------------------------------------------------------------------------


def parse_form_params(body: Optional[str]) -> Dict[str, str]:
    """Parse an ``application/x-www-form-urlencoded`` body string into a dict.

    Handles URL-encoded bodies as produced by the HAR parser.  If the body
    is ``None`` or empty, returns an empty dict.  Duplicate keys are
    overwritten by the last occurrence (consistent with HTML form behaviour).

    Args:
        body: Raw URL-encoded body string
            (e.g., ``"name=test&csrf_token=abc"``).

    Returns:
        Dict mapping parameter names to their decoded values.
    """
    if not body:
        return {}

    from urllib.parse import parse_qs

    # ``parse_qs`` returns lists per key; take the last value for each.
    parsed = parse_qs(body, keep_blank_values=True)
    return {k: v[-1] for k, v in parsed.items()}
