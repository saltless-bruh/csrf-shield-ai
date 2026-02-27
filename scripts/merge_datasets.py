#!/usr/bin/env python3
"""Merge all CSRF training data sources into a unified dataset.

Combines synthetic, OWASP, DVWA, and real-world CSVs. Validates
schema consistency and prints summary statistics.

Ref:
    - spec/Tasks.md T-304
    - docs/proposal/PROPOSAL.md §9.2

Usage:
    python scripts/merge_datasets.py
    python scripts/merge_datasets.py --output data/training/merged_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Any, Dict, List

# Expected columns in every source file.
EXPECTED_COLUMNS = [
    "has_csrf_token_in_form",
    "has_csrf_token_in_header",
    "has_samesite_cookie",
    "has_origin_check",
    "has_referer_check",
    "http_method",
    "is_state_changing",
    "content_type",
    "requires_auth",
    "token_entropy",
    "token_changes_per_request",
    "response_sets_cookie",
    "auth_mechanism",
    "endpoint_sensitivity",
    "is_vulnerable",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default source paths (relative to project root).
DEFAULT_SOURCES: List[Path] = [
    _PROJECT_ROOT / "data" / "synthetic" / "synthetic_csrf_data.csv",
    _PROJECT_ROOT / "data" / "owasp" / "owasp_benchmark_data.csv",
    _PROJECT_ROOT / "data" / "dvwa" / "dvwa_augmented_data.csv",
    _PROJECT_ROOT / "data" / "realworld" / "realworld_data.csv",
]

DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "training" / "merged_dataset.csv"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def read_csv(path: Path) -> List[Dict[str, str]]:
    """Read a CSV file and return rows as dicts."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def validate_schema(
    rows: List[Dict[str, str]], source: Path
) -> None:
    """Validate all expected columns are present.

    Raises:
        ValueError: If columns are missing or unexpected.
    """
    if not rows:
        raise ValueError(f"Empty dataset: {source}")

    actual = set(rows[0].keys())
    expected = set(EXPECTED_COLUMNS)

    missing = expected - actual
    if missing:
        raise ValueError(
            f"Missing columns in {source}: {missing}"
        )


def merge_datasets(
    source_paths: List[Path],
    seed: int = 42,
) -> List[Dict[str, str]]:
    """Merge multiple CSV datasets into one shuffled list.

    Args:
        source_paths: List of CSV file paths to merge.
        seed: Random seed for shuffling.

    Returns:
        Shuffled list of all rows from all sources.

    Raises:
        FileNotFoundError: If a source file does not exist.
        ValueError: If a source has incompatible schema.
    """
    all_rows: List[Dict[str, str]] = []

    for path in source_paths:
        if not path.exists():
            raise FileNotFoundError(f"Source not found: {path}")

        rows = read_csv(path)
        validate_schema(rows, path)
        all_rows.extend(rows)
        print(f"  + {path.name}: {len(rows)} samples")

    rng = random.Random(seed)
    rng.shuffle(all_rows)

    return all_rows


def write_merged(
    rows: List[Dict[str, str]], output_path: Path
) -> None:
    """Write merged dataset to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Merged {len(rows)} total samples → {output_path}")


def print_summary(rows: List[Dict[str, str]]) -> None:
    """Print class balance summary."""
    total = len(rows)
    n_vuln = sum(1 for r in rows if r["is_vulnerable"] == "1")
    n_prot = total - n_vuln

    print(f"\n{'=' * 40}")
    print(f"MERGED DATASET SUMMARY")
    print(f"{'=' * 40}")
    print(f"Total samples:    {total}")
    print(f"  Vulnerable (1): {n_vuln} ({n_vuln / total * 100:.1f}%)")
    print(f"  Protected  (0): {n_prot} ({n_prot / total * 100:.1f}%)")
    print(f"{'=' * 40}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Merge CSRF training datasets",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for shuffling (default: 42)",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        type=Path,
        default=None,
        help="Override default source CSV paths",
    )
    args = parser.parse_args()

    sources = args.sources or DEFAULT_SOURCES
    print(f"Merging {len(sources)} data sources...")

    rows = merge_datasets(sources, args.seed)
    write_merged(rows, args.output)
    print_summary(rows)


if __name__ == "__main__":
    main()
