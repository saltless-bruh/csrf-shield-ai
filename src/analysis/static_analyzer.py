"""Static analysis orchestrator for CSRF Shield AI.

Loads enabled rules from ``config/rules.yaml``, runs them against
every exchange in a ``SessionFlow``, and extracts ML feature vectors.

Implements the Phase 2 analysis flow described in PROPOSAL.md §8.3:
  0. Short-circuit check (header-only auth → CSRF-011)
  1. For each exchange: run all enabled rules → collect findings
  2. For each exchange: extract feature vector
  3. Return aggregated output

Ref:
    - docs/proposal/PROPOSAL.md §8.3
    - spec/Tasks.md T-241, T-242, T-243
    - config/rules.yaml
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import yaml

from src.analysis.feature_extractor import extract_features
from src.analysis.rules.base_rule import BaseRule
from src.input.models import (
    AuthMechanism,
    Finding,
    SessionFlow,
    Severity,
)

logger = logging.getLogger(__name__)

# Default path to rules configuration.
_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "rules.yaml"
)


# ------------------------------------------------------------------
# Output data structure
# ------------------------------------------------------------------


@dataclass(frozen=True)
class StaticAnalysisOutput:
    """Aggregated output from static analysis of a SessionFlow.

    Attributes:
        findings: All findings from all rules across all exchanges.
        feature_vectors: Map of exchange URL → extracted features.
        short_circuited: True if analysis was short-circuited
            due to header-only auth (CSRF-011).
    """

    findings: List[Finding]
    feature_vectors: Dict[str, Dict[str, Any]]
    short_circuited: bool = False


# ------------------------------------------------------------------
# T-242: Rule Loading
# ------------------------------------------------------------------


def load_rules(
    config_path: Optional[str] = None,
) -> List[BaseRule]:
    """Load enabled rules from rules.yaml configuration.

    Reads the YAML config, filters to ``enabled: true`` only,
    and dynamically imports each rule module to instantiate its
    class.

    Module → class naming convention:
        ``csrf_001`` → ``Csrf001``
        ``csrf_010`` → ``Csrf010``

    Args:
        config_path: Path to rules.yaml.  Defaults to
            ``config/rules.yaml`` relative to project root.

    Returns:
        List of instantiated :class:`BaseRule` subclasses.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ImportError: If a rule module cannot be imported.

    Ref: T-242, config/rules.yaml
    """
    path = Path(config_path) if config_path else _DEFAULT_RULES_PATH

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    rules: List[BaseRule] = []
    for rule_def in config.get("rules", []):
        if not rule_def.get("enabled", True):
            logger.debug(
                "Skipping disabled rule: %s", rule_def["id"]
            )
            continue

        module_name = rule_def["module"]
        class_name = _module_to_class_name(module_name)

        try:
            module = importlib.import_module(
                f"src.analysis.rules.{module_name}"
            )
            rule_class: Type[BaseRule] = getattr(
                module, class_name
            )
            rules.append(rule_class())
            logger.debug(
                "Loaded rule: %s (%s)",
                rule_def["id"],
                class_name,
            )
        except (ImportError, AttributeError) as exc:
            logger.warning(
                "Failed to load rule %s from module %s: %s",
                rule_def["id"],
                module_name,
                exc,
            )

    logger.info("Loaded %d rules from %s", len(rules), path)
    return rules


def _module_to_class_name(module_name: str) -> str:
    """Convert a module name to its expected class name.

    ``csrf_001`` → ``Csrf001``
    ``csrf_010`` → ``Csrf010``
    ``csrf_011`` → ``Csrf011``
    """
    parts = module_name.split("_")
    return "".join(p.capitalize() for p in parts)


# ------------------------------------------------------------------
# T-241: Static Analyzer
# ------------------------------------------------------------------


class StaticAnalyzer:
    """Orchestrates static analysis rules and feature extraction.

    Usage::

        analyzer = StaticAnalyzer()
        output = analyzer.analyze_flow(session_flow)
        for finding in output.findings:
            print(finding.rule_id, finding.description)

    Ref: PROPOSAL.md §8.3, T-241
    """

    def __init__(
        self,
        rules_config_path: Optional[str] = None,
    ) -> None:
        """Initialize with rules loaded from configuration.

        Args:
            rules_config_path: Optional path to rules.yaml.
        """
        self.rules = load_rules(rules_config_path)

    def analyze_flow(
        self, flow: SessionFlow
    ) -> StaticAnalysisOutput:
        """Run all rules against every exchange in the flow.

        Per PROPOSAL.md §8.3:
          0. Short-circuit if header-only auth
          1. Run rules per exchange
          2. Extract features per exchange
          3. Return aggregated output

        Args:
            flow: The session flow to analyze.

        Returns:
            :class:`StaticAnalysisOutput` with findings and
            feature vectors.
        """
        # Step 0: Short-circuit for header-only auth
        if flow.auth_mechanism == AuthMechanism.HEADER_ONLY:
            return self._short_circuit(flow)

        all_findings: List[Finding] = []
        feature_vectors: Dict[str, Dict[str, Any]] = {}

        for exchange in flow.exchanges:
            # Step 1: Run all rules
            for rule in self.rules:
                try:
                    findings = rule.analyze(exchange, flow)
                    all_findings.extend(findings)
                except Exception as exc:
                    logger.error(
                        "Rule %s failed on %s: %s",
                        rule.rule_id,
                        exchange.request_url,
                        exc,
                    )

            # Step 2: Extract feature vector (state-changing only).
            # GET/HEAD/OPTIONS requests are not CSRF targets; extracting
            # features for them would produce spurious ML predictions.
            if not BaseRule.is_state_changing(exchange.request_method):
                continue
            try:
                features = extract_features(exchange, flow)
                key = (
                    f"{exchange.request_method} "
                    f"{exchange.request_url}"
                )
                feature_vectors[key] = features
            except Exception as exc:
                logger.error(
                    "Feature extraction failed for %s: %s",
                    exchange.request_url,
                    exc,
                )

        logger.info(
            "Analyzed flow %s: %d exchanges, %d findings",
            flow.session_id,
            len(flow.exchanges),
            len(all_findings),
        )

        return StaticAnalysisOutput(
            findings=all_findings,
            feature_vectors=feature_vectors,
        )

    def _short_circuit(
        self, flow: SessionFlow
    ) -> StaticAnalysisOutput:
        """Handle header-only auth short-circuit (CSRF-011).

        Returns an INFO-level CSRF-011 finding for the first
        exchange and empty feature vectors.

        Ref: PROPOSAL.md §8.3 step 0, §8.4
        """
        findings: List[Finding] = []
        if flow.exchanges:
            exchange = flow.exchanges[0]
            findings.append(
                Finding(
                    rule_id="CSRF-011",
                    rule_name="Non-Cookie Auth (CSRF N/A)",
                    severity=Severity.INFO,
                    description=(
                        "Session uses header-based authentication "
                        "exclusively. CSRF risk is inherently low "
                        "because the browser does not auto-attach "
                        "these headers to cross-origin requests."
                    ),
                    evidence=(
                        f"Auth mechanism: {flow.auth_mechanism.value}"
                    ),
                    exchange=exchange,
                )
            )

        logger.info(
            "Short-circuited flow %s (header-only auth)",
            flow.session_id,
        )

        return StaticAnalysisOutput(
            findings=findings,
            feature_vectors={},
            short_circuited=True,
        )
