"""CSRF-007: No Origin Header Validation.

Detects state-changing requests where the server does not appear
to validate the Origin header (response is 2xx despite a
cross-origin request).

Ref:
    - spec/Requirements.md FR-208
    - config/rules.yaml CSRF-007
    - spec/Tasks.md T-217
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf007(BaseRule):
    """No Origin Header Validation.

    Heuristic: if the request carries an ``Origin`` header and the
    server responds with ``2xx``, we infer the Origin was not
    rejected.  Servers that validate the Origin should respond with
    ``403`` or ``400`` for untrusted origins or include
    ``Vary: Origin``.

    The rule only fires on state-changing requests.  If no
    ``Origin`` header is present, the rule cannot determine
    whether validation exists — so it does NOT trigger.
    """

    rule_id = "CSRF-007"
    rule_name = "No Origin Header Validation"
    severity = Severity.MEDIUM

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check if the server appears to validate Origin."""
        if not self.is_state_changing(exchange.request_method):
            return []

        origin = exchange.request_headers.get("origin", "")
        if not origin:
            return []  # Can't tell without an Origin header

        # If the server returned a client error, it likely rejected
        # the cross-origin request — no finding.
        status = exchange.response_status
        if 400 <= status < 500:
            return []

        # Check for ``Vary: Origin`` which indicates server is
        # Origin-aware.
        vary = exchange.response_headers.get("vary", "")
        if "origin" in vary.lower():
            return []

        return [
            self._make_finding(
                description=(
                    f"State-changing {exchange.request_method} request "
                    f"to {exchange.request_url} with Origin header "
                    f"'{origin}' received a {status} response — "
                    f"server may not validate Origin."
                ),
                evidence=(
                    f"Origin: {origin}, "
                    f"Response status: {status}, "
                    f"Vary header: {vary or '(absent)'}"
                ),
                exchange=exchange,
            )
        ]
