#!/usr/bin/env python3
"""Synthetic CSRF training data generator.

Generates labeled feature vectors for ML model training. Produces
~300 vulnerable and ~300 protected samples with realistic feature
distributions and ~10% deliberate noise for overfitting prevention.

Ref:
    - docs/proposal/PROPOSAL.md §9.2, §9.3.2
    - spec/Requirements.md FR-306
    - spec/Tasks.md T-151 → T-154

Usage:
    python scripts/generate_synthetic_data.py
    python scripts/generate_synthetic_data.py --seed 42 --output data/synthetic/out.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

# Feature column names matching PROPOSAL §9.3.2
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

# Categorical value spaces
SAMESITE_VALUES: List[str] = ["None", "Lax", "Strict", "absent"]
HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
CONTENT_TYPES: List[str] = [
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "application/json",
    "text/plain",
]
AUTH_MECHANISMS: List[str] = ["cookie", "header_only", "mixed", "none"]

# Default output path
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "synthetic_csrf_data.csv"


# ---------------------------------------------------------------------------
# Sample Generators
# ---------------------------------------------------------------------------


def generate_vulnerable_sample(rng: random.Random) -> Dict[str, Any]:
    """Generate a single vulnerable sample (label=1).

    Vulnerable endpoints typically lack CSRF protections:
    - No CSRF token in form or header
    - Missing or None SameSite cookie
    - No origin/referer checks
    - State-changing methods with cookie auth

    ~10% of samples include deliberate noise (partial protections).

    Args:
        rng: Seeded random instance for reproducibility.

    Returns:
        Dict with all 14 features + label.
    """
    is_noisy = rng.random() < 0.10

    if is_noisy:
        # Noisy: has some protections but still vulnerable overall
        has_csrf_form = rng.choice([0, 1])
        has_csrf_header = 0
        samesite = rng.choice(["None", "Lax", "absent"])
        has_origin = rng.choice([0, 1])
        has_referer = 0
        token_entropy = round(rng.uniform(0.0, 2.5), 4) if has_csrf_form else 0.0
        token_changes = 0
    else:
        # Standard vulnerable: no CSRF protection
        has_csrf_form = 0
        has_csrf_header = 0
        samesite = rng.choice(["None", "absent", "absent", "absent"])  # mostly absent
        has_origin = 0
        has_referer = 0
        token_entropy = 0.0
        token_changes = 0

    method = rng.choice(["POST", "POST", "PUT", "DELETE", "PATCH"])
    is_state_changing = 1  # vulnerable endpoints are state-changing
    content_type = rng.choice([
        "application/x-www-form-urlencoded",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "application/json",
    ])
    requires_auth = 1
    response_sets_cookie = rng.choice([0, 1, 1])  # usually yes
    auth_mechanism = rng.choice(["cookie", "cookie", "cookie", "mixed"])
    endpoint_sensitivity = round(rng.uniform(0.4, 1.0), 4)

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


def generate_protected_sample(rng: random.Random) -> Dict[str, Any]:
    """Generate a single protected sample (label=0).

    Protected endpoints have adequate CSRF protections:
    - CSRF token in form and/or header
    - SameSite=Strict or Lax
    - Origin/referer checks present
    - High token entropy with per-request rotation

    ~10% of samples include deliberate noise (weaker protections).

    Args:
        rng: Seeded random instance for reproducibility.

    Returns:
        Dict with all 14 features + label.
    """
    is_noisy = rng.random() < 0.10

    if is_noisy:
        # Noisy: weaker protections but still protected overall
        has_csrf_form = rng.choice([0, 1])
        has_csrf_header = rng.choice([0, 1])
        samesite = rng.choice(["Lax", "None", "absent"])
        has_origin = rng.choice([0, 1])
        has_referer = rng.choice([0, 1])
        token_entropy = round(rng.uniform(2.0, 4.0), 4)
        token_changes = rng.choice([0, 1])
    else:
        # Standard protected: strong CSRF protections
        has_csrf_form = 1
        has_csrf_header = rng.choice([0, 1])
        samesite = rng.choice(["Strict", "Strict", "Lax"])
        has_origin = rng.choice([1, 1, 0])  # usually yes
        has_referer = rng.choice([0, 1])
        token_entropy = round(rng.uniform(3.5, 6.0), 4)
        token_changes = 1

    method = rng.choice(["POST", "POST", "GET", "PUT", "DELETE"])
    is_state_changing = rng.choice([0, 1, 1])
    content_type = rng.choice(CONTENT_TYPES)
    requires_auth = rng.choice([0, 1, 1])
    response_sets_cookie = rng.choice([0, 1])
    auth_mechanism = rng.choice(AUTH_MECHANISMS)
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


# ---------------------------------------------------------------------------
# Dataset Generation
# ---------------------------------------------------------------------------


def generate_dataset(
    n_vulnerable: int = 300,
    n_protected: int = 300,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generate a complete labeled dataset.

    Args:
        n_vulnerable: Number of vulnerable samples to generate.
        n_protected: Number of protected samples to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of dicts, each containing 14 features + 1 label.
    """
    rng = random.Random(seed)
    samples: List[Dict[str, Any]] = []

    for _ in range(n_vulnerable):
        samples.append(generate_vulnerable_sample(rng))

    for _ in range(n_protected):
        samples.append(generate_protected_sample(rng))

    # Shuffle to avoid positional bias
    rng.shuffle(samples)
    return samples


