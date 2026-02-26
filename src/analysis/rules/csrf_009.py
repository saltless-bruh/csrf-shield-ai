"""CSRF-009: Missing Referer Validation.

Detects state-changing requests where the server does not appear
to check the Referer header (no Vary: Referer and 2xx response).

Ref:
    - spec/Requirements.md FR-210
    - config/rules.yaml CSRF-009
    - spec/Tasks.md T-219
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf009(BaseRule):
    """Missing Referer Validation.

    Heuristic: if a state-changing request succeeds (2xx) and the
    response does not include ``Vary: Referer``, the server
    likely does not validate the Referer header.

    This is a LOW severity supplementary check — Referer validation
    alone is not sufficient for CSRF protection, but its absence
    is a weak signal.
    """

    rule_id = "CSRF-009"
    rule_name = "Missing Referer Validation"
    severity = Severity.LOW

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check for evidence of Referer validation."""
        if not self.is_state_changing(exchange.request_method):
            return []

        # Only flag on successful responses
        if not (200 <= exchange.response_status < 300):
            return []

        vary = exchange.response_headers.get("Vary", "")
        if "referer" in vary.lower():
            return []  # Server is Referer-aware

        return [
            self._make_finding(
                description=(
                    f"State-changing {exchange.request_method} request "
                    f"to {exchange.request_url} succeeded without "
                    f"evidence of Referer header validation."
                ),
                evidence=(
                    f"Response status: {exchange.response_status}, "
                    f"Vary header: {vary or '(absent)'}"
                ),
                exchange=exchange,
            )
        ]
