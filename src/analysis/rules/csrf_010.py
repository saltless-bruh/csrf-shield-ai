"""CSRF-010: JSON Endpoint Without CORS.

Detects JSON API endpoints (state-changing) that lack proper CORS
restrictions, making them potentially exploitable via cross-origin
requests.

Ref:
    - spec/Requirements.md FR-211
    - config/rules.yaml CSRF-010
    - spec/Tasks.md T-220
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf010(BaseRule):
    """JSON Endpoint Without CORS.

    Fires when a state-changing request to a JSON endpoint does not
    have proper CORS restrictions.  Specifically:

    1. The response Content-Type is ``application/json``.
    2. ``Access-Control-Allow-Origin`` is either missing
       (no CORS policy) or set to ``*`` (wildcard — any origin).

    A restrictive ACAO (specific origin) is considered safe.
    """

    rule_id = "CSRF-010"
    rule_name = "JSON Endpoint Without CORS"
    severity = Severity.MEDIUM

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check JSON endpoints for CORS restrictions."""
        if not self.is_state_changing(exchange.request_method):
            return []

        # Check if this is a JSON endpoint
        resp_ct = exchange.response_headers.get(
            "Content-Type", ""
        ).lower()
        if "application/json" not in resp_ct:
            return []

        acao = exchange.response_headers.get(
            "Access-Control-Allow-Origin", ""
        )

        # A specific origin is considered safe
        if acao and acao != "*":
            return []

        issue = "missing" if not acao else "set to '*'"
        return [
            self._make_finding(
                description=(
                    f"JSON endpoint {exchange.request_url} has "
                    f"Access-Control-Allow-Origin {issue} — "
                    f"may be exploitable cross-origin."
                ),
                evidence=(
                    f"Response Content-Type: {resp_ct}, "
                    f"ACAO: {acao or '(absent)'}"
                ),
                exchange=exchange,
            )
        ]
