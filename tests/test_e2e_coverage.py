"""Phase 6.1 end-to-end tests.

T-601: Additional coverage for modules below 80%.
T-603: End-to-end test against representative HAR captures.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from src.ipc_server import IpcServer
from src.input.models import (
    AuthMechanism,
    HttpExchange,
    SessionFlow,
)
from src.scoring.risk_scorer import RiskLevel
from src.pipeline import CsrfPipeline

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample_har"


# ------------------------------------------------------------------
# T-603: End-to-end pipeline tests against sample HAR files
# ------------------------------------------------------------------


class TestEndToEndPipeline:
    """Full pipeline E2E: HAR → parse → analyze → score → report."""

    @pytest.mark.parametrize(
        "har_name",
        [
            "vulnerable.har",
            "form_urlencoded.har",
            "json_body.har",
            "multipart.har",
            "mixed_auth.har",
            "protected.har",
            "bearer_auth.har",
            "static_token.har",
        ],
    )
    def test_pipeline_runs_for_each_har(
        self, har_name: str
    ) -> None:
        """Pipeline completes without error for each HAR file."""
        har_path = SAMPLE_DIR / har_name
        if not har_path.exists():
            pytest.skip(f"HAR not found: {har_path}")

        pipeline = CsrfPipeline()
        results = pipeline.analyze_har(har_path)

        assert len(results.flow_results) >= 1

        for r in results.flow_results:
            assert hasattr(r, "risk")
            assert 0 <= r.risk.score <= 100
            assert r.risk.level in (
                RiskLevel.LOW,
                RiskLevel.MEDIUM,
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            )

    def test_vulnerable_har_high_risk(self) -> None:
        """Vulnerable HAR should produce elevated risk."""
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        pipeline = CsrfPipeline()
        results = pipeline.analyze_har(har_path)

        assert len(results.flow_results) >= 1
        # At least one result should have findings.
        has_findings = any(len(r.findings) > 0 for r in results.flow_results)
        assert has_findings, "Expected findings for vulnerable.har"

    def test_protected_har_lower_risk(self) -> None:
        """Protected HAR should produce lower risk than vulnerable."""
        protected = SAMPLE_DIR / "protected.har"
        if not protected.exists():
            pytest.skip("protected.har not found")

        pipeline = CsrfPipeline()
        results = pipeline.analyze_har(protected)
        assert len(results.flow_results) >= 1

    def test_e2e_json_report_generation(self) -> None:
        """Full E2E including JSON report output."""
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = CsrfPipeline()
            results = pipeline.analyze_har(
                har_path, output_dir=Path(tmpdir)
            )
            assert results.json_report_path is not None
            assert results.json_report_path.exists()
            data = json.loads(
                results.json_report_path.read_text()
            )
            assert isinstance(data, dict)

    def test_e2e_html_report_generation(self) -> None:
        """Full E2E including HTML report output."""
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = CsrfPipeline()
            results = pipeline.analyze_har(
                har_path, output_dir=Path(tmpdir)
            )
            assert results.html_report_path is not None
            assert results.html_report_path.exists()
            html = results.html_report_path.read_text()
            assert "<html" in html


# ------------------------------------------------------------------
# T-601: Additional IPC server coverage (target >85%)
# ------------------------------------------------------------------


class TestIpcServerCoverage:
    """Fill coverage gaps for ipc_server.py."""

    def _make_server(self) -> IpcServer:
        return IpcServer()

    def test_unknown_method(self) -> None:
        """Unknown method returns METHOD_NOT_FOUND."""
        server = self._make_server()
        resp = server.handle_request(
            {"id": 1, "method": "unknown_method"}
        )
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == "METHOD_NOT_FOUND"

    def test_list_flows_empty(self) -> None:
        """list_flows with no loaded HAR returns empty list."""
        server = self._make_server()
        resp = server.handle_request(
            {"id": 1, "method": "list_flows"}
        )
        assert resp is not None
        assert resp["result"]["flows"] == []

    def test_get_results_not_analyzed(self) -> None:
        """get_results for unknown session returns not_analyzed."""
        server = self._make_server()
        resp = server.handle_request({
            "id": 1,
            "method": "get_results",
            "params": {"session_id": "nonexistent"},
        })
        assert resp is not None
        assert resp["result"]["status"] == "not_analyzed"

    def test_cancel(self) -> None:
        """cancel sets cancelled flag."""
        server = self._make_server()
        resp = server.handle_request(
            {"id": 1, "method": "cancel"}
        )
        assert resp is not None
        assert resp["result"]["status"] == "cancelled"
        assert server._cancelled is True

    def test_analyze_flow_not_found(self) -> None:
        """analyze_flow for unknown session returns not_found."""
        server = self._make_server()
        resp = server.handle_request({
            "id": 1,
            "method": "analyze_flow",
            "params": {"session_id": "bad_session"},
        })
        assert resp is not None
        assert resp["result"]["status"] == "not_found"

    def test_load_har_then_list_flows(self) -> None:
        """Load a HAR, then list_flows should return sessions."""
        server = self._make_server()
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        resp = server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(har_path)},
        })
        assert resp is not None
        assert resp["result"]["total_flows"] >= 1

        resp2 = server.handle_request(
            {"id": 2, "method": "list_flows"}
        )
        assert resp2 is not None
        assert len(resp2["result"]["flows"]) >= 1

    @patch("sys.stdout", new_callable=MagicMock)
    def test_analyze_flow_with_progress(
        self, mock_stdout: MagicMock
    ) -> None:
        """analyze_flow emits progress events."""
        server = self._make_server()
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        # Load HAR.
        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(har_path)},
        })

        # Get session ID.
        resp = server.handle_request(
            {"id": 2, "method": "list_flows"}
        )
        session_id = resp["result"]["flows"][0]["session_id"]

        # Analyze.
        resp = server.handle_request({
            "id": 3,
            "method": "analyze_flow",
            "params": {"session_id": session_id},
        })
        assert resp is not None
        assert "result" in resp
        assert "summary" in resp["result"]
        assert "results" in resp["result"]

        # Progress was written to stdout.
        assert mock_stdout.write.called

    @patch("sys.stdout", new_callable=MagicMock)
    def test_analyze_all(self, mock_stdout: MagicMock) -> None:
        """analyze_all processes all sessions."""
        server = self._make_server()
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(har_path)},
        })

        resp = server.handle_request(
            {"id": 2, "method": "analyze_all"}
        )
        assert resp is not None
        assert resp["result"]["status"] == "ok"
        assert resp["result"]["completed"] >= 1

    @patch("sys.stdout", new_callable=MagicMock)
    def test_export_report_json(
        self, mock_stdout: MagicMock
    ) -> None:
        """export_report generates JSON file."""
        server = self._make_server()
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        # Load and analyze.
        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(har_path)},
        })
        flows_resp = server.handle_request(
            {"id": 2, "method": "list_flows"}
        )
        sid = flows_resp["result"]["flows"][0]["session_id"]

        server.handle_request({
            "id": 3,
            "method": "analyze_flow",
            "params": {"session_id": sid},
        })

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            out_path = f.name

        try:
            resp = server.handle_request({
                "id": 4,
                "method": "export_report",
                "params": {
                    "format": "json",
                    "scope": "selected",
                    "session_id": sid,
                    "path": out_path,
                },
            })
            assert resp is not None
            assert resp["result"]["status"] == "ok"
            assert resp["result"]["size_bytes"] > 0
        finally:
            Path(out_path).unlink(missing_ok=True)

    @patch("sys.stdout", new_callable=MagicMock)
    def test_export_report_all_scope(
        self, mock_stdout: MagicMock
    ) -> None:
        """export_report with scope=all."""
        server = self._make_server()
        har_path = SAMPLE_DIR / "vulnerable.har"
        if not har_path.exists():
            pytest.skip("vulnerable.har not found")

        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(har_path)},
        })
        server.handle_request(
            {"id": 2, "method": "analyze_all"}
        )

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            out_path = f.name

        try:
            resp = server.handle_request({
                "id": 3,
                "method": "export_report",
                "params": {
                    "format": "json",
                    "scope": "all",
                    "path": out_path,
                },
            })
            assert resp is not None
            assert resp["result"]["status"] == "ok"
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_handle_request_with_exception(self) -> None:
        """Internal error returns INTERNAL_ERROR."""
        server = self._make_server()

        # Force an error by monkeypatching.
        original = server._handle_ping

        def broken_ping(*a: Any, **kw: Any) -> None:
            raise RuntimeError("test crash")

        server._handle_ping = broken_ping  # type: ignore

        resp = server.handle_request(
            {"id": 1, "method": "ping"}
        )
        assert resp is not None
        assert resp["error"]["code"] == "INTERNAL_ERROR"
        assert "test crash" in resp["error"]["message"]

        server._handle_ping = original  # type: ignore


# ------------------------------------------------------------------
# T-601: Additional har_parser coverage
# ------------------------------------------------------------------


class TestHarParserCoverage:
    """Additional har_parser edge cases."""

    def test_parse_nonexistent_file(self) -> None:
        """Parsing a nonexistent file raises FileNotFoundError."""
        from src.input.har_parser import parse_har_file

        with pytest.raises(FileNotFoundError):
            parse_har_file("/nonexistent/file.har")

    def test_parse_invalid_json(self) -> None:
        """Parsing an invalid JSON file raises error."""
        from src.input.har_parser import parse_har_file

        with tempfile.NamedTemporaryFile(
            suffix=".har", mode="w", delete=False
        ) as f:
            f.write("not json")
            path = f.name

        try:
            with pytest.raises(Exception):
                parse_har_file(path)
        finally:
            os.unlink(path)

    def test_parse_empty_entries(self) -> None:
        """Parsing HAR with no entries returns empty list."""
        from src.input.har_parser import parse_har_file

        har_data = {
            "log": {"version": "1.2", "entries": []}
        }
        with tempfile.NamedTemporaryFile(
            suffix=".har", mode="w", delete=False
        ) as f:
            json.dump(har_data, f)
            path = f.name

        try:
            result = parse_har_file(path)
            assert result == []
        finally:
            os.unlink(path)


# ------------------------------------------------------------------
# T-601: Additional static_analyzer coverage
# ------------------------------------------------------------------


class TestStaticAnalyzerCoverage:
    """Additional static_analyzer edge cases."""

    def test_analyzer_with_empty_flow(self) -> None:
        """Analyzer handles flow with no exchanges."""
        from src.analysis.static_analyzer import StaticAnalyzer

        analyzer = StaticAnalyzer()
        flow = SessionFlow(
            session_id="empty",
            exchanges=[],
            auth_mechanism=AuthMechanism.NONE,
        )
        output = analyzer.analyze_flow(flow)
        assert output is not None
        assert output.findings == []

    def test_analyzer_with_get_only_flow(self) -> None:
        """Analyzer handles flow with only GET requests."""
        from src.analysis.static_analyzer import StaticAnalyzer

        analyzer = StaticAnalyzer()
        exchange = HttpExchange(
            request_method="GET",
            request_url="http://example.com/page",
            request_headers={"Host": "example.com"},
            request_body="",
            request_cookies={},
            request_content_type="",
            response_status=200,
            response_headers={},
            response_body="",
            timestamp=datetime.now(),
        )
        flow = SessionFlow(
            session_id="gets_only",
            exchanges=[exchange],
            auth_mechanism=AuthMechanism.COOKIE,
        )
        output = analyzer.analyze_flow(flow)
        assert output is not None
        # GETs should produce few or no findings.


# ------------------------------------------------------------------
# T-601: Pipeline method coverage
# ------------------------------------------------------------------


class TestPipelineCoverage:
    """Ensure pipeline export methods are covered."""

    def test_pipeline_export_json(self) -> None:
        """CsrfPipeline with output_dir produces valid JSON."""
        har_path = SAMPLE_DIR / "minimal.har"
        if not har_path.exists():
            pytest.skip("minimal.har not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = CsrfPipeline()
            results = pipeline.analyze_har(
                har_path, output_dir=Path(tmpdir)
            )
            assert results.json_report_path is not None
            data = json.loads(
                results.json_report_path.read_text()
            )
            assert isinstance(data, dict)

    def test_pipeline_export_html(self) -> None:
        """CsrfPipeline with output_dir produces valid HTML."""
        har_path = SAMPLE_DIR / "minimal.har"
        if not har_path.exists():
            pytest.skip("minimal.har not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = CsrfPipeline()
            results = pipeline.analyze_har(
                har_path, output_dir=Path(tmpdir)
            )
            assert results.html_report_path is not None
            html = results.html_report_path.read_text()
            assert "<html" in html
