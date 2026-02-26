"""CSRF-002: Missing CSRF Token in Header.

Detects state-changing requests that do not include a custom
anti-CSRF header (X-CSRF-Token, X-XSRF-Token, etc.).

Ref:
    - spec/Requirements.md FR-203
    - config/rules.yaml CSRF-002
    - spec/Tasks.md T-212
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.analysis.token_identifier import identify_csrf_header
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf002(BaseRule):
    """Missing CSRF Token in Header.

    Triggers when a state-changing request does not carry any
    recognised anti-CSRF header.  This covers the double-submit
    header pattern used by Angular, Django AJAX, and similar
    frameworks.

    Does NOT trigger for GET / HEAD requests.
    """

    rule_id = "CSRF-002"
    rule_name = "Missing CSRF Token in Header"
    severity = Severity.MEDIUM

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check for missing anti-CSRF header."""
        if not self.is_state_changing(exchange.request_method):
            return []

        header_match = identify_csrf_header(exchange.request_headers)
        if header_match is not None:
            return []  # Anti-CSRF header present

        return [
            self._make_finding(
                description=(
                    f"State-changing {exchange.request_method} request "
                    f"to {exchange.request_url} has no anti-CSRF header."
                ),
                evidence=(
                    f"Request headers present: "
                    f"{', '.join(exchange.request_headers.keys())}"
                ),
                exchange=exchange,
            )
        ]
