"""Unit tests for synthetic data generator.

Tests schema validation, label balance, value ranges, and
reproducibility of the generated dataset.

Ref:
    - spec/Tasks.md T-155
    - .agent/instructions/testing_strategy.instructions.md §2.1
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

# Import from scripts — add to path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_synthetic_data import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    generate_dataset,
    generate_protected_sample,
    generate_vulnerable_sample,
    write_csv,
)

import random


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = FEATURE_COLUMNS + [LABEL_COLUMN]
VALID_SAMESITE = {"None", "Lax", "Strict", "absent"}
VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
VALID_CONTENT_TYPES = {
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "application/json",
    "text/plain",
}
VALID_AUTH_MECHANISMS = {"cookie", "header_only", "mixed", "none"}


# ---------------------------------------------------------------------------
# Schema Validation
# ---------------------------------------------------------------------------


class TestSchema:
    """Tests for correct column schema."""

    def test_vulnerable_sample_has_all_columns(self) -> None:
        """Vulnerable sample has all 14 features + label."""
        rng = random.Random(42)
        sample = generate_vulnerable_sample(rng)
        assert set(sample.keys()) == set(EXPECTED_COLUMNS)

    def test_protected_sample_has_all_columns(self) -> None:
        """Protected sample has all 14 features + label."""
        rng = random.Random(42)
        sample = generate_protected_sample(rng)
        assert set(sample.keys()) == set(EXPECTED_COLUMNS)

    def test_dataset_has_correct_columns(self) -> None:
        """Full dataset has correct column order."""
        samples = generate_dataset(5, 5, seed=42)
        for sample in samples:
            assert set(sample.keys()) == set(EXPECTED_COLUMNS)

    def test_no_nan_values(self) -> None:
        """No NaN or None values in dataset."""
        samples = generate_dataset(50, 50, seed=42)
        for sample in samples:
            for col, val in sample.items():
                assert val is not None, f"NaN in column {col}"
                if isinstance(val, float):
                    assert val == val, f"NaN float in column {col}"  # NaN != NaN


# ---------------------------------------------------------------------------
# Label Balance
# ---------------------------------------------------------------------------


class TestLabelBalance:
    """Tests for label distribution."""

    def test_correct_count(self) -> None:
        """Dataset has expected total sample count."""
        samples = generate_dataset(300, 300, seed=42)
        assert len(samples) == 600

    def test_label_balance(self) -> None:
        """Dataset has ~50/50 label balance."""
        samples = generate_dataset(300, 300, seed=42)
        n_vuln = sum(1 for s in samples if s[LABEL_COLUMN] == 1)
        n_prot = sum(1 for s in samples if s[LABEL_COLUMN] == 0)
        assert n_vuln == 300
        assert n_prot == 300

    def test_vulnerable_label_value(self) -> None:
        """Vulnerable samples have label=1."""
        rng = random.Random(42)
        sample = generate_vulnerable_sample(rng)
        assert sample[LABEL_COLUMN] == 1

    def test_protected_label_value(self) -> None:
        """Protected samples have label=0."""
        rng = random.Random(42)
        sample = generate_protected_sample(rng)
        assert sample[LABEL_COLUMN] == 0


# ---------------------------------------------------------------------------
# Value Ranges
# ---------------------------------------------------------------------------


class TestValueRanges:
    """Tests for feature value validity."""

    def test_bool_features_are_binary(self) -> None:
        """Boolean features are either 0 or 1."""
        bool_cols = [
            "has_csrf_token_in_form",
            "has_csrf_token_in_header",
            "has_origin_check",
            "has_referer_check",
            "is_state_changing",
            "requires_auth",
            "token_changes_per_request",
            "response_sets_cookie",
        ]
        samples = generate_dataset(50, 50, seed=42)
        for sample in samples:
            for col in bool_cols:
                assert sample[col] in (0, 1), f"{col}={sample[col]} not binary"

    def test_token_entropy_range(self) -> None:
        """Token entropy is between 0.0 and 6.0."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert 0.0 <= sample["token_entropy"] <= 6.0, (
                f"token_entropy={sample['token_entropy']} out of range"
            )

    def test_endpoint_sensitivity_range(self) -> None:
        """Endpoint sensitivity is between 0.0 and 1.0."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert 0.0 <= sample["endpoint_sensitivity"] <= 1.0, (
                f"endpoint_sensitivity={sample['endpoint_sensitivity']} out of range"
            )

    def test_samesite_values(self) -> None:
        """SameSite cookie values are valid."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert sample["has_samesite_cookie"] in VALID_SAMESITE

    def test_http_method_values(self) -> None:
        """HTTP methods are valid."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert sample["http_method"] in VALID_METHODS

    def test_content_type_values(self) -> None:
        """Content types are valid."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert sample["content_type"] in VALID_CONTENT_TYPES

    def test_auth_mechanism_values(self) -> None:
        """Auth mechanisms are valid."""
        samples = generate_dataset(100, 100, seed=42)
        for sample in samples:
            assert sample["auth_mechanism"] in VALID_AUTH_MECHANISMS


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Tests for deterministic output with same seed."""

    def test_same_seed_same_output(self) -> None:
        """Same seed produces identical dataset."""
        ds1 = generate_dataset(50, 50, seed=123)
        ds2 = generate_dataset(50, 50, seed=123)
        assert ds1 == ds2

    def test_different_seed_different_output(self) -> None:
        """Different seeds produce different datasets."""
        ds1 = generate_dataset(50, 50, seed=1)
        ds2 = generate_dataset(50, 50, seed=2)
        assert ds1 != ds2


# ---------------------------------------------------------------------------
# CSV Output
# ---------------------------------------------------------------------------


class TestCsvOutput:
    """Tests for CSV file writing."""

    def test_csv_written(self, tmp_path: Path) -> None:
        """CSV file is created with correct row count."""
        samples = generate_dataset(10, 10, seed=42)
        out = tmp_path / "test.csv"
        write_csv(samples, out)

        assert out.exists()
        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 20

    def test_csv_columns(self, tmp_path: Path) -> None:
        """CSV has correct column headers."""
        samples = generate_dataset(5, 5, seed=42)
        out = tmp_path / "test.csv"
        write_csv(samples, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == EXPECTED_COLUMNS

    def test_csv_creates_directories(self, tmp_path: Path) -> None:
        """write_csv creates parent directories if missing."""
        samples = generate_dataset(5, 5, seed=42)
        out = tmp_path / "nested" / "dir" / "test.csv"
        write_csv(samples, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# Feature Distribution Sanity
# ---------------------------------------------------------------------------


class TestFeatureDistributions:
    """Sanity checks for realistic feature distributions."""

    def test_vulnerable_mostly_no_csrf_token(self) -> None:
        """Most vulnerable samples have no CSRF token in form."""
        rng = random.Random(42)
        samples = [generate_vulnerable_sample(rng) for _ in range(200)]
        n_no_token = sum(1 for s in samples if s["has_csrf_token_in_form"] == 0)
        # ~90% should have no token (with ~10% noise)
        assert n_no_token >= 160, f"Only {n_no_token}/200 vuln have no token"

    def test_protected_mostly_has_csrf_token(self) -> None:
        """Most protected samples have CSRF token in form."""
        rng = random.Random(42)
        samples = [generate_protected_sample(rng) for _ in range(200)]
        n_has_token = sum(1 for s in samples if s["has_csrf_token_in_form"] == 1)
        # ~90% should have token (with ~10% noise)
        assert n_has_token >= 160, f"Only {n_has_token}/200 prot have token"

    def test_protected_higher_entropy(self) -> None:
        """Protected samples have higher mean token entropy than vulnerable."""
        samples = generate_dataset(200, 200, seed=42)
        vuln_ent = [s["token_entropy"] for s in samples if s[LABEL_COLUMN] == 1]
        prot_ent = [s["token_entropy"] for s in samples if s[LABEL_COLUMN] == 0]

        avg_vuln = sum(vuln_ent) / len(vuln_ent)
        avg_prot = sum(prot_ent) / len(prot_ent)
        assert avg_prot > avg_vuln, (
            f"Protected entropy ({avg_prot:.2f}) should be > vulnerable ({avg_vuln:.2f})"
        )
