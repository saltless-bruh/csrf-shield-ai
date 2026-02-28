"""End-to-end CSRF analysis pipeline.

Orchestrates the full flow from HAR file to scored reports:
    HAR → parse → reconstruct flows → static analyze
      → ML predict → heuristic boost → risk score → report

Ref:
    - spec/Tasks.md T-421
    - docs/proposal/PROPOSAL.md §8–§10
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.static_analyzer import StaticAnalyzer, StaticAnalysisOutput
from src.input.flow_reconstructor import reconstruct_flows
from src.input.har_parser import parse_har_file
from src.input.models import Finding, SessionFlow
from src.ml.heuristics import apply_heuristics
from src.ml.predictor import CsrfPredictor
from src.output.report_generator import AnalysisResult, ReportGenerator
from src.scoring.risk_scorer import RiskResult, RiskScorer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------


@dataclass
class FlowResult:
    """Analysis result for a single session flow."""

    session_id: str
    findings: List[Finding]
    risk: RiskResult
    ml_probability: float
    short_circuited: bool
    feature_vectors: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )


@dataclass
class PipelineResult:
    """Aggregated result from the full pipeline run."""

    flow_results: List[FlowResult]
    json_report_path: Optional[Path] = None
    html_report_path: Optional[Path] = None

    @property
    def total_findings(self) -> int:
        """Get the total number of findings across all flows."""
        return sum(len(fr.findings) for fr in self.flow_results)

    @property
    def highest_risk(self) -> Optional[RiskResult]:
        """Get the highest risk result among all analyzed flows."""
        if not self.flow_results:
            return None
        return max(
            (fr.risk for fr in self.flow_results),
            key=lambda r: r.score,
        )


# ------------------------------------------------------------------
# Pipeline
# ------------------------------------------------------------------


class CsrfPipeline:
    """Full CSRF analysis pipeline: HAR → report.

    Usage::

        pipeline = CsrfPipeline()
        result = pipeline.analyze_har(Path("capture.har"))
        print(f"Highest risk: {result.highest_risk.score}")

    Ref: T-421
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        columns_path: Optional[Path] = None,
    ) -> None:
        """Initialize the CSRF pipeline with optional model paths."""
        self._analyzer = StaticAnalyzer()
        self._predictor = CsrfPredictor(
            **(
                {"model_path": model_path}
                if model_path
                else {}
            ),
            **(
                {"columns_path": columns_path}
                if columns_path
                else {}
            ),
        )
        self._scorer = RiskScorer()
        self._reporter = ReportGenerator()

    def analyze_har(
        self,
        har_path: Path,
        output_dir: Optional[Path] = None,
    ) -> PipelineResult:
        """Run the full pipeline on a HAR file.

        Args:
            har_path: Path to the HAR file.
            output_dir: Directory for report files. If None,
                reports are not written.

        Returns:
            PipelineResult with all flow results and report paths.
        """
        # Phase 1: Parse HAR → exchanges → flows.
        exchanges = parse_har_file(str(har_path))
        flows = reconstruct_flows(exchanges)

        logger.info(
            "Parsed %s: %d exchanges → %d flows",
            har_path.name,
            len(exchanges),
            len(flows),
        )

        # Phase 2–4: Analyze each flow.
        flow_results: List[FlowResult] = []
        all_findings: List[Finding] = []

        for flow in flows:
            result = self._analyze_flow(flow)
            flow_results.append(result)
            all_findings.extend(result.findings)

        pipeline_result = PipelineResult(flow_results=flow_results)

        # Generate reports if output dir provided.
        if output_dir:
            pipeline_result = self._generate_reports(
                pipeline_result, all_findings, har_path, output_dir
            )

        logger.info(
            "Pipeline complete: %d flows, %d findings, highest=%s",
            len(flow_results),
            len(all_findings),
            pipeline_result.highest_risk.score
            if pipeline_result.highest_risk
            else "N/A",
        )

        return pipeline_result

    def _analyze_flow(self, flow: SessionFlow) -> FlowResult:
        """Analyze a single session flow through all stages."""
        # Phase 2: Static analysis.
        static_output: StaticAnalysisOutput = (
            self._analyzer.analyze_flow(flow)
        )

        # FR-404: Short-circuited flows get fixed score 5.
        if static_output.short_circuited:
            risk = self._scorer.calculate_risk(
                ml_probability=0.0,
                findings=static_output.findings,
                is_short_circuited=True,
            )
            return FlowResult(
                session_id=flow.session_id,
                findings=static_output.findings,
                risk=risk,
                ml_probability=0.0,
                short_circuited=True,
                feature_vectors=static_output.feature_vectors,
            )

        # Phase 3: ML prediction + heuristics for each exchange.
        ml_probabilities: List[float] = []

        for key, features in static_output.feature_vectors.items():
            # Predict.
            prob = self._predictor.predict(features)

            # Get URL and method from the key ("METHOD URL").
            parts = key.split(" ", 1)
            method = parts[0] if len(parts) > 1 else "GET"
            url = parts[1] if len(parts) > 1 else key

            # Apply heuristics.
            adjusted = apply_heuristics(
                prob,
                static_output.findings,
                url,
                method,
            )
            ml_probabilities.append(adjusted)

        # Use max probability across exchanges (worst case).
        ml_probability = (
            max(ml_probabilities) if ml_probabilities else 0.0
        )

        # Phase 4: Risk scoring.
        url = (
            flow.exchanges[0].request_url
            if flow.exchanges
            else ""
        )
        method = (
            flow.exchanges[0].request_method
            if flow.exchanges
            else "GET"
        )

        risk = self._scorer.calculate_risk(
            ml_probability=ml_probability,
            findings=static_output.findings,
            url=url,
            http_method=method,
        )

        return FlowResult(
            session_id=flow.session_id,
            findings=static_output.findings,
            risk=risk,
            ml_probability=ml_probability,
            short_circuited=False,
            feature_vectors=static_output.feature_vectors,
        )

    def _generate_reports(
        self,
        pipeline_result: PipelineResult,
        all_findings: List[Finding],
        har_path: Path,
        output_dir: Path,
    ) -> PipelineResult:
        """Generate JSON and HTML reports."""
        # Use the highest-risk flow for the main report.
        if not pipeline_result.flow_results:
            return pipeline_result

        best = max(
            pipeline_result.flow_results,
            key=lambda fr: fr.risk.score,
        )

        analysis_result = AnalysisResult(
            findings=all_findings,
            risk=best.risk,
            ml_probability=best.ml_probability,
            source_file=har_path.name,
        )

        stem = har_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = self._reporter.generate_json(
            analysis_result, output_dir / f"{stem}_report.json"
        )
        html_path = self._reporter.generate_html(
            analysis_result, output_dir / f"{stem}_report.html"
        )

        pipeline_result.json_report_path = json_path
        pipeline_result.html_report_path = html_path

        return pipeline_result
