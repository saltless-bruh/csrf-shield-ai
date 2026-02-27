#!/usr/bin/env python3
"""Real-world-style training data generator.

Generates ~300 labeled feature vectors simulating diverse,
modern web application traffic (SPA frameworks, REST APIs,
mixed auth patterns). 40/60 vulnerable/protected split to
mimic real-world skew toward mixed protection.

Ref:
    - docs/proposal/PROPOSAL.md §9.2 (Real-world HAR row)
    - spec/Tasks.md T-303

Usage:
    python scripts/generate_realworld_data.py
"""

from __future__ import annotations

import argparse
import csv
import random
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

# Real-world: more diverse methods & content types.
_RW_METHODS: List[str] = ["GET", "POST", "POST", "PUT", "DELETE", "PATCH"]
_RW_CONTENT_TYPES: List[str] = [
    "application/x-www-form-urlencoded",
    "application/json",
    "application/json",
    "multipart/form-data",
    "text/plain",
]
_RW_AUTH_MECHS: List[str] = ["cookie", "header_only", "mixed", "none"]

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "realworld"
    / "realworld_data.csv"
)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _generate_rw_vulnerable(rng: random.Random) -> Dict[str, Any]:
    """Vulnerable real-world-style endpoint."""
    is_noisy = rng.random() < 0.15  # Higher noise in real-world

    has_csrf_form = rng.choice([0, 1]) if is_noisy else 0
    has_csrf_header = rng.choice([0, 1]) if is_noisy else 0
    samesite = rng.choice(["absent", "None", "absent", "Lax"]) if is_noisy \
        else rng.choice(["absent", "None"])
    has_origin = rng.choice([0, 1]) if is_noisy else 0
    has_referer = rng.choice([0, 1]) if is_noisy else 0
    token_entropy = round(rng.uniform(0.0, 2.5), 4) if has_csrf_form else 0.0
    token_changes = rng.choice([0, 1]) if is_noisy else 0

    method = rng.choice(_RW_METHODS)
    is_state_changing = int(method not in ("GET", "HEAD", "OPTIONS"))
    content_type = rng.choice(_RW_CONTENT_TYPES)
    requires_auth = rng.choice([0, 1, 1])
    response_sets_cookie = rng.choice([0, 1])
    auth_mechanism = rng.choice(["cookie", "cookie", "mixed", "none"])
    endpoint_sensitivity = round(rng.uniform(0.2, 1.0), 4)

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


def _generate_rw_protected(rng: random.Random) -> Dict[str, Any]:
    """Protected real-world-style endpoint (modern frameworks)."""
    is_noisy = rng.random() < 0.12

    has_csrf_form = rng.choice([0, 1]) if is_noisy else rng.choice([1, 1, 0])
    has_csrf_header = rng.choice([0, 1, 1])
    samesite = rng.choice(["Strict", "Lax", "Lax", "None"]) if is_noisy \
        else rng.choice(["Strict", "Lax"])
    has_origin = rng.choice([0, 1, 1])
    has_referer = rng.choice([0, 1])
    token_entropy = round(rng.uniform(3.0, 5.8), 4)
    token_changes = rng.choice([0, 1]) if is_noisy else 1

    method = rng.choice(_RW_METHODS)
    is_state_changing = int(method not in ("GET", "HEAD", "OPTIONS"))
    content_type = rng.choice(_RW_CONTENT_TYPES)
    requires_auth = rng.choice([0, 1, 1])
    response_sets_cookie = rng.choice([0, 1])
    auth_mechanism = rng.choice(_RW_AUTH_MECHS)
    endpoint_sensitivity = round(rng.uniform(0.0, 0.7), 4)

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


def generate_realworld_dataset(
    n_vulnerable: int = 120,
    n_protected: int = 180,
    seed: int = 300,
) -> List[Dict[str, Any]]:
    """Generate real-world-style dataset (40/60 split).

    Args:
        n_vulnerable: Number of vulnerable samples (default 120).
        n_protected: Number of protected samples (default 180).
        seed: Random seed.

    Returns:
        Shuffled list of feature dicts.
    """
    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    for _ in range(n_vulnerable):
        samples.append(_generate_rw_vulnerable(rng))
    for _ in range(n_protected):
        samples.append(_generate_rw_protected(rng))

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
    print(f"✓ Wrote {len(samples)} real-world samples to {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate real-world-style CSRF training data",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-vulnerable", type=int, default=120)
    parser.add_argument("--n-protected", type=int, default=180)
    parser.add_argument("--seed", type=int, default=300)
    args = parser.parse_args()

    samples = generate_realworld_dataset(
        args.n_vulnerable, args.n_protected, args.seed
    )
    write_csv(samples, args.output)


if __name__ == "__main__":
    main()
