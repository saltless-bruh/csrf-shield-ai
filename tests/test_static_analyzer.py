"""Unit and integration tests for the static analysis orchestrator.

Tests cover rule loading, flow analysis, short-circuit logic,
and HAR → parse → static analysis → findings integration.

Ref:
    - src/analysis/static_analyzer.py
    - spec/Tasks.md T-241, T-242, T-243
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pytest

from src.analysis.rules.base_rule import BaseRule
from src.analysis.static_analyzer import (
    StaticAnalysisOutput,
    StaticAnalyzer,
    load_rules,
    _module_to_class_name,
)
from src.input.har_parser import parse_har_file
from src.input.models import (
    AuthMechanism,
    HttpExchange,
    SessionFlow,
    Severity,
)


# ===========================================================================
# Test helpers
# ===========================================================================


def _ex(
    method: str = "POST",
    url: str = "https://example.com/update",
    request_headers: Optional[Dict[str, str]] = None,
    request_cookies: Optional[Dict[str, str]] = None,
    request_body: Optional[str] = None,
    content_type: str = "application/x-www-form-urlencoded",
    response_status: int = 200,
    response_headers: Optional[Dict[str, str]] = None,
) -> HttpExchange:
    return HttpExchange(
        request_method=method,
        request_url=url,
        request_headers=request_headers or {},
        request_cookies=request_cookies or {"session_id": "abc"},
        request_body=request_body,
        request_content_type=content_type,
        response_status=response_status,
        response_headers=response_headers or {},
        response_body=None,
        timestamp=datetime(2026, 2, 26, 12, 0, 0),
    )


def _flow(
    *exchanges: HttpExchange,
    auth: AuthMechanism = AuthMechanism.COOKIE,
) -> SessionFlow:
    return SessionFlow(
        session_id="test",
        exchanges=list(exchanges),
        auth_mechanism=auth,
    )


# ===========================================================================
# T-242: Rule Loading
# ===========================================================================


class TestLoadRules:
    """Tests for rule loading from rules.yaml."""

    def test_load_rules_from_default_config(self) -> None:
        """All enabled rules from config/rules.yaml are loaded."""
        rules = load_rules()
        # rules.yaml has 11 rules, all enabled
        assert len(rules) == 11

    def test_all_rules_are_base_rule_subclass(self) -> None:
        """Every loaded rule is a BaseRule instance."""
        rules = load_rules()
        for rule in rules:
            assert isinstance(rule, BaseRule), (
                f"{rule} is not a BaseRule"
            )

    def test_rule_ids_match_config(self) -> None:
        """Loaded rule IDs match the YAML config order."""
        rules = load_rules()
        ids = [r.rule_id for r in rules]
        assert "CSRF-001" in ids
        assert "CSRF-011" in ids

    def test_module_to_class_name(self) -> None:
        """Module name → class name conversion."""
        assert _module_to_class_name("csrf_001") == "Csrf001"
        assert _module_to_class_name("csrf_010") == "Csrf010"
        assert _module_to_class_name("csrf_011") == "Csrf011"


# ===========================================================================
# T-241: StaticAnalyzer
# ===========================================================================


class TestStaticAnalyzer:
    """Tests for the StaticAnalyzer orchestrator."""

    def test_analyzer_initializes_with_rules(self) -> None:
        """StaticAnalyzer loads rules on init."""
        analyzer = StaticAnalyzer()
        assert len(analyzer.rules) > 0

    def test_analyze_vulnerable_flow_produces_findings(self) -> None:
        """A flow with no CSRF protections → findings."""
        ex = _ex(
            method="POST",
            url="https://example.com/transfer",
            request_body="amount=5000&to=attacker",
            response_headers={
                "Set-Cookie": "session_id=abc; Path=/",
                "Content-Type": "application/json",
            },
        )
        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(_flow(ex))

        assert isinstance(output, StaticAnalysisOutput)
        assert len(output.findings) > 0
        assert not output.short_circuited

    def test_analyze_flow_extracts_features(self) -> None:
        """Feature vectors produced for each exchange."""
        ex = _ex(request_body="data=x")
        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(_flow(ex))

        assert len(output.feature_vectors) == 1
        key = list(output.feature_vectors.keys())[0]
        assert "has_csrf_token_in_form" in output.feature_vectors[key]

    def test_analyze_multiple_exchanges(self) -> None:
        """Multiple exchanges → multiple feature vectors."""
        ex1 = _ex(
            url="https://example.com/a",
            request_body="data=1",
        )
        ex2 = _ex(
            url="https://example.com/b",
            request_body="data=2",
        )
        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(_flow(ex1, ex2))

        assert len(output.feature_vectors) == 2

    def test_short_circuit_header_only_auth(self) -> None:
        """HEADER_ONLY auth → CSRF-011 finding, rules skipped."""
        ex = _ex(
            method="GET",
            request_headers={"Authorization": "Bearer tok"},
            request_cookies={},
        )
        flow = _flow(ex, auth=AuthMechanism.HEADER_ONLY)

        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(flow)

        assert output.short_circuited is True
        assert len(output.findings) == 1
        assert output.findings[0].rule_id == "CSRF-011"
        assert output.findings[0].severity == Severity.INFO
        assert output.feature_vectors == {}

    def test_short_circuit_empty_flow(self) -> None:
        """HEADER_ONLY auth with no exchanges → no findings."""
        flow = SessionFlow(
            session_id="empty",
            exchanges=[],
            auth_mechanism=AuthMechanism.HEADER_ONLY,
        )
        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(flow)

        assert output.short_circuited is True
        assert len(output.findings) == 0

    def test_protected_flow_fewer_findings(self) -> None:
        """A well-protected exchange → fewer critical findings."""
        ex = _ex(
            method="POST",
            url="https://example.com/update",
            request_headers={"X-CSRF-Token": "valid_token_123"},
            request_body="csrf_token=valid_token_abcdef123456&data=x",
            response_headers={
                "Set-Cookie": (
                    "session_id=abc; SameSite=Lax; Secure; "
                    "HttpOnly"
                ),
                "Vary": "Origin, Referer",
            },
        )
        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(_flow(ex))

        # Protected flow may still have CSRF-009 (LOW) or
        # other minor findings, but should have no CRITICAL.
        critical = [
            f for f in output.findings
            if f.severity == Severity.CRITICAL
        ]
        assert len(critical) == 0


# ===========================================================================
# T-243: Integration Test (HAR → parse → static analysis → findings)
# ===========================================================================


class TestIntegration:
    """End-to-end integration: HAR file → analysis output."""

    def test_vulnerable_har_produces_findings(self) -> None:
        """Parse vulnerable.har → analyze → findings detected.

        The vulnerable.har sample has:
        - POST to /api/transfer with no CSRF token
        - POST to /api/settings with no CSRF token
        - No SameSite attribute on session cookies
        - No anti-CSRF headers
        """
        har_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "sample_har"
            / "vulnerable.har"
        )
        exchanges = parse_har_file(str(har_path))
        assert len(exchanges) > 0

        flow = SessionFlow(
            session_id="vuln-test",
            exchanges=exchanges,
            auth_mechanism=AuthMechanism.COOKIE,
        )

        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(flow)

        # Must produce findings (vulnerable traffic)
        assert len(output.findings) > 0
        assert not output.short_circuited

        # Feature vectors extracted for each exchange
        assert len(output.feature_vectors) == len(exchanges)

        # Should detect missing CSRF tokens (CSRF-001 or CSRF-002)
        rule_ids = {f.rule_id for f in output.findings}
        assert "CSRF-002" in rule_ids, (
            "Expected CSRF-002 (missing header) for vulnerable HAR"
        )

    def test_bearer_har_short_circuits(self) -> None:
        """Parse bearer_auth.har → short-circuit on header auth."""
        har_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "sample_har"
            / "bearer_auth.har"
        )
        exchanges = parse_har_file(str(har_path))

        flow = SessionFlow(
            session_id="bearer-test",
            exchanges=exchanges,
            auth_mechanism=AuthMechanism.HEADER_ONLY,
        )

        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(flow)

        assert output.short_circuited is True
        assert output.findings[0].rule_id == "CSRF-011"
