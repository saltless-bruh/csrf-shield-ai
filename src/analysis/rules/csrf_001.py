"""CSRF-001: Missing CSRF Token in Form.

Detects state-changing requests with form-encoded or multipart bodies
that do not contain a CSRF token parameter.

Ref:
    - spec/Requirements.md FR-202
    - config/rules.yaml CSRF-001
    - spec/Tasks.md T-211
"""

from __future__ import annotations

import json
import logging
from typing import List

from src.analysis.rules.base_rule import BaseRule
from src.analysis.token_identifier import (
    identify_csrf_token,
    parse_form_params,
)
from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)

# Content types where form CSRF tokens are expected.
_FORM_CONTENT_TYPES = (
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)


class Csrf001(BaseRule):
    """Missing CSRF Token in Form.

    Triggers when a state-changing request carries a form body
    (urlencoded or multipart) but no CSRF token is identified
    by the 3-tier token identification strategy.

    Does NOT trigger for:
        - GET / HEAD requests (not state-changing)
        - JSON content-type bodies (checked by CSRF-002 header rule)
        - Requests with no body
    """

    rule_id = "CSRF-001"
    rule_name = "Missing CSRF Token in Form"
    severity = Severity.HIGH

    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Check for missing CSRF token in form body."""
        if not self.is_state_changing(exchange.request_method):
            return []

        content_type = exchange.request_content_type.lower()
        if not any(ct in content_type for ct in _FORM_CONTENT_TYPES):
            return []

        if not exchange.request_body:
            return []

        # Try to parse as JSON first — some apps send JSON
        # with a form content-type (edge case, skip).
        params = parse_form_params(exchange.request_body)
        if not params:
            return []

        token = identify_csrf_token(params)
        if token is not None:
            return []  # Token found — no finding

        return [
            self._make_finding(
                description=(
                    f"State-changing {exchange.request_method} request "
                    f"to {exchange.request_url} has a form body "
                    f"without a CSRF token parameter."
                ),
                evidence=(
                    f"Form parameters: "
                    f"{', '.join(params.keys()) or '(empty)'}"
                ),
                exchange=exchange,
            )
        ]
