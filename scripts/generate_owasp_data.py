#!/usr/bin/env python3
"""OWASP Benchmark-style training data generator.

Generates ~400 labeled feature vectors simulating enterprise Java
web application patterns (Spring, JSP, Struts). Balanced 50/50
vulnerable/protected split.

Ref:
    - docs/proposal/PROPOSAL.md §9.2 (OWASP Benchmark row)
    - spec/Tasks.md T-301
    - spec/Requirements.md FR-303

Usage:
    python scripts/generate_owasp_data.py
    python scripts/generate_owasp_data.py --seed 123 --output data/owasp/out.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

# Reuse column definitions from the synthetic generator.
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

# OWASP Benchmark-specific distributions.
_OWASP_METHODS: List[str] = ["POST", "POST", "POST", "PUT", "GET"]
_OWASP_CONTENT_TYPES: List[str] = [
    "application/x-www-form-urlencoded",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "application/json",
]

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "owasp"
    / "owasp_benchmark_data.csv"
)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _generate_owasp_vulnerable(rng: random.Random) -> Dict[str, Any]:
    """Vulnerable OWASP-style endpoint (missing protections)."""
    is_noisy = rng.random() < 0.10

    has_csrf_form = rng.choice([0, 1]) if is_noisy else 0
    has_csrf_header = 0
    samesite = rng.choice(["None", "absent", "absent"])
    has_origin = rng.choice([0, 1]) if is_noisy else 0
    has_referer = 0
    token_entropy = round(rng.uniform(0.0, 2.0), 4) if has_csrf_form else 0.0
    token_changes = 0

    method = rng.choice(_OWASP_METHODS)
    is_state_changing = int(method != "GET")
    content_type = rng.choice(_OWASP_CONTENT_TYPES)
    requires_auth = 1
    response_sets_cookie = rng.choice([0, 1, 1])
    auth_mechanism = rng.choice(["cookie", "cookie", "mixed"])
    endpoint_sensitivity = round(rng.uniform(0.3, 1.0), 4)

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


def _generate_owasp_protected(rng: random.Random) -> Dict[str, Any]:
    """Protected OWASP-style endpoint (Spring Security patterns)."""
    is_noisy = rng.random() < 0.10

    has_csrf_form = rng.choice([0, 1]) if is_noisy else 1
    has_csrf_header = rng.choice([0, 1])
    samesite = rng.choice(["Strict", "Lax", "Lax"])
    has_origin = rng.choice([0, 1]) if is_noisy else 1
    has_referer = rng.choice([0, 1])
    token_entropy = round(rng.uniform(3.5, 5.5), 4)
    token_changes = rng.choice([0, 1]) if is_noisy else 1

    method = rng.choice(_OWASP_METHODS)
    is_state_changing = int(method != "GET")
    content_type = rng.choice(_OWASP_CONTENT_TYPES)
    requires_auth = rng.choice([0, 1, 1])
    response_sets_cookie = rng.choice([0, 1])
    auth_mechanism = rng.choice(["cookie", "cookie", "mixed", "none"])
    endpoint_sensitivity = round(rng.uniform(0.0, 0.6), 4)

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


def generate_owasp_dataset(
    n_vulnerable: int = 200,
    n_protected: int = 200,
    seed: int = 100,
) -> List[Dict[str, Any]]:
    """Generate OWASP Benchmark-style dataset.

    Args:
        n_vulnerable: Number of vulnerable samples.
        n_protected: Number of protected samples.
        seed: Random seed.

    Returns:
        Shuffled list of feature dicts.
    """
    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    for _ in range(n_vulnerable):
        samples.append(_generate_owasp_vulnerable(rng))
    for _ in range(n_protected):
        samples.append(_generate_owasp_protected(rng))

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
    print(f"✓ Wrote {len(samples)} OWASP samples to {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate OWASP Benchmark-style CSRF training data",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-vulnerable", type=int, default=200)
    parser.add_argument("--n-protected", type=int, default=200)
    parser.add_argument("--seed", type=int, default=100)
    args = parser.parse_args()

    samples = generate_owasp_dataset(
        args.n_vulnerable, args.n_protected, args.seed
    )
    write_csv(samples, args.output)


if __name__ == "__main__":
    main()
