"""CSRF-003: Predictable CSRF Token.

Detects CSRF tokens with low Shannon entropy, suggesting they are
predictable and therefore bypassable.

Ref:
    - spec/Requirements.md FR-204
    - config/rules.yaml CSRF-003 (threshold: < 3.0 bits/char)
    - spec/Tasks.md T-213
"""

from __future__ import annotations

import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.analysis.token_identifier import (
    identify_csrf_token,
    parse_form_params,
    shannon_entropy,
)
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)

# Per rules.yaml CSRF-003: "Token has low entropy (< 3.0 bits/char)."
_LOW_ENTROPY_THRESHOLD = 3.0


class Csrf003(BaseRule):
    """Predictable CSRF Token (low entropy).

    Triggers when a CSRF token IS present but its Shannon entropy
    is below the threshold (< 3.0 bits/char), suggesting it could
    be predicted or brute-forced.

    Does NOT trigger if:
        - No token is found (that is CSRF-001's job)
        - Request is not state-changing
    """

    rule_id = "CSRF-003"
    rule_name = "Predictable CSRF Token"
    severity = Severity.HIGH

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check token entropy if a token is found."""
        if not self.is_state_changing(exchange.request_method):
            return []

        if not exchange.request_body:
            return []

        params = parse_form_params(exchange.request_body)
        token = identify_csrf_token(params)
        if token is None:
            return []  # No token → CSRF-001 handles this

        entropy = shannon_entropy(token.value)
        if entropy >= _LOW_ENTROPY_THRESHOLD:
            return []  # Entropy is acceptable

        return [
            self._make_finding(
                description=(
                    f"CSRF token '{token.name}' has low entropy "
                    f"({entropy:.2f} bits/char < {_LOW_ENTROPY_THRESHOLD}), "
                    f"suggesting it may be predictable."
                ),
                evidence=(
                    f"Token value: {token.value!r} "
                    f"(entropy={entropy:.2f} bits/char)"
                ),
                exchange=exchange,
            )
        ]
