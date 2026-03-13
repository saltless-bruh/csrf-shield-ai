"""Tests for the inference engine (predictor + heuristics).

Ref:
    - src/ml/predictor.py
    - src/ml/heuristics.py
    - spec/Tasks.md T-321, T-322, T-323
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pytest

from src.input.models import Finding, HttpExchange, Severity
from src.ml.heuristics import (
    _count_protections,
    _has_action_params,
    _is_sensitive_endpoint,
    apply_heuristics,
)
from src.ml.predictor import CsrfPredictor


# ===========================================================================
# Helpers
# ===========================================================================


def _make_finding(rule_id: str) -> Finding:
    """Create a minimal Finding for testing."""
    ex = HttpExchange(
        request_method="POST",
        request_url="https://example.com/test",
        request_headers={},
        request_cookies={},
        request_body=None,
        request_content_type="",
        response_status=200,
        response_headers={},
        response_body=None,
        timestamp=datetime(2026, 2, 27),
    )
    return Finding(
        rule_id=rule_id,
        rule_name="Test",
        severity=Severity.HIGH,
        description="Test finding",
        evidence="",
        exchange=ex,
    )


def _sample_features() -> Dict[str, Any]:
    """Feature dict for a vulnerable POST with no protections."""
    return {
        "has_csrf_token_in_form": 0,
        "has_csrf_token_in_header": 0,
        "has_samesite_cookie": "absent",
        "has_origin_check": 0,
        "has_referer_check": 0,
        "http_method": "POST",
        "is_state_changing": 1,
        "content_type": "application/x-www-form-urlencoded",
        "requires_auth": 1,
        "token_entropy": 0.0,
        "token_changes_per_request": 0,
        "response_sets_cookie": 1,
        "auth_mechanism": "cookie",
        "endpoint_sensitivity": 0.8,
    }


# ===========================================================================
# T-321: Predictor
# ===========================================================================


class TestCsrfPredictor:
    """CsrfPredictor inference tests."""

    @pytest.fixture(scope="class")
    def predictor(self) -> CsrfPredictor:
        return CsrfPredictor()

    def test_loads_model(self, predictor: CsrfPredictor) -> None:
        """Model loads and has predict_proba."""
        assert hasattr(predictor.model, "predict_proba")
        assert len(predictor.columns) > 0

    def test_predict_returns_probability(
        self, predictor: CsrfPredictor
    ) -> None:
        """predict() returns float in [0, 1]."""
        prob = predictor.predict(_sample_features())
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_predict_vulnerable_high(
        self, predictor: CsrfPredictor
    ) -> None:
        """Unprotected POST → high probability."""
        prob = predictor.predict(_sample_features())
        assert prob > 0.5

    def test_predict_protected_low(
        self, predictor: CsrfPredictor
    ) -> None:
        """Well-protected endpoint → low probability."""
        features = _sample_features()
        features["has_csrf_token_in_form"] = 1
        features["has_csrf_token_in_header"] = 1
        features["has_samesite_cookie"] = "Strict"
        features["has_origin_check"] = 1
        features["token_entropy"] = 4.5
        features["token_changes_per_request"] = 1
        prob = predictor.predict(features)
        assert prob < 0.5

    def test_predict_batch(
        self, predictor: CsrfPredictor
    ) -> None:
        """Batch prediction returns list of same length."""
        batch = [_sample_features(), _sample_features()]
        probs = predictor.predict_batch(batch)
        assert len(probs) == 2
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_predict_batch_empty(
        self, predictor: CsrfPredictor
    ) -> None:
        """Empty batch returns empty list."""
        assert predictor.predict_batch([]) == []


# ===========================================================================
# T-322: Heuristics
# ===========================================================================


class TestHeuristics:
    """Heuristic boost/reduce rules."""

    def test_csrf004_boost(self) -> None:
        """CSRF-004 (static token) → floor at 0.95.

        Include all protection-absence findings so defense-in-depth
        doesn't also apply (0 protections → no reduction).
        """
        findings = [
            _make_finding("CSRF-004"),
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(0.50, findings, "/test", "POST")
        assert result >= 0.95

    def test_csrf004_already_high(self) -> None:
        """CSRF-004 with already-high score stays high."""
        findings = [
            _make_finding("CSRF-004"),
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(0.98, findings, "/test", "POST")
        assert result >= 0.98

    def test_sensitive_endpoint_boost(self) -> None:
        """Sensitive URL → ×1.2 boost (no defense-in-depth)."""
        # All protection-absence rules present → 0 protections
        findings = [
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(
            0.50, findings, "https://bank.com/admin/users", "POST"
        )
        assert abs(result - 0.60) < 0.01

    def test_sensitive_transfer(self) -> None:
        """Transfer endpoint → boost (no defense-in-depth)."""
        findings = [
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(
            0.50, findings, "https://bank.com/api/transfer", "POST"
        )
        assert result > 0.50

    def test_get_action_params_boost(self) -> None:
        """GET with ?action= → ×1.3 boost (no defense-in-depth)."""
        findings = [
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(
            0.50, findings, "https://ex.com/api?action=delete", "GET"
        )
        assert abs(result - 0.65) < 0.01

    def test_get_no_action_params(self) -> None:
        """GET without action params → no boost (no defense-in-depth)."""
        findings = [
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(
            0.50, findings, "https://ex.com/page?id=1", "GET"
        )
        assert result == 0.50

    def test_defense_in_depth(self) -> None:
        """2+ protections → ×0.6 reduction."""
        # No CSRF-001 and no CSRF-002 in findings → protections present
        findings: List[Finding] = []
        result = apply_heuristics(
            0.80, findings, "/test", "POST"
        )
        # All 5 protection rules absent from findings → 5 protections
        assert result < 0.80

    def test_defense_all_absent(self) -> None:
        """All protection rules firing → 0 protections → no reduction."""
        findings = [
            _make_finding("CSRF-001"),
            _make_finding("CSRF-002"),
            _make_finding("CSRF-005"),
            _make_finding("CSRF-007"),
            _make_finding("CSRF-009"),
        ]
        result = apply_heuristics(
            0.80, findings, "/test", "POST"
        )
        assert result == 0.80  # No reduction

    def test_clamp_high(self) -> None:
        """Score clamped to max 1.0."""
        result = apply_heuristics(
            0.90,
            [_make_finding("CSRF-004")],
            "https://bank.com/admin/transfer",
            "GET",
        )
        assert result <= 1.0

    def test_clamp_low(self) -> None:
        """Score cannot go below 0.0."""
        result = apply_heuristics(0.0, [], "/test", "POST")
        assert result >= 0.0


class TestHeuristicHelpers:
    """Helper function tests."""

    def test_sensitive_admin(self) -> None:
        assert _is_sensitive_endpoint("https://ex.com/admin") is True

    def test_sensitive_transfer(self) -> None:
        assert _is_sensitive_endpoint("https://ex.com/api/transfer") is True

    def test_not_sensitive(self) -> None:
        assert _is_sensitive_endpoint("https://ex.com/home") is False

    def test_action_params_present(self) -> None:
        assert _has_action_params("https://ex.com/?action=del") is True

    def test_action_params_absent(self) -> None:
        assert _has_action_params("https://ex.com/?id=1") is False

    def test_count_protections_all(self) -> None:
        """No protection-absence findings → all 5 protections."""
        assert _count_protections(set()) == 5

    def test_count_protections_none(self) -> None:
        """All protection-absence findings → 0 protections."""
        all_rules = {"CSRF-001", "CSRF-002",
                     "CSRF-005", "CSRF-007", "CSRF-009"}
        assert _count_protections(all_rules) == 0
