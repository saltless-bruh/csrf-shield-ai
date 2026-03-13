"""Risk scoring engine for CSRF Shield AI.

Calculates a 0–100 risk score using the Base Score + Modifier
model described in PROPOSAL.md §10.

Formula:
    Base = (W_ml × ML_Prob + W_static × Static_Normalized) × 100
    Final = Clamp(Base + Context_Modifier_Sum, 0, 100)

Ref:
    - docs/proposal/PROPOSAL.md §10.1, §10.2, §10.3
    - spec/Tasks.md T-401 through T-405
    - spec/Requirements.md FR-401, FR-402, FR-403, FR-404
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

from src.input.models import Finding, Severity, RiskLevel
from src.config import SETTINGS

logger = logging.getLogger(__name__)

# Weights for the base score formula (PROPOSAL §10.1).
scoring_weights = SETTINGS.get("scoring", {}).get("weights", {})
W_ML: float = scoring_weights.get("ml", 0.50)
W_STATIC: float = scoring_weights.get("static", 0.50)

# Severity → numeric mapping for static normalization (T-402).
_YAML_SEVERITY_MAP = SETTINGS.get("severity_map", {})
SEVERITY_MAP: dict[Severity, float] = {
    Severity.CRITICAL: _YAML_SEVERITY_MAP.get("CRITICAL", 1.0),
    Severity.HIGH: _YAML_SEVERITY_MAP.get("HIGH", 0.75),
    Severity.MEDIUM: _YAML_SEVERITY_MAP.get("MEDIUM", 0.5),
    Severity.LOW: _YAML_SEVERITY_MAP.get("LOW", 0.25),
    Severity.INFO: _YAML_SEVERITY_MAP.get("INFO", 0.0),
}

# Maximum possible static severity (sum of all rules' actual severities
# from config/rules.yaml).  Per PROPOSAL §10.1 this is "max possible
# severity if all rules triggered" — which uses each rule's real
# severity, not CRITICAL for every rule.
_RULE_SEVERITIES: list[str] = [
    r.get("severity", "INFO")
    for r in SETTINGS.get("rules", {})  # may be empty at import time
]
if not _RULE_SEVERITIES:
    # Fallback: hardcode the actual rules.yaml severities.
    # HIGH×4 + CRITICAL×1 + MEDIUM×4 + LOW×1 + INFO×1
    _RULE_SEVERITIES = [
        "HIGH", "MEDIUM", "HIGH", "CRITICAL", "MEDIUM",  # 001–005
        "HIGH", "MEDIUM", "HIGH", "LOW", "MEDIUM", "INFO",  # 006–011
    ]
MAX_POSSIBLE_SEVERITY: float = sum(
    SEVERITY_MAP.get(Severity(s), 0.0) for s in _RULE_SEVERITIES
)

# Risk level thresholds (PROPOSAL §10.2).
SHORT_CIRCUIT_SCORE: int = SETTINGS.get(
    "scoring", {}).get("short_circuit_score", 5)
THRESHOLDS = SETTINGS.get("scoring", {}).get("thresholds", {
    "low": 20, "medium": 40, "high": 70
})

_CONTEXT_MODIFIERS = SETTINGS.get("scoring", {}).get("context_modifiers", {})


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------
@dataclass(frozen=True)
class RiskResult:
    """Result of risk scoring for a single exchange/flow.

    Attributes:
        score: Final risk score 0–100.
        level: Classified risk level.
        base_score: Raw base score before modifiers.
        modifiers_applied: List of modifier descriptions applied.
    """

    score: int
    level: RiskLevel
    base_score: float
    modifiers_applied: List[str] = field(default_factory=list)


# ------------------------------------------------------------------
# T-404: Risk Level Classification (FR-402)
# ------------------------------------------------------------------


def classify_risk(score: int) -> RiskLevel:
    """Classify a 0–100 score into a risk level.

    Per PROPOSAL §10.2:
        0–20   → LOW
        21–40  → MEDIUM
        41–70  → HIGH
        71–100 → CRITICAL

    Args:
        score: Integer risk score (0–100).

    Returns:
        RiskLevel enum value.
    """
    if score <= THRESHOLDS.get("low", 20):
        return RiskLevel.LOW
    elif score <= THRESHOLDS.get("medium", 40):
        return RiskLevel.MEDIUM
    elif score <= THRESHOLDS.get("high", 70):
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


# ------------------------------------------------------------------
# T-402: Static Score Normalization
# ------------------------------------------------------------------


def normalize_static_score(findings: List[Finding]) -> float:
    """Normalize static analysis findings to a 0.0–1.0 score.

    Maps each finding's severity to a numeric value, sums them,
    and divides by the maximum possible severity.

    Args:
        findings: List of static analysis findings.

    Returns:
        Normalized score in [0.0, 1.0].
    """
    if not findings:
        return 0.0

    total = sum(
        SEVERITY_MAP.get(f.severity, 0.0) for f in findings
    )

    normalized = total / MAX_POSSIBLE_SEVERITY
    return min(normalized, 1.0)  # Clamp to 1.0


# ------------------------------------------------------------------
# T-403: Context Modifiers (FR-403)
# ------------------------------------------------------------------


# Financial endpoint patterns.
_FINANCIAL_PATTERNS = [
    "/transfer", "/payment", "/checkout", "/billing",
    "/invoice", "/refund", "/withdraw", "/deposit",
]

# Admin endpoint patterns.
_ADMIN_PATTERNS = [
    "/admin", "/manage", "/dashboard/admin", "/staff",
]

# User data modification patterns.
_USER_DATA_PATTERNS = [
    "/profile", "/settings", "/account", "/password",
    "/update", "/edit", "/preferences", "/email",
]

# Protection-absence rule IDs (same as heuristics.py).
_PROTECTION_RULES = {
    "CSRF-001", "CSRF-002", "CSRF-005", "CSRF-007", "CSRF-009",
}


def detect_context_modifiers(
    url: str,
    http_method: str,
    findings: List[Finding],
) -> List[tuple[str, int]]:
    """Detect which context modifiers apply.

    Per PROPOSAL §10.3, returns a list of (description, points)
    tuples for each applicable modifier.

    Args:
        url: The request URL.
        http_method: HTTP method (GET, POST, etc.).
        findings: Static analysis findings.

    Returns:
        List of (description, modifier_points) tuples.
    """
    modifiers: List[tuple[str, int]] = []
    path = urlparse(url).path.lower()
    finding_ids = {f.rule_id for f in findings}

    # +15: Financial data endpoint.
    if any(p in path for p in _FINANCIAL_PATTERNS):
        modifiers.append(("Financial data endpoint",
                         _CONTEXT_MODIFIERS.get("financial_data", 15)))

    # +10: Modifies user data.
    if any(p in path for p in _USER_DATA_PATTERNS):
        modifiers.append(
            ("Modifies user data", _CONTEXT_MODIFIERS.get("user_data_modify", 10)))  # noqa: E501

    # +10: Admin-only endpoint.
    if any(p in path for p in _ADMIN_PATTERNS):
        modifiers.append(
            ("Admin-only endpoint", _CONTEXT_MODIFIERS.get("admin_only", 10)))

    # -5: Uses HTTPS.
    parsed = urlparse(url)
    if parsed.scheme == "https":
        modifiers.append(
            ("Uses HTTPS", _CONTEXT_MODIFIERS.get("uses_https", -5)))

    # -15: Multiple CSRF protections present.
    protection_count = sum(
        1 for r in _PROTECTION_RULES
        if r not in finding_ids
    )
    if protection_count >= 2:
        modifiers.append(("Multiple CSRF protections",
                         _CONTEXT_MODIFIERS.get("multiple_protections", -15)))

    # +20: GET-based state change.
    if http_method.upper() == "GET":
        # Check for action-like query params or side-effect paths.
        query = urlparse(url).query.lower()
        action_params = {"action", "op", "do", "cmd"}
        if any(p in query for p in action_params):
            modifiers.append(
                ("GET-based state change", _CONTEXT_MODIFIERS.get("get_state_change", 20)))  # noqa: E501

    return modifiers


# ------------------------------------------------------------------
# T-401: Risk Scorer (FR-401)
# ------------------------------------------------------------------


class RiskScorer:
    """Calculate risk scores using Base Score + Modifier model.

    Usage::

        scorer = RiskScorer()
        result = scorer.calculate_risk(
            ml_probability=0.85,
            findings=static_findings,
            url="https://bank.com/transfer",
            http_method="POST",
        )
        print(result.score, result.level)

    Ref: PROPOSAL §10.1, FR-401
    """

    def calculate_risk(
        self,
        ml_probability: float,
        findings: List[Finding],
        url: str = "",
        http_method: str = "GET",
        is_short_circuited: bool = False,
    ) -> RiskResult:
        """Calculate the final risk score.

        Args:
            ml_probability: ML vulnerability probability [0, 1].
            findings: Static analysis findings.
            url: Request URL for context modifier detection.
            http_method: HTTP method.
            is_short_circuited: True if session was short-circuited
                (header-only auth, FR-404).

        Returns:
            RiskResult with score, level, and applied modifiers.
        """
        # FR-404: Short-circuited sessions get fixed score 5 (LOW).
        if is_short_circuited:
            return RiskResult(
                score=SHORT_CIRCUIT_SCORE,
                level=RiskLevel.LOW,
                base_score=float(SHORT_CIRCUIT_SCORE),
                modifiers_applied=["Short-circuited (header-only auth)"],
            )

        # Step 1: Calculate Base Score.
        static_normalized = normalize_static_score(findings)
        base_score = (
            W_ML * ml_probability
            + W_STATIC * static_normalized
        ) * 100

        # Step 2: Detect and apply context modifiers.
        modifiers = detect_context_modifiers(
            url, http_method, findings
        )
        modifier_sum = sum(pts for _, pts in modifiers)
        modifier_descriptions = [
            f"{desc} ({pts:+d})" for desc, pts in modifiers
        ]

        # Final score, clamped to [0, 100].
        final = int(round(_clamp(base_score + modifier_sum, 0, 100)))

        # Classify risk level.
        level = classify_risk(final)

        logger.info(
            "Risk: base=%.1f modifiers=%+d final=%d (%s)",
            base_score,
            modifier_sum,
            final,
            level.value,
        )

        return RiskResult(
            score=final,
            level=level,
            base_score=round(base_score, 2),
            modifiers_applied=modifier_descriptions,
        )


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to [low, high]."""
    return max(low, min(high, value))
