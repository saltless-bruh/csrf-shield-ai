"""Tests for data preparation pipeline.

Covers data generators, merger, and stratified splitter.

Ref:
    - spec/Tasks.md T-301 through T-305
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

import pytest

from scripts.generate_owasp_data import generate_owasp_dataset
from scripts.generate_dvwa_data import generate_dvwa_dataset
from scripts.generate_realworld_data import generate_realworld_dataset
from scripts.generate_synthetic_data import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    generate_dataset as generate_synthetic_dataset,
)
from scripts.merge_datasets import merge_datasets
from scripts.split_dataset import stratified_split


# ===========================================================================
# Helper
# ===========================================================================


def _write_temp_csv(
    samples: List[Dict[str, Any]], tmp_dir: Path
) -> Path:
    """Write samples to a temp CSV and return path."""
    path = tmp_dir / f"temp_{id(samples)}.csv"
    columns = FEATURE_COLUMNS + [LABEL_COLUMN]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(samples)
    return path


# ===========================================================================
# T-301: OWASP Generator
# ===========================================================================


class TestOWASPGenerator:
    """OWASP Benchmark-style data generator."""

    def test_generates_correct_count(self) -> None:
        samples = generate_owasp_dataset(200, 200, seed=1)
        assert len(samples) == 400

    def test_correct_columns(self) -> None:
        samples = generate_owasp_dataset(10, 10, seed=1)
        expected = set(FEATURE_COLUMNS + [LABEL_COLUMN])
        assert set(samples[0].keys()) == expected

    def test_balanced_split(self) -> None:
        samples = generate_owasp_dataset(200, 200, seed=1)
        n_vuln = sum(1 for s in samples if s[LABEL_COLUMN] == 1)
        assert n_vuln == 200

    def test_deterministic(self) -> None:
        a = generate_owasp_dataset(10, 10, seed=99)
        b = generate_owasp_dataset(10, 10, seed=99)
        assert a == b


# ===========================================================================
# T-302: DVWA Generator
# ===========================================================================


class TestDVWAGenerator:
    """DVWA/WebGoat augmented data generator."""

    def test_generates_correct_count(self) -> None:
        samples = generate_dvwa_dataset(140, 60, seed=1)
        assert len(samples) == 200

    def test_biased_toward_vulnerable(self) -> None:
        samples = generate_dvwa_dataset(140, 60, seed=1)
        n_vuln = sum(1 for s in samples if s[LABEL_COLUMN] == 1)
        assert n_vuln == 140  # 70% vulnerable

    def test_correct_columns(self) -> None:
        samples = generate_dvwa_dataset(10, 10, seed=1)
        expected = set(FEATURE_COLUMNS + [LABEL_COLUMN])
        assert set(samples[0].keys()) == expected


# ===========================================================================
# T-303: Real-World Generator
# ===========================================================================


class TestRealWorldGenerator:
    """Real-world-style data generator."""

    def test_generates_correct_count(self) -> None:
        samples = generate_realworld_dataset(120, 180, seed=1)
        assert len(samples) == 300

    def test_skewed_toward_protected(self) -> None:
        samples = generate_realworld_dataset(120, 180, seed=1)
        n_prot = sum(1 for s in samples if s[LABEL_COLUMN] == 0)
        assert n_prot == 180  # 60% protected

    def test_diverse_auth_mechanisms(self) -> None:
        samples = generate_realworld_dataset(50, 100, seed=1)
        mechs = {s["auth_mechanism"] for s in samples}
        assert len(mechs) >= 2  # At least 2 different mechanisms


# ===========================================================================
# T-304: Merge Datasets
# ===========================================================================


class TestMergeDatasets:
    """Dataset merger."""

    def test_merge_combines_all_sources(self, tmp_path: Path) -> None:
        s1 = generate_owasp_dataset(10, 10, seed=1)
        s2 = generate_dvwa_dataset(10, 5, seed=2)

        p1 = _write_temp_csv(s1, tmp_path)
        p2 = _write_temp_csv(s2, tmp_path)

        merged = merge_datasets([p1, p2], seed=42)
        assert len(merged) == 35  # 20 + 15

    def test_merge_validates_schema(self, tmp_path: Path) -> None:
        # Write a CSV with wrong columns
        bad_path = tmp_path / "bad.csv"
        with open(bad_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["wrong_col"])
            writer.writeheader()
            writer.writerow({"wrong_col": "x"})

        with pytest.raises(ValueError, match="Missing columns"):
            merge_datasets([bad_path])

    def test_merge_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            merge_datasets([tmp_path / "nonexistent.csv"])

    def test_merge_total_correct(self, tmp_path: Path) -> None:
        """Simulates full pipeline with all 4 sources."""
        synthetic = generate_synthetic_dataset(30, 30, seed=1)
        owasp = generate_owasp_dataset(20, 20, seed=2)
        dvwa = generate_dvwa_dataset(14, 6, seed=3)
        realworld = generate_realworld_dataset(12, 18, seed=4)

        paths = [
            _write_temp_csv(s, tmp_path)
            for s in [synthetic, owasp, dvwa, realworld]
        ]

        merged = merge_datasets(paths, seed=42)
        assert len(merged) == 150  # 60 + 40 + 20 + 30


# ===========================================================================
# T-305: Stratified Split
# ===========================================================================


class TestStratifiedSplit:
    """Stratified train/val/test split."""

    def _make_rows(self, n_vuln: int, n_prot: int) -> List[Dict[str, str]]:
        """Create dummy rows for split testing."""
        rows: List[Dict[str, str]] = []
        for _ in range(n_vuln):
            rows.append({"is_vulnerable": "1", "dummy": "x"})
        for _ in range(n_prot):
            rows.append({"is_vulnerable": "0", "dummy": "x"})
        return rows

    def test_split_ratios(self) -> None:
        """70/15/15 split within ±2% tolerance."""
        rows = self._make_rows(500, 500)
        train, val, test = stratified_split(rows, seed=42)

        total = len(rows)
        assert abs(len(train) / total - 0.70) < 0.02
        assert abs(len(val) / total - 0.15) < 0.02
        assert abs(len(test) / total - 0.15) < 0.02

    def test_no_data_loss(self) -> None:
        """All rows appear exactly once across splits."""
        rows = self._make_rows(200, 200)
        train, val, test = stratified_split(rows, seed=42)
        assert len(train) + len(val) + len(test) == len(rows)

    def test_stratification_preserves_balance(self) -> None:
        """Class ratio in each split ≈ overall ratio (±5%)."""
        rows = self._make_rows(300, 700)
        overall_ratio = 300 / 1000  # 30% vulnerable

        train, val, test = stratified_split(rows, seed=42)

        for split_name, split in [
            ("train", train),
            ("val", val),
            ("test", test),
        ]:
            n_vuln = sum(
                1 for r in split if r["is_vulnerable"] == "1"
            )
            split_ratio = n_vuln / len(split)
            assert abs(split_ratio - overall_ratio) < 0.05, (
                f"{split_name} ratio {split_ratio:.2f} "
                f"deviates from {overall_ratio:.2f}"
            )

    def test_deterministic(self) -> None:
        rows = self._make_rows(100, 100)
        a = stratified_split(rows, seed=99)
        b = stratified_split(rows, seed=99)
        assert a == b
