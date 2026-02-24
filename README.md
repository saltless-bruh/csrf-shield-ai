# 🛡️ CSRF Shield AI

> **AI-Powered CSRF Risk Scoring Tool**

An automated security analysis tool that detects Cross-Site Request Forgery (CSRF) vulnerabilities by analyzing HTTP traffic captures. Combines static rule-based analysis with machine learning classification to produce quantified risk scores (0–100).

---

## Features

- 📂 **HAR File Analysis** — Parse browser-exported traffic captures
- 🔍 **11 CSRF Detection Rules** — Comprehensive static analysis (tokens, cookies, headers, CORS)
- 🤖 **ML Classification** — Random Forest / XGBoost vulnerability prediction
- 📊 **Risk Scoring** — Quantified 0–100 scores with severity levels
- 📝 **Reports** — JSON & HTML reports with remediation recommendations
- 🌐 **Web Dashboard** — Browser-based interactive results viewer

## Quick Start

```bash
# Install
pip install -e .

# Analyze a HAR file
csrf-shield analyze --input traffic.har --output report.json --format json

# Train ML model
csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl
```

## Project Structure

See [`docs/proposal/PROPOSAL.md`](docs/proposal/PROPOSAL.md) §11.1 for the full module structure.

## Technology Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.10+ |
| ML | scikit-learn, XGBoost |
| Web | Flask 3.0+ |
| Testing | pytest |

## Documentation

- [Project Proposal](docs/proposal/PROPOSAL.md)
- [Defense Notes](docs/defense/DEFENSE_NOTES.md)
- [Design Document](spec/Design.md)
- [Requirements](spec/Requirements.md)
- [Task Breakdown](spec/Tasks.md)

## License

Academic project — FPT University, IAW Course, Group 9.

---

> **Status:** Phase 1 — Foundation (In Progress)
