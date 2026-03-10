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

# Add project root to sys.path so 'src.X' imports work when run directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import click  # noqa: E402

from src.input.auth_detector import (  # noqa: E402
    build_short_circuit_result,
    update_flow_auth,
)
from src.input.flow_reconstructor import reconstruct_flows  # noqa: E402
from src.input.har_parser import HarParseError, parse_har_file  # noqa: E402
from src.input.models import AuthMechanism  # noqa: E402
from src.pipeline import CsrfPipeline  # noqa: E402
from src.ml.trainer import CsrfTrainer  # noqa: E402

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

    Runs the full Phase 1-4 pipeline: parse → static analysis → ML inference → scoring → reporting.
    """
    click.echo(f"🔍 Analyzing: {input_file}")

    # Check if file exists first
    input_path = Path(input_file)
    if not input_path.exists():
        click.echo(f"❌ File not found: {input_file}", err=True)
        sys.exit(1)

    try:
        pipeline = CsrfPipeline()
        output_dir = Path(output_file).parent if output_file else None
        
        # In a real environment we would conditionally suppress logs here based on verbosity,
        # but CsrfPipeline handles the heavy lifting
        result = pipeline.analyze_har(input_path, output_dir=output_dir)

        # Output logic
        click.echo(f"\n✅ Analysis complete. Flow results: {len(result.flow_results)}")
        click.echo(f"📄 Output format: {output_format}")
        if output_format == 'json' and result.json_report_path:
             click.echo(f"💾 Report saved to: {result.json_report_path}")
             # If user specified a specific file, rename it
             if output_file and str(result.json_report_path) != output_file:
                 import shutil
                 shutil.move(str(result.json_report_path), output_file)
                 click.echo(f"💾 Report moved to: {output_file}")
        elif output_format == 'html' and result.html_report_path:
             click.echo(f"💾 Report saved to: {result.html_report_path}")
             if output_file and str(result.html_report_path) != output_file:
                 import shutil
                 shutil.move(str(result.html_report_path), output_file)
                 click.echo(f"💾 Report moved to: {output_file}")
        elif not output_file:
             click.echo("⚠️  No output file specified, no report generated")

    except Exception as e:
        click.echo(f"❌ Pipeline error: {e}", err=True)
        sys.exit(1)


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
    
    try:
        trainer = CsrfTrainer(
            train_path=Path(data_dir) / "train.csv",
            val_path=Path(data_dir) / "val.csv",
            test_path=Path(data_dir) / "test.csv",
            model_dir=Path(model_output).parent
        )
        result = trainer.run()
        click.echo(f"✅ Training complete. Best model: {result.best_model_name}")
    except Exception as e:
        click.echo(f"❌ Training error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