def write_csv(samples: List[Dict[str, Any]], output_path: Path) -> None:
    """Write samples to CSV file.

    Args:
        samples: List of feature dicts.
        output_path: Path to write CSV to.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = FEATURE_COLUMNS + [LABEL_COLUMN]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(samples)

    print(f"✓ Wrote {len(samples)} samples to {output_path}")


def print_summary(samples: List[Dict[str, Any]]) -> None:
    """Print dataset summary statistics.

    Args:
        samples: List of feature dicts.
    """
    total = len(samples)
    n_vuln = sum(1 for s in samples if s[LABEL_COLUMN] == 1)
    n_prot = total - n_vuln

    # Token entropy stats for protected samples
    prot_entropies = [s["token_entropy"] for s in samples if s[LABEL_COLUMN] == 0]
    vuln_entropies = [s["token_entropy"] for s in samples if s[LABEL_COLUMN] == 1]

    # Auth mechanism distribution
    auth_dist: Dict[str, int] = {}
    for s in samples:
        mech = s["auth_mechanism"]
        auth_dist[mech] = auth_dist.get(mech, 0) + 1

    print("\n" + "=" * 50)
    print("SYNTHETIC DATA SUMMARY")
    print("=" * 50)
    print(f"Total samples:        {total}")
    print(f"  Vulnerable (1):     {n_vuln} ({n_vuln / total * 100:.1f}%)")
    print(f"  Protected  (0):     {n_prot} ({n_prot / total * 100:.1f}%)")
    print(f"\nToken entropy (protected): "
          f"mean={_mean(prot_entropies):.2f}, "
          f"min={min(prot_entropies):.2f}, "
          f"max={max(prot_entropies):.2f}")
    print(f"Token entropy (vuln):      "
          f"mean={_mean(vuln_entropies):.2f}, "
          f"min={min(vuln_entropies):.2f}, "
          f"max={max(vuln_entropies):.2f}")
    print(f"\nAuth mechanism distribution:")
    for mech, count in sorted(auth_dist.items()):
        print(f"  {mech:15s} {count:4d} ({count / total * 100:.1f}%)")
    print("=" * 50)


def _mean(values: List[float]) -> float:
    """Calculate mean of a list of floats."""
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for synthetic data generation."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic CSRF training data",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--n-vulnerable",
        type=int,
        default=300,
        help="Number of vulnerable samples (default: 300)",
    )
    parser.add_argument(
        "--n-protected",
        type=int,
        default=300,
        help="Number of protected samples (default: 300)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    print(f"Generating {args.n_vulnerable + args.n_protected} synthetic samples (seed={args.seed})...")
    samples = generate_dataset(args.n_vulnerable, args.n_protected, args.seed)
    write_csv(samples, args.output)
    print_summary(samples)


if __name__ == "__main__":
    main()
