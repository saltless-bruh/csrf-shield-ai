"""CSRF-004: Static CSRF Token (non-rotating).

Detects when the same CSRF token value is used across multiple
state-changing requests in a session flow, indicating the token
does not rotate per-request.

Ref:
    - spec/Requirements.md FR-205
    - config/rules.yaml CSRF-004
    - spec/Tasks.md T-214
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.analysis.token_identifier import (
    extract_token_from_body,
)
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)


class Csrf004(BaseRule):
    """Static CSRF Token (non-rotating).

    This is a **cross-exchange** rule.  It compares token values
    across all state-changing exchanges in the flow.  If the same
    token value appears in ≥ 2 exchanges, it fires on each exchange
    that shares the duplicate token.

    Severity: CRITICAL — a static token can be trivially replayed.
    """

    rule_id = "CSRF-004"
    rule_name = "Static CSRF Token"
    severity = Severity.CRITICAL

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check if this exchange's token is reused elsewhere in the flow."""
        if not self.is_state_changing(exchange.request_method):
            return []

        if not exchange.request_body:
            return []

        token = extract_token_from_body(exchange.request_body)
        if token is None:
            return []

        # Count how many OTHER state-changing exchanges in the flow
        # share the same token value.
        reuse_count = 0
        for other in flow.exchanges:
            if other is exchange:
                continue
            if not self.is_state_changing(other.request_method):
                continue
            if not other.request_body:
                continue
            other_token = extract_token_from_body(other.request_body)
            if other_token and other_token.value == token.value:
                reuse_count += 1

        if reuse_count == 0:
            return []

        return [
            self._make_finding(
                description=(
                    f"CSRF token '{token.name}' has the same value "
                    f"across {reuse_count + 1} state-changing requests "
                    f"in this session — the token is not rotating."
                ),
                evidence=(
                    f"Static token value: {token.value!r}"
                ),
                exchange=exchange,
            )
        ]
