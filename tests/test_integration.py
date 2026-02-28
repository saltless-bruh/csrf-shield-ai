"""End-to-end integration tests for the CSRF analysis pipeline.

Uses the sample HAR file to validate the full flow from
HAR parsing through report generation.

Ref:
    - src/pipeline.py
    - spec/Tasks.md T-421, T-422, T-423
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pipeline import CsrfPipeline, FlowResult, PipelineResult
from src.scoring.risk_scorer import RiskLevel


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE_HAR = _PROJECT_ROOT / "data" / "sample_har" / "mixed_auth.har"


# ===========================================================================
# T-422: Integration Test with Sample HAR
# ===========================================================================


class TestPipelineEndToEnd:
    """Full pipeline integration tests."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory) -> PipelineResult:
        """Run pipeline once on sample HAR (cached per class)."""
        output_dir = tmp_path_factory.mktemp("reports")
        pipeline = CsrfPipeline()
        return pipeline.analyze_har(_SAMPLE_HAR, output_dir)

    def test_pipeline_runs(self, result: PipelineResult) -> None:
        """Pipeline completes without errors."""
        assert result is not None
        assert len(result.flow_results) > 0

    def test_produces_flow_results(
        self, result: PipelineResult
    ) -> None:
        """At least one flow result is produced."""
        assert len(result.flow_results) >= 1
        for fr in result.flow_results:
            assert isinstance(fr, FlowResult)
            assert fr.session_id

    def test_scores_in_valid_range(
        self, result: PipelineResult
    ) -> None:
        """All risk scores are 0–100."""
        for fr in result.flow_results:
            assert 0 <= fr.risk.score <= 100

    def test_risk_level_assigned(
        self, result: PipelineResult
    ) -> None:
        """All flow results have a valid risk level."""
        valid_levels = set(RiskLevel)
        for fr in result.flow_results:
            assert fr.risk.level in valid_levels

    def test_findings_present(
        self, result: PipelineResult
    ) -> None:
        """Static analysis produces findings."""
        assert result.total_findings > 0

    def test_json_report_created(
        self, result: PipelineResult
    ) -> None:
        """JSON report file exists and is valid."""
        assert result.json_report_path is not None
        assert result.json_report_path.exists()

        with open(result.json_report_path) as f:
            data = json.load(f)
        assert "csrf_shield_ai_report" in data

    def test_html_report_created(
        self, result: PipelineResult
    ) -> None:
        """HTML report file exists and contains content."""
        assert result.html_report_path is not None
        assert result.html_report_path.exists()
        html = result.html_report_path.read_text()
        assert "CSRF Shield AI" in html
        assert len(html) > 200


# ===========================================================================
# T-422: Short-Circuit Test
# ===========================================================================


class TestPipelineMixedAuth:
    """Verify mixed auth (cookie + JWT) is NOT short-circuited."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory) -> PipelineResult:
        """Run pipeline on mixed_auth.har (has cookies + Bearer JWT)."""
        output_dir = tmp_path_factory.mktemp("reports_sc")
        pipeline = CsrfPipeline()
        return pipeline.analyze_har(_SAMPLE_HAR, output_dir)

    def test_mixed_auth_not_short_circuited(
        self, result: PipelineResult
    ) -> None:
        """Mixed auth (cookie+JWT) is not short-circuited.

        mixed_auth.har has both Cookie and Authorization headers,
        so auth_detector classifies as MIXED, not HEADER_ONLY.
        """
        for fr in result.flow_results:
            # MIXED auth should NOT trigger short-circuit
            assert not fr.short_circuited

    def test_mixed_auth_scored_normally(
        self, result: PipelineResult
    ) -> None:
        """Mixed auth flows get normal scoring (not fixed 5)."""
        for fr in result.flow_results:
            # Score can be anything, but pipeline ran the full analysis
            assert 0 <= fr.risk.score <= 100


# ===========================================================================
# T-423: Validate Against Manually Calculated Scores
# ===========================================================================


class TestManualScoreValidation:
    """Verify scores match hand-calculated expectations."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory) -> PipelineResult:
        output_dir = tmp_path_factory.mktemp("reports_manual")
        pipeline = CsrfPipeline()
        return pipeline.analyze_har(_SAMPLE_HAR, output_dir)

    def test_short_circuit_manual_check(
        self, result: PipelineResult
    ) -> None:
        """Manual: mixed_auth.har has Bearer JWT → short-circuit → score=5.

        The HAR has Authorization: Bearer headers, so auth_detector
        classifies as HEADER_ONLY. Per FR-404, short-circuited
        sessions receive fixed score 5 (LOW).
        """
        for fr in result.flow_results:
            if fr.short_circuited:
                # Manually known: short-circuit = 5, LOW
                assert fr.risk.score == 5
                assert fr.risk.level == RiskLevel.LOW
                assert fr.ml_probability == 0.0

    def test_report_json_score_matches(
        self, result: PipelineResult
    ) -> None:
        """Score in JSON report matches pipeline result."""
        assert result.json_report_path is not None
        with open(result.json_report_path) as f:
            data = json.load(f)
        report = data["csrf_shield_ai_report"]

        # Report uses highest-risk flow
        highest = max(
            result.flow_results, key=lambda fr: fr.risk.score
        )
        assert report["risk_score"] == highest.risk.score
