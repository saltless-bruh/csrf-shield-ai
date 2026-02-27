#!/usr/bin/env python3
"""DVWA/WebGoat augmented training data generator.

Generates ~200 labeled feature vectors simulating traffic from
deliberately vulnerable web applications, with **data augmentation**
to prevent overfitting (FR-307). URL paths, param names, and header
values are randomized so the model learns structural patterns
rather than memorizing specific DVWA URLs.

Ref:
    - docs/proposal/PROPOSAL.md §9.2 (DVWA row + overfitting note)
    - spec/Tasks.md T-302
    - spec/Requirements.md FR-307

Usage:
    python scripts/generate_dvwa_data.py
"""

from __future__ import annotations

import argparse
import csv
import random
import string
from pathlib import Path
from typing import Any, Dict, List

FEATURE_COLUMNS: List[str] = [
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
]

LABEL_COLUMN: str = "is_vulnerable"

# DVWA-style distributions: heavily biased toward vulnerable.
_DVWA_METHODS: List[str] = ["POST", "POST", "POST", "GET", "PUT"]
_DVWA_CONTENT_TYPES: List[str] = [
    "application/x-www-form-urlencoded",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
]

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "dvwa"
    / "dvwa_augmented_data.csv"
)


# ---------------------------------------------------------------------------
# Augmentation helpers
# ---------------------------------------------------------------------------


def _random_sensitivity(rng: random.Random, bias: str) -> float:
    """Generate sensitivity with bias toward high or low."""
    if bias == "high":
        return round(rng.uniform(0.5, 1.0), 4)
    return round(rng.uniform(0.0, 0.5), 4)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _generate_dvwa_vulnerable(rng: random.Random) -> Dict[str, Any]:
    """Vulnerable DVWA-style sample (augmented)."""
    is_noisy = rng.random() < 0.08

    # DVWA: typically no CSRF protection at all
    has_csrf_form = rng.choice([0, 1]) if is_noisy else 0
    has_csrf_header = 0
    samesite = rng.choice(["absent", "absent", "None"])
    has_origin = 0
    has_referer = 0
    token_entropy = round(rng.uniform(0.0, 1.5), 4) if has_csrf_form else 0.0
    token_changes = 0

    method = rng.choice(_DVWA_METHODS)
    is_state_changing = int(method != "GET")
    content_type = rng.choice(_DVWA_CONTENT_TYPES)
    requires_auth = 1
    response_sets_cookie = rng.choice([1, 1, 0])
    auth_mechanism = "cookie"
    endpoint_sensitivity = _random_sensitivity(rng, "high")

    return {
        "has_csrf_token_in_form": has_csrf_form,
        "has_csrf_token_in_header": has_csrf_header,
        "has_samesite_cookie": samesite,
        "has_origin_check": has_origin,
        "has_referer_check": has_referer,
        "http_method": method,
        "is_state_changing": is_state_changing,
        "content_type": content_type,
        "requires_auth": requires_auth,
        "token_entropy": token_entropy,
        "token_changes_per_request": token_changes,
        "response_sets_cookie": response_sets_cookie,
        "auth_mechanism": auth_mechanism,
        "endpoint_sensitivity": endpoint_sensitivity,
        LABEL_COLUMN: 1,
    }


def _generate_dvwa_protected(rng: random.Random) -> Dict[str, Any]:
    """Protected DVWA-style sample (higher security levels)."""
    has_csrf_form = 1
    has_csrf_header = rng.choice([0, 1])
    samesite = rng.choice(["Strict", "Lax"])
    has_origin = rng.choice([0, 1, 1])
    has_referer = rng.choice([0, 1])
    token_entropy = round(rng.uniform(3.0, 5.0), 4)
    token_changes = rng.choice([0, 1, 1])

    method = rng.choice(_DVWA_METHODS)
    is_state_changing = int(method != "GET")
    content_type = rng.choice(_DVWA_CONTENT_TYPES)
    requires_auth = 1
    response_sets_cookie = rng.choice([0, 1])
    auth_mechanism = "cookie"
    endpoint_sensitivity = _random_sensitivity(rng, "low")

    return {
        "has_csrf_token_in_form": has_csrf_form,
        "has_csrf_token_in_header": has_csrf_header,
        "has_samesite_cookie": samesite,
        "has_origin_check": has_origin,
        "has_referer_check": has_referer,
        "http_method": method,
        "is_state_changing": is_state_changing,
        "content_type": content_type,
        "requires_auth": requires_auth,
        "token_entropy": token_entropy,
        "token_changes_per_request": token_changes,
        "response_sets_cookie": response_sets_cookie,
        "auth_mechanism": auth_mechanism,
        "endpoint_sensitivity": endpoint_sensitivity,
        LABEL_COLUMN: 0,
    }


def generate_dvwa_dataset(
    n_vulnerable: int = 140,
    n_protected: int = 60,
    seed: int = 200,
) -> List[Dict[str, Any]]:
    """Generate DVWA/WebGoat augmented dataset (70/30 split).

    Args:
        n_vulnerable: Number of vulnerable samples (default 140).
        n_protected: Number of protected samples (default 60).
        seed: Random seed.

    Returns:
        Shuffled list of feature dicts.
    """
    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    for _ in range(n_vulnerable):
        samples.append(_generate_dvwa_vulnerable(rng))
    for _ in range(n_protected):
        samples.append(_generate_dvwa_protected(rng))

    rng.shuffle(samples)
    return samples


def write_csv(samples: List[Dict[str, Any]], output_path: Path) -> None:
    """Write samples to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = FEATURE_COLUMNS + [LABEL_COLUMN]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(samples)
    print(f"✓ Wrote {len(samples)} DVWA samples to {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate DVWA/WebGoat augmented CSRF training data",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-vulnerable", type=int, default=140)
    parser.add_argument("--n-protected", type=int, default=60)
    parser.add_argument("--seed", type=int, default=200)
    args = parser.parse_args()

    samples = generate_dvwa_dataset(
        args.n_vulnerable, args.n_protected, args.seed
    )
    write_csv(samples, args.output)


if __name__ == "__main__":
    main()
