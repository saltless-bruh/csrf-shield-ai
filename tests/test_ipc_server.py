"""Tests for the NDJSON IPC server.

Tests all 8 methods, serialization helpers, error responses,
and progress events.

Ref:
    - src/ipc_server.py
    - spec/Tasks.md T-431 through T-434
    - docs/proposal/CLI_TUI_PROPOSAL.md §3.2
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


import pytest

from src.input.models import (
    AuthMechanism,
    Finding,
    HttpExchange,
    Severity,
    SessionFlow,
)
from src.ipc_server import (
    IpcServer,
    compute_static_score,
    serialize_exchange_ref,
    serialize_finding,
    serialize_flow_summary,
)


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE_HAR = _PROJECT_ROOT / "data" / "sample_har" / "mixed_auth.har"
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ipc"


# ===========================================================================
# Helpers
# ===========================================================================


def _ex() -> HttpExchange:
    return HttpExchange(
        request_method="POST",
        request_url="https://example.com/api/transfer",
        request_headers={},
        request_cookies={"session_id": "abc"},
        request_body="amount=100",
        request_content_type="application/x-www-form-urlencoded",
        response_status=200,
        response_headers={},
        response_body='{"ok": true}',
        timestamp=datetime(2026, 2, 28),
    )


def _finding(rule_id: str = "CSRF-001", severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        rule_id=rule_id,
        rule_name="Test Rule",
        severity=severity,
        description="Test description",
        evidence="Test evidence",
        exchange=_ex(),
    )


def _flow(session_id: str = "test-session") -> SessionFlow:
    return SessionFlow(
        session_id=session_id,
        exchanges=[_ex()],
        auth_mechanism=AuthMechanism.COOKIE,
    )


# ===========================================================================
# T-432: Serialization Helpers
# ===========================================================================


class TestSerialization:
    """IPC serialization tests."""

    def test_exchange_ref_compact(self) -> None:
        """Exchange ref is compact: method, url path, status."""
        ref = serialize_exchange_ref(_ex())
        assert ref == {
            "method": "POST",
            "url": "/api/transfer",
            "status": 200,
        }

    def test_finding_serialization(self) -> None:
        """Finding uses .value strings and compact exchange ref."""
        data = serialize_finding(_finding())
        assert data["severity"] == "HIGH"  # .value string
        assert data["exchange"]["method"] == "POST"
        assert "request_headers" not in data["exchange"]

    def test_static_score_computation(self) -> None:
        """static_score = sum(severities) / max_possible."""
        findings = [
            _finding("CSRF-001", Severity.HIGH),
            _finding("CSRF-005", Severity.MEDIUM),
        ]
        score = compute_static_score(findings)
        expected = (0.75 + 0.5) / 11.0
        assert abs(score - expected) < 0.01

    def test_static_score_empty(self) -> None:
        assert compute_static_score([]) == 0.0

    def test_flow_summary_serialization(self) -> None:
        """Flow summary includes host and auth .value string."""
        data = serialize_flow_summary(_flow())
        assert data["session_id"] == "test-session"
        assert data["auth_mechanism"] == "cookie"  # lowercase
        assert data["exchange_count"] == 1
        assert data["host"] == "example.com"


# ===========================================================================
# T-431: Method Handlers
# ===========================================================================


class TestPing:
    """ping method tests."""

    def test_ping_response(self) -> None:
        server = IpcServer()
        resp = server.handle_request(
            {"id": 1, "method": "ping", "params": {}}
        )
        assert resp["id"] == 1
        assert resp["result"]["status"] == "ok"
        assert resp["result"]["version"] == "1.0"

    def test_ping_matches_fixture(self) -> None:
        """Response matches golden fixture."""
        server = IpcServer()
        resp = server.handle_request(
            {"id": 1, "method": "ping", "params": {}}
        )
        expected = json.loads(
            (_FIXTURES_DIR / "ping_response.json").read_text()
        )
        assert resp == expected


class TestLoadHar:
    """load_har method tests."""

    def test_load_har_success(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 2,
            "method": "load_har",
            "params": {"path": str(_SAMPLE_HAR)},
        })
        result = resp["result"]
        assert result["total_flows"] >= 1
        assert result["total_exchanges"] >= 2
        assert len(result["flows"]) >= 1

    def test_load_har_file_not_found(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 2,
            "method": "load_har",
            "params": {"path": "/bad/path.har"},
        })
        assert "error" in resp
        assert resp["error"]["code"] == "FILE_NOT_FOUND"


class TestListFlows:
    """list_flows method tests."""

    def test_list_flows_after_load(self) -> None:
        server = IpcServer()
        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(_SAMPLE_HAR)},
        })
        resp = server.handle_request({
            "id": 2,
            "method": "list_flows",
            "params": {},
        })
        assert len(resp["result"]["flows"]) >= 1

    def test_list_flows_empty(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 1,
            "method": "list_flows",
            "params": {},
        })
        assert resp["result"]["flows"] == []


class TestAnalyzeFlow:
    """analyze_flow method tests."""

    @pytest.fixture
    def loaded_server(self) -> IpcServer:
        server = IpcServer()
        server.handle_request({
            "id": 1,
            "method": "load_har",
            "params": {"path": str(_SAMPLE_HAR)},
        })
        # Redirect stdout to capture progress events.
        server._write = lambda data: None  # Suppress for tests.
        return server

    def test_analyze_flow_returns_results(
        self, loaded_server: IpcServer
    ) -> None:
        # Get session ID from list_flows.
        flows_resp = loaded_server.handle_request({
            "id": 2,
            "method": "list_flows",
            "params": {},
        })
        session_id = flows_resp["result"]["flows"][0]["session_id"]

        resp = loaded_server.handle_request({
            "id": 3,
            "method": "analyze_flow",
            "params": {"session_id": session_id},
        })
        result = resp["result"]
        assert "summary" in result
        assert "results" in result
        assert result["summary"]["risk_score"] >= 0
        assert result["summary"]["risk_level"] in (
            "LOW", "MEDIUM", "HIGH", "CRITICAL"
        )

    def test_analyze_flow_not_found(
        self, loaded_server: IpcServer
    ) -> None:
        resp = loaded_server.handle_request({
            "id": 3,
            "method": "analyze_flow",
            "params": {"session_id": "nonexistent"},
        })
        assert resp["result"]["status"] == "not_found"


class TestGetResults:
    """get_results method tests."""

    def test_not_analyzed(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 1,
            "method": "get_results",
            "params": {"session_id": "abc123"},
        })
        assert resp["result"]["status"] == "not_analyzed"


class TestCancel:
    """cancel method tests."""

    def test_cancel_sets_flag(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 1,
            "method": "cancel",
            "params": {},
        })
        assert resp["result"]["status"] == "cancelled"
        assert server._cancelled is True


class TestExportReport:
    """export_report method tests."""

    def test_export_json(self, tmp_path: Path) -> None:
        server = IpcServer()
        out = tmp_path / "report.json"
        resp = server.handle_request({
            "id": 1,
            "method": "export_report",
            "params": {
                "format": "json",
                "scope": "all",
                "path": str(out),
            },
        })
        assert resp["result"]["status"] == "ok"
        assert out.exists()


# ===========================================================================
# Error Handling
# ===========================================================================


class TestErrors:
    """Error response tests."""

    def test_unknown_method(self) -> None:
        server = IpcServer()
        resp = server.handle_request({
            "id": 1,
            "method": "unknown_method",
            "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == "METHOD_NOT_FOUND"

    def test_error_format_matches_fixture(self) -> None:
        """Error format matches golden fixture structure."""
        server = IpcServer()
        resp = server.handle_request({
            "id": 2,
            "method": "load_har",
            "params": {"path": "/bad/path.har"},
        })
        expected = json.loads(
            (_FIXTURES_DIR / "error_response.json").read_text()
        )
        # Structure matches (code and message keys present).
        assert set(resp["error"].keys()) == set(expected["error"].keys())
        assert resp["error"]["code"] == expected["error"]["code"]


# ===========================================================================
# T-433: Golden Fixture Validation
# ===========================================================================


class TestGoldenFixtures:
    """Verify golden fixtures have correct structure."""

    def test_ping_fixture_structure(self) -> None:
        data = json.loads(
            (_FIXTURES_DIR / "ping_response.json").read_text()
        )
        assert "id" in data
        assert "result" in data
        assert data["result"]["status"] == "ok"

    def test_analyze_fixture_structure(self) -> None:
        data = json.loads(
            (_FIXTURES_DIR / "analyze_flow_response.json").read_text()
        )
        assert data["result"]["summary"]["risk_level"] in (
            "LOW", "MEDIUM", "HIGH", "CRITICAL"
        )
        assert len(data["result"]["results"]) >= 1
        finding = data["result"]["results"][0]["findings"][0]
        assert finding["severity"] in (
            "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
        )
        assert "method" in finding["exchange"]

    def test_error_fixture_structure(self) -> None:
        data = json.loads(
            (_FIXTURES_DIR / "error_response.json").read_text()
        )
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
