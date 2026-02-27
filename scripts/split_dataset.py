#!/usr/bin/env python3
"""Stratified train/validation/test dataset splitter.

Splits a merged CSV dataset into 70/15/15 train/val/test sets
while preserving class balance (stratified split).

Ref:
    - spec/Tasks.md T-305
    - docs/proposal/PROPOSAL.md §9.5

Usage:
    python scripts/split_dataset.py
    python scripts/split_dataset.py --input data/training/merged_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

EXPECTED_LABEL = "is_vulnerable"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = _PROJECT_ROOT / "data" / "training" / "merged_dataset.csv"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "training"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read CSV and return (fieldnames, rows)."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return list(fieldnames), rows


def stratified_split(
    rows: List[Dict[str, str]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[
    List[Dict[str, str]],
    List[Dict[str, str]],
    List[Dict[str, str]],
]:
    """Split rows into train/val/test with stratification.

    Splits each class independently to preserve label balance.

    Args:
        rows: All data rows.
        train_ratio: Fraction for training (default 0.70).
        val_ratio: Fraction for validation (default 0.15).
        seed: Random seed.

    Returns:
        Tuple of (train_rows, val_rows, test_rows).
    """
    rng = random.Random(seed)

    # Separate by class
    class_0 = [r for r in rows if r[EXPECTED_LABEL] == "0"]
    class_1 = [r for r in rows if r[EXPECTED_LABEL] == "1"]

    rng.shuffle(class_0)
    rng.shuffle(class_1)

    def _split_list(
        data: List[Dict[str, str]],
    ) -> Tuple[
        List[Dict[str, str]],
        List[Dict[str, str]],
        List[Dict[str, str]],
    ]:
        n = len(data)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        return (
            data[:n_train],
            data[n_train : n_train + n_val],
            data[n_train + n_val :],
        )

    train_0, val_0, test_0 = _split_list(class_0)
    train_1, val_1, test_1 = _split_list(class_1)

    train = train_0 + train_1
    val = val_0 + val_1
    test = test_0 + test_1

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)

    return train, val, test


def write_split(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
    output_path: Path,
) -> None:
    """Write a split to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(
    train: List[Dict[str, str]],
    val: List[Dict[str, str]],
    test: List[Dict[str, str]],
) -> None:
    """Print split summary."""
    total = len(train) + len(val) + len(test)

    def _class_balance(rows: List[Dict[str, str]]) -> str:
        n = len(rows)
        if n == 0:
            return "empty"
        n_vuln = sum(1 for r in rows if r[EXPECTED_LABEL] == "1")
        return f"{n_vuln / n * 100:.1f}% vuln"

    print(f"\n{'=' * 45}")
    print(f"DATASET SPLIT SUMMARY")
    print(f"{'=' * 45}")
    print(f"Total:      {total}")
    print(
        f"  Train:    {len(train):4d} "
        f"({len(train) / total * 100:.1f}%) "
        f"[{_class_balance(train)}]"
    )
    print(
        f"  Val:      {len(val):4d} "
        f"({len(val) / total * 100:.1f}%) "
        f"[{_class_balance(val)}]"
    )
    print(
        f"  Test:     {len(test):4d} "
        f"({len(test) / total * 100:.1f}%) "
        f"[{_class_balance(test)}]"
    )
    print(f"{'=' * 45}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Split merged CSRF dataset into train/val/test",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    fieldnames, rows = read_csv(args.input)
    print(f"Read {len(rows)} samples from {args.input}")

    train, val, test = stratified_split(rows, seed=args.seed)

    write_split(train, fieldnames, args.output_dir / "train.csv")
    write_split(val, fieldnames, args.output_dir / "val.csv")
    write_split(test, fieldnames, args.output_dir / "test.csv")

    print_summary(train, val, test)
    print(f"\n✓ Splits written to {args.output_dir}/")


if __name__ == "__main__":
    main()
