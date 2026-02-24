"""Unit tests for CLI entry point.

Tests Click CLI commands using CliRunner for isolated testing.

Ref:
    - spec/Tasks.md T-161, T-162, T-163
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.main import main

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_har"


# ---------------------------------------------------------------------------
# CLI Group (T-161)
# ---------------------------------------------------------------------------


class TestCliGroup:
    """Tests for the main CLI group."""

    def test_version(self) -> None:
        """--version prints version string."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self) -> None:
        """--help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "CSRF Shield AI" in result.output

    def test_no_command_shows_help(self) -> None:
        """Running with no subcommand shows help."""
        runner = CliRunner()
        result = runner.invoke(main)
        assert result.exit_code == 0
        assert "Usage" in result.output


# ---------------------------------------------------------------------------
# Analyze Subcommand (T-162)
# ---------------------------------------------------------------------------


class TestAnalyzeCommand:
    """Tests for the analyze subcommand."""

    def test_analyze_help(self) -> None:
        """analyze --help shows subcommand usage."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--format" in result.output

    def test_analyze_minimal_har(self, tmp_path: Path) -> None:
        """analyze processes a valid HAR file."""
        output = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(main, [
            "analyze",
            "--input", str(SAMPLE_DIR / "minimal.har"),
            "--output", str(output),
        ])
        assert result.exit_code == 0
        assert "Parsing HAR file" in result.output
        assert "Reconstructing session flows" in result.output
        assert "Analysis complete" in result.output
        assert output.exists()

    def test_analyze_bearer_short_circuits(self, tmp_path: Path) -> None:
        """analyze short-circuits bearer auth flows."""
        output = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(main, [
            "analyze",
            "--input", str(SAMPLE_DIR / "bearer_auth.har"),
            "--output", str(output),
        ])
        assert result.exit_code == 0
        assert "Short-circuited" in result.output

    def test_analyze_missing_file(self) -> None:
        """analyze exits with error for missing file."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "analyze",
            "--input", "/nonexistent/file.har",
        ])
        # Click's exists=True validation catches this
        assert result.exit_code != 0

    def test_analyze_json_output(self, tmp_path: Path) -> None:
        """analyze produces valid JSON output."""
        import json

        output = tmp_path / "report.json"
        runner = CliRunner()
        runner.invoke(main, [
            "analyze",
            "--input", str(SAMPLE_DIR / "minimal.har"),
            "--output", str(output),
        ])
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert "flows" in data
        assert "total_flows" in data

    def test_analyze_requires_input(self) -> None:
        """analyze fails without --input."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()


# ---------------------------------------------------------------------------
# Train Subcommand (T-163)
# ---------------------------------------------------------------------------


class TestTrainCommand:
    """Tests for the train subcommand."""

    def test_train_help(self) -> None:
        """train --help shows subcommand usage."""
        runner = CliRunner()
        result = runner.invoke(main, ["train", "--help"])
        assert result.exit_code == 0
        assert "--data" in result.output

    def test_train_skeleton_message(self, tmp_path: Path) -> None:
        """train prints skeleton message."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "train",
            "--data", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()


# ---------------------------------------------------------------------------
# Verbosity
# ---------------------------------------------------------------------------


class TestVerbosity:
    """Tests for verbosity flag."""

    def test_quiet_mode(self, tmp_path: Path) -> None:
        """--verbosity quiet still runs analyze."""
        output = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(main, [
            "--verbosity", "quiet",
            "analyze",
            "--input", str(SAMPLE_DIR / "minimal.har"),
            "--output", str(output),
        ])
        assert result.exit_code == 0

    def test_verbose_mode(self, tmp_path: Path) -> None:
        """--verbosity verbose still runs analyze."""
        output = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(main, [
            "--verbosity", "verbose",
            "analyze",
            "--input", str(SAMPLE_DIR / "minimal.har"),
            "--output", str(output),
        ])
        assert result.exit_code == 0
