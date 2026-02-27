"""Heuristic boost rules for CSRF probability adjustment.

Applies post-ML heuristic rules that boost or reduce the raw
ML probability based on static analysis findings and URL context.

Per PROPOSAL.md §9.6, these rules are NEVER called for
``header_only`` auth sessions (short-circuited in Phase 2).

Ref:
    - docs/proposal/PROPOSAL.md §9.6
    - spec/Tasks.md T-322
    - spec/Requirements.md FR-305
"""

from __future__ import annotations

import logging
import re
from typing import List, Set
from urllib.parse import parse_qs, urlparse

from src.input.models import Finding

logger = logging.getLogger(__name__)

# Sensitive endpoint path patterns (PROPOSAL §9.6).
_SENSITIVE_PATHS: List[str] = [
    "/admin",
    "/transfer",
    "/delete",
    "/password",
    "/update",
    "/remove",
    "/add",
    "/settings",
    "/payment",
    "/checkout",
    "/account",
]

# Query parameter names that suggest state-changing GET (PROPOSAL §9.6).
_ACTION_PARAMS: Set[str] = {"action", "op", "do", "cmd"}

# Protection-indicating rule IDs for defense-in-depth.
_PROTECTION_RULES: Set[str] = {
    "CSRF-001",  # has form token
    "CSRF-002",  # has header token
    "CSRF-005",  # has SameSite cookie
    "CSRF-007",  # has Origin check
    "CSRF-009",  # has Referer check
}


def apply_heuristics(
    ml_probability: float,
    static_findings: List[Finding],
    url: str,
    http_method: str,
) -> float:
    """Apply heuristic boost/reduce rules to ML probability.

    PRECONDITION: This function is NEVER called for 'header_only'
    auth sessions. Those are short-circuited in the orchestrator.

    Rules (per PROPOSAL §9.6):
        1. CSRF-004 (static token) → floor at 0.95
        2. Sensitive endpoint → ×1.2
        3. GET with action query params → ×1.3
        4. 2+ protections → ×0.6 (defense in depth)

    Args:
        ml_probability: Raw ML probability in [0.0, 1.0].
        static_findings: Findings from static analysis.
        url: The request URL.
        http_method: HTTP method (GET, POST, etc.).

    Returns:
        Adjusted probability, clamped to [0.0, 1.0].
    """
    score = ml_probability
    finding_ids = {f.rule_id for f in static_findings}

    # Rule 1: Critical static findings override ML.
    if "CSRF-004" in finding_ids:
        score = max(score, 0.95)
        logger.debug("CSRF-004 boost → %.2f", score)

    # Rule 2: Sensitive endpoint boost.
    if _is_sensitive_endpoint(url):
        score *= 1.2
        logger.debug("Sensitive endpoint boost → %.2f", score)

    # Rule 3: GET with state-changing query params.
    if http_method.upper() == "GET" and _has_action_params(url):
        score *= 1.3
        logger.debug("GET action params boost → %.2f", score)

    # Rule 4: Multiple protections reduce risk.
    protection_count = _count_protections(finding_ids)
    if protection_count >= 2:
        score *= 0.6
        logger.debug(
            "Defense-in-depth (%d protections) → %.2f",
            protection_count,
            score,
        )

    return _clamp(score, 0.0, 1.0)


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------


def _is_sensitive_endpoint(url: str) -> bool:
    """Check if URL path matches a sensitive endpoint pattern."""
    path = urlparse(url).path.lower()
    return any(pattern in path for pattern in _SENSITIVE_PATHS)


def _has_action_params(url: str) -> bool:
    """Check if URL has state-changing query parameters."""
    query = urlparse(url).query
    if not query:
        return False
    params = parse_qs(query)
    return bool(_ACTION_PARAMS & set(params.keys()))


def _count_protections(finding_ids: Set[str]) -> int:
    """Count how many protection-absence findings are NOT present.

    If a protection-absence rule (e.g., CSRF-001 = missing token)
    is NOT in findings, that means the protection IS present.

    Returns:
        Number of protections detected (0–5).
    """
    # Each of these rules fires when protection is ABSENT.
    # If the rule is NOT in findings → protection is present.
    return sum(
        1 for rule_id in _PROTECTION_RULES
        if rule_id not in finding_ids
    )


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to [low, high]."""
    return max(low, min(high, value))
