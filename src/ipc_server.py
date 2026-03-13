"""NDJSON IPC server for Go TUI communication.

Reads JSON-RPC-like requests from stdin, writes JSON responses to
stdout. Wraps the Phases 1–4 analysis pipeline.

Protocol defined in CLI_TUI_PROPOSAL.md §3.2.

Ref:
    - spec/Tasks.md T-431, T-432
    - spec/Requirements.md FR-506
"""

from __future__ import annotations

import json
import logging
import sys

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.analysis.static_analyzer import StaticAnalyzer, StaticAnalysisOutput
from src.input.flow_reconstructor import reconstruct_flows
from src.input.auth_detector import update_flow_auth
from src.input.har_parser import parse_har_file
from src.input.models import (
    AnalysisResult,
    Finding,
    HttpExchange,
    Severity,
    SessionFlow,
)
from src.ml.heuristics import apply_heuristics
from src.ml.predictor import CsrfPredictor
from src.output.remediation import get_remediation
from src.output.report_generator import (
    ReportAnalysisResult,
    ReportGenerator,
)
from src.scoring.risk_scorer import (
    RiskLevel,
    RiskResult,
    RiskScorer,
)

# Configure logging to file (backend.log) so it doesn't corrupt stdout/stderr TUI buffers.
logging.basicConfig(
    filename='backend.log',
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "1.0"

# Reuse normalization from risk_scorer (DRY).
from src.scoring.risk_scorer import normalize_static_score  # noqa: E402


# ------------------------------------------------------------------
# T-432: Serialization Helpers
# ------------------------------------------------------------------


def serialize_exchange_ref(exchange: HttpExchange) -> Dict[str, Any]:
    """Compact exchange reference for Finding serialization.

    Per CLI_TUI_PROPOSAL.md §3.2:
        {"method": "POST", "url": "/api/transfer", "status": 200}
    """
    return {
        "method": exchange.request_method,
        "url": urlparse(exchange.request_url).path,
        "status": exchange.response_status,
    }


def serialize_finding(finding: Finding) -> Dict[str, Any]:
    """Serialize a Finding for IPC, using compact exchange ref."""
    return {
        "rule_id": finding.rule_id,
        "rule_name": finding.rule_name,
        "severity": finding.severity.value,
        "description": finding.description,
        "evidence": finding.evidence,
        "exchange": serialize_exchange_ref(finding.exchange),
    }


def compute_static_score(findings: List[Finding]) -> float:
    """Compute static_score on-the-fly (PROPOSAL §10.1).

    Delegates to risk_scorer.normalize_static_score() to stay
    in sync with settings.yaml severity weights.
    """
    return round(normalize_static_score(findings), 4)


def serialize_flow_summary(flow: SessionFlow) -> Dict[str, Any]:
    """Serialize a SessionFlow for list_flows response."""
    host = ""
    if flow.exchanges:
        parsed = urlparse(flow.exchanges[0].request_url)
        host = parsed.hostname or ""

    return {
        "session_id": flow.session_id,
        "host": host,
        "auth_mechanism": flow.auth_mechanism.value,
        "exchange_count": len(flow.exchanges),
    }


def serialize_analysis_result(
    result: AnalysisResult,
) -> Dict[str, Any]:
    """Serialize an AnalysisResult for IPC response."""
    findings_data = [serialize_finding(f) for f in result.findings]

    # Per-finding remediation (FR-503).
    seen_rules: set[str] = set()
    recommendations: List[str] = []
    for f in result.findings:
        if f.rule_id not in seen_rules:
            seen_rules.add(f.rule_id)
            title, rec = get_remediation(f.rule_id)
            recommendations.append(f"{title}: {rec}")

    return {
        "endpoint": result.endpoint,
        "http_method": result.http_method,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level.value,
        "findings": findings_data,
        "ml_probability": result.ml_probability,
        "static_score": compute_static_score(result.findings),
        "feature_vector": result.feature_vector or {},
        "recommendations": recommendations
        if recommendations
        else result.recommendations,
    }


# ------------------------------------------------------------------
# IPC Server
# ------------------------------------------------------------------


class IpcServer:
    """NDJSON IPC server wrapping the analysis pipeline.

    Usage::

        server = IpcServer()
        server.run()  # Reads stdin, writes stdout

    Or for testing::

        response = server.handle_request({"id": 1, "method": "ping"})
    """

    def __init__(self) -> None:
        """Initialize the IPC server with analysis components."""
        self._flows: List[SessionFlow] = []
        self._results: Dict[str, Dict[str, Any]] = {}
        self._analyzer = StaticAnalyzer()
        self._predictor = CsrfPredictor()
        self._scorer = RiskScorer()
        self._reporter = ReportGenerator()
        self._cancelled = False

    # ---------------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------------

    def run(self) -> None:
        """Read requests from stdin, write responses to stdout."""
        logger.info("IPC server starting (version %s)", VERSION)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                self._write({
                    "id": None,
                    "error": {
                        "code": "PARSE_ERROR",
                        "message": f"Invalid JSON: {exc}",
                    },
                })
                continue

            response = self.handle_request(request)
            if response is not None:
                self._write(response)

        logger.info("IPC server shutting down (stdin closed)")

    def handle_request(
        self, request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Dispatch a single request to the appropriate handler."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        handler = {
            "ping": self._handle_ping,
            "load_har": self._handle_load_har,
            "list_flows": self._handle_list_flows,
            "analyze_flow": self._handle_analyze_flow,
            "analyze_all": self._handle_analyze_all,
            "get_results": self._handle_get_results,
            "cancel": self._handle_cancel,
            "export_report": self._handle_export_report,
            "get_flow_exchanges": self._handle_get_flow_exchanges,
        }.get(method)

        if handler is None:
            return {
                "id": req_id,
                "error": {
                    "code": "METHOD_NOT_FOUND",
                    "message": f"Unknown method: {method}",
                },
            }

        try:
            result = handler(params, req_id)
            return {"id": req_id, "result": result}
        except FileNotFoundError as exc:
            return {
                "id": req_id,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": str(exc),
                },
            }
        except Exception as exc:
            logger.exception("Error handling %s", method)
            return {
                "id": req_id,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    # ---------------------------------------------------------------
    # Method handlers
    # ---------------------------------------------------------------

    def _handle_get_flow_exchanges(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> List[Dict[str, Any]]:
        """Return raw HTTP exchanges for a given session."""
        session_id = params.get("session_id")
        if not session_id:
            raise ValueError("session_id is required")

        flow = self._find_flow(session_id)
        if not flow:
            raise ValueError(f"Session not found: {session_id}")

        result = []
        for ex in flow.exchanges:
            result.append({
                "request_method": ex.request_method,
                "request_url": ex.request_url,
                "request_headers": ex.request_headers,
                "request_cookies": ex.request_cookies,
                "request_body": ex.request_body,
                "request_content_type": ex.request_content_type,
                "response_status": ex.response_status,
                "response_headers": ex.response_headers,
                "response_body": ex.response_body,
                "timestamp": ex.timestamp.isoformat() if ex.timestamp else None,
            })
        return result

    def _handle_ping(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Health check."""
        return {"status": "ok", "version": VERSION}

    def _handle_load_har(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Parse HAR file and reconstruct flows."""
        path = params.get("path", "")
        if not Path(path).exists():
            raise FileNotFoundError(
                f"File does not exist: {path}"
            )

        exchanges = parse_har_file(path)
        raw_flows = reconstruct_flows(exchanges)
        self._flows = [update_flow_auth(f) for f in raw_flows]
        self._results.clear()

        return {
            "flows": [
                serialize_flow_summary(f) for f in self._flows
            ],
            "total_flows": len(self._flows),
            "total_exchanges": sum(
                len(f.exchanges) for f in self._flows
            ),
        }

    def _handle_list_flows(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Return current session flow summaries."""
        return {
            "flows": [
                serialize_flow_summary(f) for f in self._flows
            ],
        }

    def _handle_analyze_flow(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Run full analysis on one session."""
        session_id = params.get("session_id", "")
        flow = self._find_flow(session_id)

        if flow is None:
            return {
                "session_id": session_id,
                "status": "not_found",
            }

        analysis = self._run_analysis(flow, req_id, 1, 1)
        self._results[session_id] = analysis
        return analysis

    def _handle_analyze_all(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Analyze all sessions sequentially."""
        self._cancelled = False
        completed = 0

        for i, flow in enumerate(self._flows):
            if self._cancelled:
                break

            analysis = self._run_analysis(
                flow, req_id, i + 1, len(self._flows)
            )
            self._results[flow.session_id] = analysis
            completed += 1

        return {
            "status": "cancelled" if self._cancelled else "ok",
            "completed": completed,
            "total": len(self._flows),
        }

    def _handle_get_results(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Return cached results for a session."""
        session_id = params.get("session_id", "")
        cached = self._results.get(session_id)

        if cached is None:
            return {
                "session_id": session_id,
                "status": "not_analyzed",
            }

        return cached

    def _handle_cancel(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Set cancel flag for analyze_all."""
        self._cancelled = True
        return {"status": "cancelled"}

    def _handle_export_report(
        self,
        params: Dict[str, Any],
        req_id: Any,
    ) -> Dict[str, Any]:
        """Generate a report file."""
        fmt = params.get("format", "json")
        scope = params.get("scope", "selected")
        session_id = params.get("session_id", "")
        path = Path(params.get("path", f"report.{fmt}"))

        # Gather findings and best ML probability.
        all_findings: List[Finding] = []
        best_ml: float = 0.0

        def _collect_from_cached(
            cached: Dict[str, Any],
            flow: SessionFlow,
        ) -> None:
            """Extract findings + best_ml from a cached result."""
            nonlocal best_ml
            for r_data in cached.get("results", []):
                # Track best ML probability.
                ml_p = r_data.get("ml_probability", 0.0)
                if isinstance(ml_p, (int, float)):
                    best_ml = max(best_ml, float(ml_p))

                # Find matching exchange for this result.
                endpoint = r_data.get("endpoint", "")
                method = r_data.get("http_method", "")
                match_ex = None
                for ex in flow.exchanges:
                    if (
                        urlparse(ex.request_url).path == endpoint
                        and ex.request_method == method
                    ):
                        match_ex = ex
                        break
                # Fallback to first exchange if no match.
                if match_ex is None and flow.exchanges:
                    match_ex = flow.exchanges[0]

                if match_ex is not None:
                    for fd in r_data.get("findings", []):
                        all_findings.append(
                            self._reconstruct_finding(fd, match_ex)
                        )

        if scope == "selected" and session_id:
            cached = self._results.get(session_id)
            if cached and "results" in cached:
                flow = self._find_flow(session_id)
                if flow:
                    _collect_from_cached(cached, flow)
        else:
            for flow in self._flows:
                cached = self._results.get(flow.session_id)
                if cached and "results" in cached:
                    _collect_from_cached(cached, flow)

        # Also extract best_ml from summary if available.
        if scope == "selected" and session_id:
            cached = self._results.get(session_id)
            if cached and "summary" in cached:
                summary_ml = cached["summary"].get(
                    "ml_probability_max", 0.0
                )
                if isinstance(summary_ml, (int, float)):
                    best_ml = max(best_ml, float(summary_ml))

        # Use the scorer for the report.
        risk = RiskResult(
            score=5,
            level=RiskLevel.LOW,
            base_score=5.0,
        )
        if all_findings:
            risk = self._scorer.calculate_risk(
                ml_probability=best_ml,
                findings=all_findings,
            )

        report_result = ReportAnalysisResult(
            findings=all_findings,
            risk=risk,
            ml_probability=best_ml,
            source_file=session_id,
        )

        if fmt == "html":
            self._reporter.generate_html(report_result, path)
        else:
            self._reporter.generate_json(report_result, path)

        size = path.stat().st_size if path.exists() else 0

        return {
            "status": "ok",
            "path": str(path),
            "size_bytes": size,
        }

    # ---------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------

    def _find_flow(
        self, session_id: str
    ) -> Optional[SessionFlow]:
        """Find a flow by session ID."""
        for f in self._flows:
            if f.session_id == session_id:
                return f
        return None

    def _run_analysis(
        self,
        flow: SessionFlow,
        req_id: Any,
        session_index: int,
        session_total: int,
    ) -> Dict[str, Any]:
        """Run full pipeline on one flow with progress events."""
        steps = [
            "static_analysis",
            "feature_extraction",
            "ml_inference",
            "risk_scoring",
            "recommendations",
        ]

        def emit_progress(step_idx: int) -> None:
            pct = int(
                (
                    (session_index - 1) / session_total
                    + (step_idx + 1)
                    / (len(steps) * session_total)
                )
                * 100
            )
            self._write({
                "id": req_id,
                "progress": {
                    "status": "analyzing",
                    "session_id": flow.session_id,
                    "session_index": session_index,
                    "session_total": session_total,
                    "step": steps[step_idx],
                    "step_current": step_idx + 1,
                    "step_total": len(steps),
                    "percent": min(pct, 100),
                },
            })

        # Step 1: Static analysis.
        emit_progress(0)
        static_output: StaticAnalysisOutput = (
            self._analyzer.analyze_flow(flow)
        )

        # Short-circuit check.
        if static_output.short_circuited:
            return {
                "session_id": flow.session_id,
                "summary": {
                    "risk_score": 5,
                    "risk_level": "LOW",
                    "ml_probability_max": 0.0,
                    "static_score_max": 0.0,
                },
                "results": [
                    {
                        "endpoint": "short-circuited",
                        "http_method": "",
                        "risk_score": 5,
                        "risk_level": "LOW",
                        "findings": [
                            serialize_finding(f)
                            for f in static_output.findings
                        ],
                        "ml_probability": 0.0,
                        "static_score": 0.0,
                        "feature_vector": {},
                        "recommendations": [
                            "No action needed — CSRF N/A (header-only auth)."
                        ],
                    }
                ],
            }

        # Step 2: Feature extraction (already done in static_analyzer).
        emit_progress(1)

        # Step 3: ML inference + heuristics.
        emit_progress(2)
        exchange_results: List[Dict[str, Any]] = []
        max_ml = 0.0
        max_static = 0.0
        max_risk = 0
        max_risk_level = "LOW"

        for key, features in static_output.feature_vectors.items():
            parts = key.split(" ", 1)
            method = parts[0] if len(parts) > 1 else "GET"
            url = parts[1] if len(parts) > 1 else key

            # Resolve the HttpExchange object for this key so findings
            # can be scoped to this exchange only (not the whole session).
            exchange_obj = next(
                (
                    ex
                    for ex in flow.exchanges
                    if f"{ex.request_method} {ex.request_url}" == key
                ),
                None,
            )
            exchange_findings = (
                [f for f in static_output.findings if f.exchange is exchange_obj]
                if exchange_obj is not None
                else list(static_output.findings)
            )

            prob = self._predictor.predict(features)
            adjusted = apply_heuristics(
                prob, exchange_findings, url, method
            )

            # Step 4: Risk scoring.
            risk = self._scorer.calculate_risk(
                ml_probability=adjusted,
                findings=exchange_findings,
                url=url,
                http_method=method,
            )

            static_score = compute_static_score(
                exchange_findings
            )

            # Build recommendations.
            seen_rules: set[str] = set()
            recs: List[str] = []
            for f in exchange_findings:
                if f.rule_id not in seen_rules:
                    seen_rules.add(f.rule_id)
                    title, rec = get_remediation(f.rule_id)
                    recs.append(f"{title}: {rec}")

            exchange_results.append({
                "endpoint": urlparse(url).path,
                "http_method": method,
                "risk_score": risk.score,
                "risk_level": risk.level.value,
                "findings": [
                    serialize_finding(f)
                    for f in exchange_findings
                ],
                "ml_probability": round(adjusted, 4),
                "static_score": static_score,
                "feature_vector": features,
                "recommendations": recs,
            })

            max_ml = max(max_ml, adjusted)
            max_static = max(max_static, static_score)
            if risk.score > max_risk:
                max_risk = risk.score
                max_risk_level = risk.level.value

        # Step 5: Recommendations (already built per exchange).
        emit_progress(3)
        emit_progress(4)

        return {
            "session_id": flow.session_id,
            "summary": {
                "risk_score": max_risk,
                "risk_level": max_risk_level,
                "ml_probability_max": round(max_ml, 4),
                "static_score_max": round(max_static, 4),
            },
            "results": exchange_results,
        }

    def _write(self, data: Dict[str, Any]) -> None:
        """Write a JSON line to stdout."""
        sys.stdout.write(json.dumps(data) + "\n")
        sys.stdout.flush()

    @staticmethod
    def _reconstruct_finding(
        fd: Dict[str, Any], ex: HttpExchange
    ) -> Finding:
        """Reconstruct a Finding from serialized data."""
        return Finding(
            rule_id=fd.get("rule_id", ""),
            rule_name=fd.get("rule_name", ""),
            severity=Severity(fd.get("severity", "INFO")),
            description=fd.get("description", ""),
            evidence=fd.get("evidence", ""),
            exchange=ex,
        )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main() -> None:
    """Run the IPC server."""
    server = IpcServer()
    server.run()


if __name__ == "__main__":
    main()
