"""Report generator for JSON and HTML output.

Produces analysis reports from risk scoring and static analysis
results, including per-finding remediation recommendations.

Ref:
    - spec/Tasks.md T-411 through T-415
    - spec/Requirements.md FR-501, FR-502, FR-503
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from src.input.models import Finding, Severity
from src.output.remediation import get_remediation
from src.scoring.risk_scorer import RiskResult

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------


@dataclass
class RemediationItem:
    """A remediation recommendation for a specific finding."""

    rule_id: str
    title: str
    recommendation: str


@dataclass
class AnalysisResult:
    """Aggregated analysis result for a single session/flow.

    This is the input to the report generator — it aggregates
    data from the static analyzer, ML predictor, and risk scorer.
    """

    findings: List[Finding]
    risk: RiskResult
    ml_probability: float
    source_file: str = ""
    url: str = ""
    http_method: str = ""


@dataclass
class ReportData:
    """Fully prepared data ready for report rendering."""

    findings: List[Dict[str, Any]]
    risk: Dict[str, Any]
    ml_probability: float
    modifiers: List[str]
    remediations: List[Dict[str, str]]
    critical_count: int
    generated_at: str
    source_file: str


# ------------------------------------------------------------------
# Report Generator
# ------------------------------------------------------------------


class ReportGenerator:
    """Generate JSON and HTML analysis reports.

    Usage::

        gen = ReportGenerator()
        gen.generate_json(result, Path("report.json"))
        gen.generate_html(result, Path("report.html"))

    Ref: FR-501, FR-502, FR-503
    """

    def __init__(
        self,
        templates_dir: Path = _TEMPLATES_DIR,
    ) -> None:
        """Initialize the report generator."""
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )

    def _prepare_data(
        self, result: AnalysisResult
    ) -> ReportData:
        """Transform AnalysisResult into render-ready data."""
        # Build findings list with remediation.
        findings_data: List[Dict[str, Any]] = []
        remediations: List[Dict[str, str]] = []
        seen_rules: set[str] = set()

        for f in result.findings:
            findings_data.append({
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "severity": f.severity.value,
                "description": f.description,
                "evidence": f.evidence or "",
            })

            # Add unique remediation per rule (FR-503).
            if f.rule_id not in seen_rules:
                seen_rules.add(f.rule_id)
                title, rec = get_remediation(f.rule_id)
                remediations.append({
                    "rule_id": f.rule_id,
                    "title": title,
                    "recommendation": rec,
                })

        # Count critical + high findings.
        critical_count = sum(
            1
            for f in result.findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
        )

        return ReportData(
            findings=findings_data,
            risk={
                "score": result.risk.score,
                "level": result.risk.level.value,
                "base_score": result.risk.base_score,
            },
            ml_probability=result.ml_probability,
            modifiers=list(result.risk.modifiers_applied),
            remediations=remediations,
            critical_count=critical_count,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source_file=result.source_file,
        )

    # ---------------------------------------------------------------
    # T-411: JSON Report (FR-501)
    # ---------------------------------------------------------------

    def generate_json(
        self,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Generate a JSON analysis report.

        Args:
            result: Aggregated analysis result.
            output_path: Where to write the JSON file.

        Returns:
            Path to the written JSON file.
        """
        data = self._prepare_data(result)
        report = {
            "csrf_shield_ai_report": {
                "generated_at": data.generated_at,
                "source_file": data.source_file,
                "risk_score": data.risk["score"],
                "risk_level": data.risk["level"],
                "base_score": data.risk["base_score"],
                "ml_probability": round(data.ml_probability, 4),
                "context_modifiers": data.modifiers,
                "findings": data.findings,
                "remediations": data.remediations,
                "summary": {
                    "total_findings": len(data.findings),
                    "critical_high_count": data.critical_count,
                },
            }
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("JSON report written to %s", output_path)
        return output_path

    # ---------------------------------------------------------------
    # T-413: HTML Report (FR-502)
    # ---------------------------------------------------------------

    def generate_html(
        self,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Generate an HTML analysis report.

        Args:
            result: Aggregated analysis result.
            output_path: Where to write the HTML file.

        Returns:
            Path to the written HTML file.
        """
        data = self._prepare_data(result)

        template = self._env.get_template("report.html")
        html = template.render(
            findings=data.findings,
            risk=data.risk,
            ml_probability=data.ml_probability,
            modifiers=data.modifiers,
            remediations=[
                RemediationItem(**r) for r in data.remediations
            ],
            critical_count=data.critical_count,
            generated_at=data.generated_at,
            source_file=data.source_file,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("HTML report written to %s", output_path)
        return output_path
