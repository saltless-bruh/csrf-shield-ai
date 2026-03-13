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

## How to download

### Prerequisites

- **Python:** 3.10+
- **Go:** 1.21+ (for building the TUI)

### Setup

```bash
# Clone the repository
git clone https://github.com/saltless-bruh/csrf-shield-ai.git
cd csrf-shield-ai

# Install Python backend dependencies
pip install -e .

# Build interactive TUI
cd cmd/tui
go build -o ../../csrf-shield-tui main.go
cd ../..
```

## How to use

```bash
# Launch interactive TUI (Flagship Interface)
./csrf-shield-tui --input traffic.har

# Analyze a HAR file non-interactively (CI/CD)
csrf-shield analyze --input traffic.har --output report.json --format json

# Train ML model
csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl
```

For more detailed usage instructions, please refer to the [User Guide](docs/guides/USER_GUIDE.md).

## Project Structure

See [`docs/proposal/PROPOSAL.md`](docs/proposal/PROPOSAL.md) §11.1 for the Python backend structure and [`docs/proposal/CLI_TUI_PROPOSAL.md`](docs/proposal/CLI_TUI_PROPOSAL.md) §11 for the Go TUI structure.

## Technology Stack

The tool uses a **two-process architecture** communicating via NDJSON over stdin/stdout:

| Component     | Technology             | Role                                        |
| ------------- | ---------------------- | ------------------------------------------- |
| **Backend**   | Python 3.10+           | Heavy lifting: ML, static analysis, parsing |
| **Frontend**  | Go 1.21+ / gocui       | Fast, responsive, single-binary Terminal UI |
| **ML Models** | scikit-learn, XGBoost  | Classical ML for tabular HTTP data          |
| **Testing**   | pytest (Py), `go test` | Cross-language unit/integration testing     |

## Documentation

### Guides

- [User Guide](docs/guides/USER_GUIDE.md)
- [API Reference](docs/guides/API_REFERENCE.md)

### Specifications

- [Project Proposal](docs/proposal/PROPOSAL.md)
- [TUI Extension Spec](docs/proposal/CLI_TUI_PROPOSAL.md)
- [Defense Notes](docs/defense/DEFENSE_NOTES.md)
- [Design Document](spec/Design.md)
- [Requirements](spec/Requirements.md)
- [Task Breakdown](spec/Tasks.md)

## License

Academic project — FPT University, IAW Course, Group 9.

---

> **Status:** Phase 6 — Testing, Polish & Documentation
