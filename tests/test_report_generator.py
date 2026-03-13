"""Tests for report generation (JSON and HTML).

Ref:
    - src/output/report_generator.py
    - src/output/remediation.py
    - spec/Tasks.md T-411 through T-415
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


import pytest

from src.input.models import Finding, HttpExchange, Severity
from src.output.remediation import REMEDIATIONS, get_remediation
from src.output.report_generator import (
    ReportAnalysisResult,
    ReportGenerator,
)
from src.scoring.risk_scorer import RiskLevel, RiskResult


# ===========================================================================
# Helpers
# ===========================================================================


def _ex() -> HttpExchange:
    """Minimal exchange for findings."""
    return HttpExchange(
        request_method="POST",
        request_url="https://example.com/test",
        request_headers={},
        request_cookies={},
        request_body=None,
        request_content_type="",
        response_status=200,
        response_headers={},
        response_body=None,
        timestamp=datetime(2026, 2, 28),
    )


def _sample_result() -> ReportAnalysisResult:
    """Build a sample ReportAnalysisResult for testing."""
    findings = [
        Finding(
            rule_id="CSRF-001",
            rule_name="Missing Form Token",
            severity=Severity.HIGH,
            description="No CSRF token found in form",
            evidence="<form action='/update'>",
            exchange=_ex(),
        ),
        Finding(
            rule_id="CSRF-005",
            rule_name="Missing SameSite",
            severity=Severity.MEDIUM,
            description="SameSite cookie attribute not set",
            evidence="Set-Cookie: session=abc",
            exchange=_ex(),
        ),
    ]
    risk = RiskResult(
        score=65,
        level=RiskLevel.HIGH,
        base_score=55.0,
        modifiers_applied=[
            "Modifies user data (+10)",
            "Uses HTTPS (-5)",
        ],
    )
    return ReportAnalysisResult(
        findings=findings,
        risk=risk,
        ml_probability=0.78,
        source_file="test.har",
    )


# ===========================================================================
# T-414: Remediation
# ===========================================================================


class TestRemediation:
    """Remediation recommendations tests."""

    def test_all_11_rules_covered(self) -> None:
        """All CSRF-001 through CSRF-011 have remediations."""
        for i in range(1, 12):
            rule_id = f"CSRF-{i:03d}"
            assert rule_id in REMEDIATIONS, f"Missing: {rule_id}"

    def test_get_known_rule(self) -> None:
        title, rec = get_remediation("CSRF-001")
        assert "CSRF" in title or "Token" in title
        assert len(rec) > 20

    def test_get_unknown_rule(self) -> None:
        title, rec = get_remediation("CSRF-999")
        assert "Review" in title


# ===========================================================================
# T-411: JSON Report (FR-501)
# ===========================================================================


class TestJSONReport:
    """JSON report generation tests."""

    @pytest.fixture
    def gen(self) -> ReportGenerator:
        return ReportGenerator()

    def test_json_output_valid(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """Generated JSON is valid and parseable."""
        out = tmp_path / "report.json"
        gen.generate_json(_sample_result(), out)

        with open(out) as f:
            data = json.load(f)
        assert "csrf_shield_ai_report" in data

    def test_json_contains_findings(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """JSON contains findings."""
        out = tmp_path / "report.json"
        gen.generate_json(_sample_result(), out)

        with open(out) as f:
            data = json.load(f)
        report = data["csrf_shield_ai_report"]
        assert len(report["findings"]) == 2
        assert report["findings"][0]["rule_id"] == "CSRF-001"

    def test_json_contains_risk_score(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """JSON contains risk score and level."""
        out = tmp_path / "report.json"
        gen.generate_json(_sample_result(), out)

        with open(out) as f:
            data = json.load(f)
        report = data["csrf_shield_ai_report"]
        assert report["risk_score"] == 65
        assert report["risk_level"] == "HIGH"

    def test_json_contains_remediation(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """JSON contains per-finding recommendations (FR-503)."""
        out = tmp_path / "report.json"
        gen.generate_json(_sample_result(), out)

        with open(out) as f:
            data = json.load(f)
        report = data["csrf_shield_ai_report"]
        assert len(report["remediations"]) == 2
        assert report["remediations"][0]["rule_id"] == "CSRF-001"

    def test_json_contains_summary(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """JSON contains summary statistics."""
        out = tmp_path / "report.json"
        gen.generate_json(_sample_result(), out)

        with open(out) as f:
            data = json.load(f)
        summary = data["csrf_shield_ai_report"]["summary"]
        assert summary["total_findings"] == 2
        assert summary["critical_high_count"] == 1  # 1 HIGH


# ===========================================================================
# T-413: HTML Report (FR-502)
# ===========================================================================


class TestHTMLReport:
    """HTML report generation tests."""

    @pytest.fixture
    def gen(self) -> ReportGenerator:
        return ReportGenerator()

    def test_html_renders(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """HTML renders without Jinja2 errors."""
        out = tmp_path / "report.html"
        gen.generate_html(_sample_result(), out)
        assert out.exists()
        html = out.read_text()
        assert len(html) > 100

    def test_html_contains_risk_badge(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """HTML contains color-coded risk badge."""
        out = tmp_path / "report.html"
        gen.generate_html(_sample_result(), out)
        html = out.read_text()
        assert "risk-HIGH" in html
        assert "65" in html

    def test_html_contains_findings(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """HTML contains findings table."""
        out = tmp_path / "report.html"
        gen.generate_html(_sample_result(), out)
        html = out.read_text()
        assert "CSRF-001" in html
        assert "CSRF-005" in html

    def test_html_contains_remediation(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """HTML contains remediation cards (FR-503)."""
        out = tmp_path / "report.html"
        gen.generate_html(_sample_result(), out)
        html = out.read_text()
        assert "Remediation" in html
        assert "CSRF-001" in html

    def test_html_contains_modifiers(
        self, gen: ReportGenerator, tmp_path: Path
    ) -> None:
        """HTML contains context modifiers."""
        out = tmp_path / "report.html"
        gen.generate_html(_sample_result(), out)
        html = out.read_text()
        assert "HTTPS" in html
