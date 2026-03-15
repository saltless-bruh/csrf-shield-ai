# CSRF Shield AI

AI-powered CSRF risk analysis for HAR traffic captures.

CSRF Shield AI combines deterministic static checks with machine-learning scoring to produce actionable, per-session risk results and exportable security reports.

## Highlights

- HAR ingestion and session-flow reconstruction.
- 11 static CSRF/security checks (token, origin/referer, cookie and auth signals).
- ML-assisted risk scoring (`0-100`) with severity classification.
- Interactive Go TUI for investigation and triage.
- JSON/HTML report export for CI and audit workflows.

## Architecture

The project uses a two-process model over NDJSON (`stdin/stdout`):

- Python backend: parsing, static analysis, ML inference, risk scoring, report generation.
- Go TUI frontend: terminal UI, navigation, orchestration, IPC client.

## Prerequisites

- Python `3.10+`
- Go `1.21+`

## Quick Start

```bash
# 1) Clone
git clone https://github.com/saltless-bruh/csrf-shield-ai.git
cd csrf-shield-ai

# 2) Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3) Build TUI binary
go build -o bin/csrf-shield-tui ./cmd/tui
```

## Usage

### Interactive TUI (recommended)

```bash
bin/csrf-shield-tui --input path/to/traffic.har
```

### CLI analysis (non-interactive)

```bash
csrf-shield analyze --input path/to/traffic.har --output report.json --format json
```

### Train model

```bash
csrf-shield train --data data/training --output src/ml/models/csrf_rf_model.pkl
```

## Developer Commands

```bash
# Python tests
python -m pytest -q

# Go tests
go test ./...
```

## Project Layout

- `src/` Python backend
- `cmd/tui/` Go TUI entrypoint
- `internal/` Go TUI internals (IPC, UI, models)
- `tests/` Python test suite
- `docs/` guides, specs, reports, reviews
- `data/` sample and training datasets

## Documentation

- [User Guide](docs/guides/USER_GUIDE.md)
- [API Reference](docs/guides/API_REFERENCE.md)
- [Project Proposal](docs/proposal/PROPOSAL.md)
- [CLI/TUI Proposal](docs/proposal/CLI_TUI_PROPOSAL.md)

## License

Academic project for FPT University (IAW course, Group 9).
