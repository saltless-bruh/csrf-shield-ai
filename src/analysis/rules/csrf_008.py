"""CSRF-008: GET Request with Side Effects.

Detects GET requests whose URL path or query parameters suggest
state-changing operations (e.g., /delete, ?action=remove).

Ref:
    - spec/Requirements.md FR-209
    - config/rules.yaml CSRF-008 (detection_patterns)
    - spec/Tasks.md T-218
"""

from __future__ import annotations

import logging
from typing import FrozenSet, List, Tuple
from urllib.parse import parse_qs, urlparse

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)

# From config/rules.yaml CSRF-008 detection_patterns.
_DANGEROUS_URL_PATTERNS: Tuple[str, ...] = (
    "/delete",
    "/update",
    "/add",
    "/remove",
    "/transfer",
)

_DANGEROUS_QUERY_PARAMS: FrozenSet[str] = frozenset(
    {"action", "op", "do"}
)


class Csrf008(BaseRule):
    """GET Request with Side Effects.

    GET requests should be safe and idempotent (RFC 7231 §4.2.1).
    This rule detects GET requests whose URL or query string
    suggests a state-changing operation, which is a CSRF risk
    because browsers freely send GET requests cross-origin.
    """

    rule_id = "CSRF-008"
    rule_name = "GET Request with Side Effects"
    severity = Severity.HIGH

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check GET requests for state-changing URL patterns."""
        if exchange.request_method.upper() != "GET":
            return []

        parsed = urlparse(exchange.request_url)
        path_lower = parsed.path.lower()
        evidence_parts: List[str] = []

        # Check URL path for dangerous patterns
        for pattern in _DANGEROUS_URL_PATTERNS:
            if pattern in path_lower:
                evidence_parts.append(
                    f"URL path contains '{pattern}'"
                )

        # Check query parameters for action-type params
        query_params = parse_qs(parsed.query)
        for param in _DANGEROUS_QUERY_PARAMS:
            if param in query_params:
                evidence_parts.append(
                    f"Query param '{param}' = "
                    f"'{query_params[param][0]}'"
                )

        if not evidence_parts:
            return []

        return [
            self._make_finding(
                description=(
                    f"GET request to {exchange.request_url} appears "
                    f"to perform a state-changing operation."
                ),
                evidence="; ".join(evidence_parts),
                exchange=exchange,
            )
        ]
