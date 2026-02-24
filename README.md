# 🛡️ CSRF Shield AI

> **AI-Powered CSRF Risk Scoring Tool**

An automated security analysis tool that detects Cross-Site Request Forgery (CSRF) vulnerabilities by analyzing HTTP traffic captures. Combines static rule-based analysis with machine learning classification to produce quantified risk scores (0–100).

---

## Features

- 📂 **HAR File Analysis** — Parse browser-exported traffic captures
- 🔍 **11 CSRF Detection Rules** — Comprehensive static analysis (tokens, cookies, headers, CORS)
- 🤖 **ML Classification** — Random Forest / XGBoost vulnerability prediction
- 📊 **Risk Scoring** — Quantified 0–100 scores with severity levels
- 💻 **Interactive TUI** — Go-based terminal interface with Vim-style navigation and real-time analysis
- 📝 **Reports** — JSON & HTML reports with remediation recommendations

## Quick Start

```bash
# Install Python backend
pip install -e .

# Launch interactive TUI (Flagship Interface)
csrf-shield tui --input traffic.har

# Analyze a HAR file non-interactively (CI/CD)
csrf-shield analyze --input traffic.har --output report.json --format json

# Train ML model
csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl
```

## Project Structure

See [`docs/proposal/PROPOSAL.md`](docs/proposal/PROPOSAL.md) §11.1 for the Python backend structure and [`docs/proposal/CLI_TUI_PROPOSAL.md`](docs/proposal/CLI_TUI_PROPOSAL.md) §11 for the Go TUI structure.

## Technology Stack

The tool uses a **two-process architecture** communicating via NDJSON over stdin/stdout:

| Component | Technology | Role |
| --- | --- | --- |
| **Backend** | Python 3.10+ | Heavy lifting: ML, static analysis, parsing |
| **Frontend** | Go 1.21+ / gocui | Fast, responsive, single-binary Terminal UI |
| **ML Models** | scikit-learn, XGBoost | Classical ML for tabular HTTP data |
| **Testing** | pytest (Py), `go test` | Cross-language unit/integration testing |

## Documentation

- [Project Proposal](docs/proposal/PROPOSAL.md)
- [TUI Extension Spec](docs/proposal/CLI_TUI_PROPOSAL.md)
- [Defense Notes](docs/defense/DEFENSE_NOTES.md)
- [Design Document](spec/Design.md)
- [Requirements](spec/Requirements.md)
- [Task Breakdown](spec/Tasks.md)

## License

Academic project — FPT University, IAW Course, Group 9.

---

> **Status:** Phase 2 — Static Analysis (Pre-coding Setup Complete)
