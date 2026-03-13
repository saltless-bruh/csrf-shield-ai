"""Abstract base class for all CSRF static analysis rules.

Every rule in ``src/analysis/rules/csrf_*.py`` subclasses :class:`BaseRule`
and implements :meth:`analyze`.  The static analyzer orchestrator
(``static_analyzer.py``, Phase 2.4) loads enabled rules from
``config/rules.yaml`` and calls ``analyze()`` on each exchange.

Ref:
    - spec/Design.md §2.2 (Phase 2 responsibilities)
    - spec/Tasks.md T-211–T-220
    - .github/instructions/coding_standards.instructions.md §3.1
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from src.input.models import Finding, HttpExchange, SessionFlow, Severity

logger = logging.getLogger(__name__)

# HTTP methods that are considered state-changing (CSRF-relevant).
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


class BaseRule(ABC):
    """Abstract base class for CSRF detection rules.

    Subclasses must set the three class-level attributes and implement
    :meth:`analyze`.

    Attributes:
        rule_id: Unique rule identifier (e.g., ``"CSRF-001"``).
        rule_name: Human-readable name matching ``config/rules.yaml``.
        severity: Default severity from ``config/rules.yaml``.
    """

    rule_id: str
    rule_name: str
    severity: Severity

    @abstractmethod
    def analyze(
        self,
        exchange: HttpExchange,
        flow: SessionFlow,
    ) -> List[Finding]:
        """Run this rule against a single exchange.

        Args:
            exchange: The HTTP exchange to inspect.
            flow: The enclosing session flow (for cross-exchange rules
                like CSRF-004 that compare tokens across requests).

        Returns:
            A list of :class:`Finding` objects.  Return an empty list
            if the rule does not trigger for this exchange.
        """

    # ------------------------------------------------------------------
    # Shared helpers available to all rules
    # ------------------------------------------------------------------

    @staticmethod
    def is_state_changing(method: str) -> bool:
        """Return True if the HTTP method is state-changing.

        State-changing methods (POST, PUT, DELETE, PATCH) are the
        primary targets for CSRF protection analysis.  GET and HEAD
        are not state-changing by HTTP semantics.

        Args:
            method: HTTP method string (case-insensitive).

        Returns:
            True if the method is in STATE_CHANGING_METHODS.
        """
        return method.upper() in STATE_CHANGING_METHODS

    def _make_finding(
        self,
        description: str,
        evidence: str,
        exchange: HttpExchange,
    ) -> Finding:
        """Create a Finding using this rule's metadata.

        Convenience method that pre-fills rule_id, rule_name, and
        severity from the class attributes.

        Args:
            description: What was found (specific to this instance).
            evidence: Supporting data from the exchange.
            exchange: The exchange that triggered the finding.

        Returns:
            A populated :class:`Finding` instance.
        """
        return Finding(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            description=description,
            evidence=evidence,
            exchange=exchange,
        )
