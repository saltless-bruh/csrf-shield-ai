"""CSRF Shield AI — CLI Entry Point.

Provides the main command-line interface for the tool.

Usage:
    csrf-shield analyze --input traffic.har --output report.json --format json
    csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl

Ref:
    - spec/Design.md §6.1 (CLI Interface)
    - spec/Tasks.md T-161, T-162, T-163
    - spec/Requirements.md FR-504
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from src.input.auth_detector import (
    build_short_circuit_result,
    detect_auth_mechanism,
    update_flow_auth,
)
from src.input.flow_reconstructor import reconstruct_flows
from src.input.har_parser import HarParseError, parse_har_file
from src.input.models import AuthMechanism

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logger = logging.getLogger("csrf_shield")


def _configure_logging(verbosity: str) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbosity: One of 'quiet', 'normal', 'verbose'.
    """
    level_map = {
        "quiet": logging.WARNING,
        "normal": logging.INFO,
        "verbose": logging.DEBUG,
    }
    level = level_map.get(verbosity, logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT)


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="csrf-shield")
@click.option(
    "--verbosity",
    "-v",
    type=click.Choice(["quiet", "normal", "verbose"], case_sensitive=False),
    default="normal",
    help="Logging verbosity level.",
)
@click.pass_context
def main(ctx: click.Context, verbosity: str) -> None:
    """🛡️ CSRF Shield AI — AI-Powered CSRF Risk Scoring Tool.

    Analyze HTTP traffic captures for Cross-Site Request Forgery vulnerabilities
    using static rules and machine learning classification.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbosity"] = verbosity
    _configure_logging(verbosity)
    
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Analyze Subcommand (T-162)
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--input", "-i", "input_file", required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to HAR file to analyze.",
)
@click.option(
    "--output", "-o", "output_file", default="report.json",
    help="Output report path.",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "html"], case_sensitive=False),
    default="json",
    help="Report format.",
)
@click.pass_context
def analyze(ctx: click.Context, input_file: str, output_file: str, output_format: str) -> None:
    """Analyze a HAR file for CSRF vulnerabilities.

    Runs the Phase 1 pipeline: parse → reconstruct flows → detect auth.
    Static analysis and ML scoring added in Phases 2–3.
    """
    click.echo(f"🔍 Analyzing: {input_file}")

    # --- Phase 1 Pipeline ---

    # Step 1: Parse HAR file → List[HttpExchange]
    try:
        click.echo("📥 Parsing HAR file...")
        exchanges = parse_har_file(Path(input_file))
        click.echo(f"  ✓ Parsed {len(exchanges)} exchange(s)")
    except HarParseError as e:
        click.echo(f"❌ HAR parse error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"❌ File not found: {input_file}", err=True)
        sys.exit(1)

    if not exchanges:
        click.echo("⚠️  No exchanges found in HAR file.")
        sys.exit(0)

    # Step 2: Reconstruct session flows → List[SessionFlow]
    click.echo("🔗 Reconstructing session flows...")
    flows = reconstruct_flows(exchanges)
    click.echo(f"  ✓ Reconstructed {len(flows)} session flow(s)")

    # Step 3: Detect auth mechanisms
    click.echo("🔐 Detecting auth mechanisms...")
    updated_flows = [update_flow_auth(flow) for flow in flows]

    results = []
    for flow in updated_flows:
        mechanism = flow.auth_mechanism
        click.echo(
            f"  Session '{flow.session_id[:20]}...' → "
            f"{mechanism.value} ({len(flow.exchanges)} requests)"
        )

        if mechanism == AuthMechanism.HEADER_ONLY:
            # Short-circuit: CSRF not applicable
            result = build_short_circuit_result(flow)
            results.append({
                "session_id": flow.session_id,
                "short_circuited": True,
                "risk_score": result.risk_score,
                "risk_level": result.risk_level.value,
                "finding": result.findings[0].rule_id if result.findings else None,
            })
            click.echo(f"    ⚡ Short-circuited → score={result.risk_score} (CSRF N/A)")
        else:
            # TODO: Phase 2 static analysis + Phase 3 ML scoring
            results.append({
                "session_id": flow.session_id,
                "short_circuited": False,
                "auth_mechanism": mechanism.value,
                "exchanges": len(flow.exchanges),
                "status": "awaiting_phase2",
            })
            click.echo(f"    ⏳ Queued for analysis (Phase 2 not yet implemented)")

    # Step 4: Output results
    click.echo(f"\n📄 Output format: {output_format}")

    if output_format == "json":
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"flows": results, "total_flows": len(results)}, f, indent=2)
        click.echo(f"💾 Report saved to: {output_file}")
    else:
        # TODO: HTML report generation (Phase 4)
        click.echo(f"⚠️  HTML format not yet implemented — use JSON.")

    click.echo("✅ Analysis complete.")


# ---------------------------------------------------------------------------
# Train Subcommand (T-163)
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--data", "-d", "data_dir", required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to training data directory.",
)
@click.option(
    "--output", "-o", "model_output",
    default="src/ml/models/csrf_rf_model.pkl",
    help="Path to save trained model.",
)
@click.pass_context
def train(ctx: click.Context, data_dir: str, model_output: str) -> None:
    """Train the ML classifier on labeled data.

    Trains a Random Forest model using feature vectors from the data directory.
    """
    click.echo(f"🧠 Training data: {data_dir}")
    click.echo(f"💾 Model output: {model_output}")
    # TODO: Wire up trainer once Phase 3 is complete
    click.echo("⚠️  Trainer not yet implemented — skeleton only (Phase 1)")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
