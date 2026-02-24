"""CSRF Shield AI — CLI Entry Point.

Provides the main command-line interface for the tool.

Usage:
    csrf-shield analyze --input traffic.har --output report.json --format json
    csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl

Ref: spec/Design.md §6.1 (CLI Interface)
"""

from __future__ import annotations

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="csrf-shield")
def main() -> None:
    """🛡️ CSRF Shield AI — AI-Powered CSRF Risk Scoring Tool.

    Analyze HTTP traffic captures for Cross-Site Request Forgery vulnerabilities
    using static rules and machine learning classification.
    """


@main.command()
@click.option("--input", "-i", "input_file", required=True, help="Path to HAR file to analyze.")
@click.option(
    "--output", "-o", "output_file", default="report.json", help="Output report path."
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "html"], case_sensitive=False),
    default="json",
    help="Report format.",
)
def analyze(input_file: str, output_file: str, output_format: str) -> None:
    """Analyze a HAR file for CSRF vulnerabilities.

    Runs the full pipeline: parse → static analysis → ML → risk scoring → report.
    """
    click.echo(f"🔍 Analyzing: {input_file}")
    click.echo(f"📄 Output format: {output_format}")
    click.echo(f"💾 Output file: {output_file}")
    # TODO: Wire up pipeline once Phase 1 modules are complete
    click.echo("⚠️  Pipeline not yet implemented — skeleton only (Phase 1)")


@main.command()
@click.option(
    "--data", "-d", "data_dir", required=True, help="Path to training data directory."
)
@click.option(
    "--output",
    "-o",
    "model_output",
    default="src/ml/models/csrf_rf_model.pkl",
    help="Path to save trained model.",
)
def train(data_dir: str, model_output: str) -> None:
    """Train the ML classifier on labeled data.

    Trains a Random Forest model using feature vectors from the data directory.
    """
    click.echo(f"🧠 Training data: {data_dir}")
    click.echo(f"💾 Model output: {model_output}")
    # TODO: Wire up trainer once Phase 3 is complete
    click.echo("⚠️  Trainer not yet implemented — skeleton only (Phase 1)")


if __name__ == "__main__":
    main()
