"""CSRF-011: Non-Cookie Auth (CSRF N/A).

Short-circuit rule for header-only authentication.  This rule is
primarily triggered by the ``StaticAnalyzer._short_circuit()``
method rather than per-exchange analysis; however, a module must
exist so that ``load_rules()`` can instantiate it from
``config/rules.yaml``.

Ref:
    - spec/Requirements.md FR-212
    - config/rules.yaml CSRF-011
    - docs/proposal/PROPOSAL.md §8.4
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf011(BaseRule):
    """Non-Cookie Auth (CSRF N/A).

    When all requests use header-based authentication exclusively
    (Bearer token / API key) and no session cookies are set, CSRF
    risk is inherently low.  The orchestrator short-circuits before
    running individual rules, but this class exists for rule-loading
    completeness and can produce a finding if called directly.
    """

    rule_id = "CSRF-011"
    rule_name = "Non-Cookie Auth (CSRF N/A)"
    severity = Severity.INFO

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Return an INFO finding if the flow uses header-only auth.

        Normally the orchestrator handles this via short-circuit,
        but this method is provided for completeness.
        """
        from src.input.models import AuthMechanism

        if flow.auth_mechanism != AuthMechanism.HEADER_ONLY:
            return []

        return [
            self._make_finding(
                description=(
                    "Session uses header-based authentication "
                    "exclusively. CSRF risk is inherently low."
                ),
                evidence=(
                    f"Auth mechanism: {flow.auth_mechanism.value}"
                ),
                exchange=exchange,
            )
        ]
