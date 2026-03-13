# Final Project Report — CSRF Shield AI

> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Course:** IAW (Web Application Security / Bảo mật ứng dụng Web)
> **Institution:** FPT University — Group 9
> **Date:** March 3, 2026
> **Version:** 1.0

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Related Work](#3-related-work)
4. [System Architecture](#4-system-architecture)
5. [Technical Design](#5-technical-design)
6. [AI/ML Component](#6-aiml-component)
7. [Risk Scoring Model](#7-risk-scoring-model)
8. [Interactive TUI & IPC](#8-interactive-tui--ipc)
9. [Implementation Summary](#9-implementation-summary)
10. [Testing & Quality Assurance](#10-testing--quality-assurance)
11. [Results & Evaluation](#11-results--evaluation)
12. [Discussion](#12-discussion)
13. [Future Work](#13-future-work)
14. [Conclusion](#14-conclusion)
15. [References](#15-references)

---

## 1. Abstract

CSRF Shield AI is an automated security analysis tool that detects Cross-Site Request Forgery (CSRF) vulnerabilities by analyzing HTTP traffic captures. The tool combines **11 static analysis rules** with a **heuristic Machine Learning classifier** (Random Forest / XGBoost) to produce quantified risk scores in the range 0–100 for each analyzed endpoint.

The system follows a hybrid three-phase pipeline — Data Collection & Parsing, Static Analysis & Feature Extraction, and ML Classification & Risk Scoring — to analyze HAR (HTTP Archive) files exported from browser DevTools or proxy tools. It features both a **CLI** for non-interactive CI/CD usage and an **interactive Go-based TUI** that communicates with the Python backend via NDJSON IPC over stdin/stdout.

Key results include:

- **438 automated tests** with **90% code coverage**
- ML model achieving **100% accuracy** (Random Forest) and **99.56% accuracy** (XGBoost) on the test set, exceeding all FR-304 targets
- Full end-to-end pipeline from HAR file → parsed flows → static analysis → ML prediction → risk scoring → JSON/HTML report generation

---

## 2. Introduction

### 2.1 Problem Statement

Cross-Site Request Forgery (CSRF) remains one of the most prevalent web application vulnerabilities. CSRF attacks exploit the trust that a web application has in the user's browser, allowing attackers to perform unauthorized actions on behalf of authenticated users. Despite well-known mitigation strategies — CSRF tokens, SameSite cookies, Origin/Referer validation — many applications still fail to implement them correctly.

Existing tools have significant limitations:

| Approach                             | Limitation                                                  |
| ------------------------------------ | ----------------------------------------------------------- |
| **Manual Code Review**               | Time-consuming, error-prone, doesn't scale                  |
| **Traditional Scanners** (ZAP, Burp) | Rule-based, high false positive rate, limited flow analysis |
| **Static Analysis Tools**            | Cannot understand runtime request flows                     |
| **Penetration Testing**              | Expensive, point-in-time, requires expert knowledge         |

### 2.2 Objectives

| #   | Objective                            | Measurable Outcome                            | Status      |
| --- | ------------------------------------ | --------------------------------------------- | ----------- |
| O1  | Develop a request flow analyzer      | Successfully parse HAR files                  | ✅ Achieved |
| O2  | Implement static analysis rules      | Detect 5+ CSRF categories (11 implemented)    | ✅ Achieved |
| O3  | Build a heuristic ML model           | Achieve ≥80% accuracy (100% achieved)         | ✅ Achieved |
| O4  | Create a risk scoring system (0–100) | Produce actionable, ranked risk reports       | ✅ Achieved |
| O5  | Deliver a usable CLI/TUI tool        | End-to-end functional tool with documentation | ✅ Achieved |

### 2.3 Key Innovation

Unlike traditional CSRF scanners that rely on simple signature matching, CSRF Shield AI:

- **Analyzes full request/response flows** (not just individual requests)
- **Uses heuristic ML** to learn patterns of CSRF-vulnerable vs. protected endpoints
- **Produces quantified risk scores** (0–100) rather than binary yes/no detection
- **Explains its reasoning** with detailed findings for each flagged endpoint
- **Short-circuits header-only auth** — JWT/Bearer token sessions are identified early and assigned low risk without wasted ML inference

---

## 3. Related Work

| Tool/Paper                      | Approach                           | Limitation vs. Our Approach                    |
| ------------------------------- | ---------------------------------- | ---------------------------------------------- |
| **OWASP ZAP**                   | Active/passive scanning with rules | No ML, limited flow analysis                   |
| **Burp Suite Pro**              | Proxy-based scanning               | Commercial, rule-based                         |
| **CSRFGuard**                   | Prevention library                 | Not a detection tool                           |
| **CSRF Scanner** (academic)     | Pattern matching                   | No risk quantification                         |
| **DeepCSRF** (Kim et al., 2023) | Deep learning for CSRF             | Requires large labeled datasets, heavy compute |

CSRF Shield AI bridges the gap between simple rule-based scanners and heavy ML systems by using **heuristic ML at a moderate level** — practical, explainable, and efficient.

---

## 4. System Architecture

### 4.1 High-Level Architecture

The system uses a **two-process architecture**:

| Component         | Technology               | Role                                           |
| ----------------- | ------------------------ | ---------------------------------------------- |
| **Backend**       | Python 3.10+             | HAR parsing, static analysis, ML, risk scoring |
| **Frontend**      | Go 1.21+ / gocui         | Interactive Terminal UI (TUI)                  |
| **Communication** | NDJSON over stdin/stdout | IPC protocol between Go TUI and Python         |

### 4.2 Pipeline Overview

```
HAR File → Parse → Reconstruct Flows → Detect Auth
  ├── [header_only] → Short-circuit (score=5, CSRF N/A)
  └── [cookie/mixed] → Static Analysis → Feature Extract
                          → ML Predict → Heuristic Boost
                            → Risk Score → Report (JSON/HTML)
```

### 4.3 Component Breakdown

| Component          | Module                              | Responsibility                                     |
| ------------------ | ----------------------------------- | -------------------------------------------------- |
| HAR Parser         | `src/input/har_parser.py`           | Parse HAR 1.2 files → `HttpExchange` objects       |
| Flow Reconstructor | `src/input/flow_reconstructor.py`   | Group exchanges by session cookie                  |
| Auth Detector      | `src/input/auth_detector.py`        | Classify auth: cookie / header_only / mixed / none |
| Static Analyzer    | `src/analysis/static_analyzer.py`   | Orchestrate 11 CSRF detection rules                |
| Feature Extractor  | `src/analysis/feature_extractor.py` | Extract 14 ML features per exchange                |
| ML Predictor       | `src/ml/predictor.py`               | Random Forest inference                            |
| Heuristics         | `src/ml/heuristics.py`              | Adjust ML probability with context rules           |
| Risk Scorer        | `src/scoring/risk_scorer.py`        | Calculate 0–100 score with modifiers               |
| Report Generator   | `src/output/report_generator.py`    | JSON and HTML report output                        |
| IPC Server         | `src/ipc_server.py`                 | NDJSON server wrapping full pipeline               |
| Pipeline           | `src/pipeline.py`                   | End-to-end orchestration                           |

---

## 5. Technical Design

### 5.1 Core Data Models

Four frozen dataclasses power the entire pipeline:

- **`HttpExchange`** — A single HTTP request/response pair with method, URL, headers, cookies, body, and timestamp
- **`SessionFlow`** — An ordered sequence of exchanges belonging to one user session, tagged with `AuthMechanism`
- **`Finding`** — A single security finding from static analysis, with rule ID, severity, description, and evidence
- **`AnalysisResult`** — Final analysis output for a single endpoint with risk score (0–100), risk level, findings, recommendations, and ML probability

### 5.2 Static Analysis Rules

11 rules are implemented in `src/analysis/rules/`:

| Rule ID  | Rule Name                     | Severity |
| -------- | ----------------------------- | -------- |
| CSRF-001 | Missing CSRF Token in Form    | HIGH     |
| CSRF-002 | Missing CSRF Token in Header  | MEDIUM   |
| CSRF-003 | Predictable CSRF Token        | HIGH     |
| CSRF-004 | Static CSRF Token             | CRITICAL |
| CSRF-005 | Missing SameSite Cookie       | MEDIUM   |
| CSRF-006 | SameSite=None Without Secure  | HIGH     |
| CSRF-007 | No Origin Header Validation   | MEDIUM   |
| CSRF-008 | GET Request with Side Effects | HIGH     |
| CSRF-009 | Missing Referer Validation    | LOW      |
| CSRF-010 | JSON Endpoint Without CORS    | MEDIUM   |
| CSRF-011 | Non-Cookie Auth (CSRF N/A)    | INFO     |

### 5.3 Authentication Short-Circuit

When the Auth Detector classifies a session as `header_only` (JWT Bearer / API key), the system **short-circuits** with a fixed score of 5 (LOW) and skips the entire ML pipeline. This improves both accuracy (avoiding false positives on inherently safe sessions) and performance.

### 5.4 Token Identification

A three-tier strategy identifies CSRF tokens in form data:

1. **Tier 1:** Exact name match against known token names (`csrf_token`, `csrfmiddlewaretoken`, `_token`, etc.)
2. **Tier 2:** Fuzzy keyword match (contains `csrf`, `xsrf`, `forgery`)
3. **Tier 3:** High-entropy string detection (≥16 chars, Shannon entropy ≥3.5 bits/char)

---

## 6. AI/ML Component

### 6.1 Feature Engineering

14 features are extracted per HTTP exchange:

| Feature                     | Type        | Description                                |
| --------------------------- | ----------- | ------------------------------------------ |
| `has_csrf_token_in_form`    | Boolean     | Hidden form field with CSRF token pattern  |
| `has_csrf_token_in_header`  | Boolean     | Custom anti-CSRF header present            |
| `has_samesite_cookie`       | Categorical | SameSite attribute value                   |
| `has_origin_check`          | Boolean     | Evidence of Origin header validation       |
| `has_referer_check`         | Boolean     | Evidence of Referer validation             |
| `http_method`               | Categorical | GET/POST/PUT/DELETE/PATCH                  |
| `is_state_changing`         | Boolean     | Heuristic: does the endpoint modify state? |
| `content_type`              | Categorical | Form-urlencoded, multipart, JSON, etc.     |
| `requires_auth`             | Boolean     | Session cookie or auth header present      |
| `token_entropy`             | Float       | Shannon entropy of token value             |
| `token_changes_per_request` | Boolean     | Token rotation detection                   |
| `response_sets_cookie`      | Boolean     | Response sets new cookies                  |
| `auth_mechanism`            | Categorical | cookie / header_only / mixed               |
| `endpoint_sensitivity`      | Float       | Heuristic score based on URL patterns      |

### 6.2 Model Selection

| Model                | Role      | Rationale                                            |
| -------------------- | --------- | ---------------------------------------------------- |
| **Random Forest** ⭐ | Primary   | Good accuracy, interpretable, handles mixed features |
| **XGBoost**          | Secondary | Higher accuracy potential, comparison baseline       |

Classical ML was chosen over deep learning because: (1) dataset size (~1,500 samples) is ideal for tree-based models, (2) feature importance provides explainability critical for security tools, (3) inference is ~1ms/sample with no GPU requirement.

### 6.3 Training Data

| Source          | Method                | Volume             |
| --------------- | --------------------- | ------------------ |
| Synthetic data  | Auto-generated script | ~600 vectors       |
| OWASP Benchmark | Known vulnerable/safe | ~400 samples       |
| DVWA / WebGoat  | Captured + augmented  | ~200 vectors       |
| Real-world HAR  | Manually labeled      | ~300 samples       |
| **Total**       |                       | **~1,500 samples** |

Dataset split: 70% training, 15% validation, 15% test.

### 6.4 Training Results

| Metric    | Target | Random Forest  | XGBoost        |
| --------- | ------ | -------------- | -------------- |
| Accuracy  | ≥80%   | **100.00%** ✅ | **99.56%** ✅  |
| Precision | ≥75%   | **100.00%** ✅ | **99.13%** ✅  |
| Recall    | ≥85%   | **100.00%** ✅ | **100.00%** ✅ |
| F1-Score  | ≥80%   | **100.00%** ✅ | **99.56%** ✅  |
| AUC-ROC   | ≥85%   | **100.00%** ✅ | **100.00%** ✅ |

**Best model:** Random Forest (selected by F1-score). Serialized to `models/csrf_model.pkl`.

### 6.5 Heuristic Boost

After ML inference, heuristic rules adjust the probability:

- **CSRF-004 (Static Token):** Force probability ≥0.95
- **Sensitive endpoints** (`/admin`, `/transfer`, `/delete`): Multiply by 1.2
- **GET with action params** (`?action=`, `?op=`): Multiply by 1.3
- **Multiple protections (defense-in-depth):** Multiply by 0.6

---

## 7. Risk Scoring Model

### 7.1 Formula

```
Base Score = (0.50 × ML_Probability + 0.50 × Static_Normalized_Score) × 100
Final Score = Clamp(Base Score + Context_Modifier_Sum, 0, 100)
```

Where `Static_Normalized_Score = sum(triggered_severities) / max_possible_severity`.

### 7.2 Score Interpretation

| Score Range | Risk Level  | Action                                 |
| ----------- | ----------- | -------------------------------------- |
| 0–20        | 🟢 LOW      | Acceptable risk, monitor only          |
| 21–40       | 🟡 MEDIUM   | Review recommended                     |
| 41–70       | 🟠 HIGH     | Remediation required before production |
| 71–100      | 🔴 CRITICAL | Immediate action required              |

### 7.3 Context Modifiers

| Factor                    | Modifier |
| ------------------------- | -------- |
| Financial data endpoint   | +15      |
| User data modification    | +10      |
| Admin-only endpoint       | +10      |
| HTTPS in use              | -5       |
| Multiple CSRF protections | -15      |
| GET-based state change    | +20      |

---

## 8. Interactive TUI & IPC

### 8.1 Two-Process Architecture

The Go TUI spawns the Python backend as a subprocess and communicates via NDJSON (newline-delimited JSON) over stdin/stdout:

```
Go TUI (gocui) ←→ stdin/stdout ←→ Python IPC Server
```

### 8.2 IPC Methods

The IPC server (`src/ipc_server.py`) supports 8 methods:

| Method          | Purpose                              |
| --------------- | ------------------------------------ |
| `ping`          | Health check                         |
| `load_har`      | Parse HAR file and reconstruct flows |
| `list_flows`    | Return session flow summaries        |
| `analyze_flow`  | Run full analysis on one session     |
| `analyze_all`   | Analyze all sessions sequentially    |
| `get_results`   | Return cached results                |
| `cancel`        | Cancel in-progress analysis          |
| `export_report` | Generate JSON/HTML report file       |

### 8.3 TUI Features

- **Panel-based layout:** Sessions, Exchanges, Analysis Engine
- **Vim-style navigation:** h/j/k/l, Tab for panel switching
- **Modal system:** Help, export, raw view, finding detail, quit confirm
- **Real-time progress:** Per-session and per-step analysis progress
- **State machine:** LAUNCH → LOADING → BROWSING → ANALYZING → EXPORTING → EXIT

---

## 9. Implementation Summary

### 9.1 Codebase Statistics

| Component                    | Files  | Lines of Code |
| ---------------------------- | ------ | ------------- |
| Python backend (`src/`)      | 36     | 5,481         |
| Python tests (`tests/`)      | 20     | 5,915         |
| Go TUI (`cmd/`, `internal/`) | 12     | 2,236         |
| **Total**                    | **68** | **13,632**    |

### 9.2 Module Breakdown

```
src/
├── main.py                 # CLI entry point (Click)
├── pipeline.py             # End-to-end orchestration
├── ipc_server.py           # NDJSON IPC server
├── input/                  # HAR parsing, flow reconstruction, auth detection
├── analysis/               # Static analyzer + 11 rules + feature extractor
│   └── rules/              # Individual CSRF-001 through CSRF-011
├── ml/                     # Trainer, predictor, heuristics
├── scoring/                # Risk scorer
├── output/                 # Report generator (JSON + HTML templates)
└── web/                    # Optional Flask dashboard
```

### 9.3 Technology Stack

| Layer              | Technology                         |
| ------------------ | ---------------------------------- |
| Language (backend) | Python 3.10+                       |
| Language (TUI)     | Go 1.21+                           |
| ML Framework       | scikit-learn, XGBoost              |
| Data Processing    | pandas, numpy                      |
| CLI Framework      | Click                              |
| Templating         | Jinja2                             |
| Testing            | pytest (Python), `go test` (Go)    |
| Configuration      | PyYAML (rules.yaml, settings.yaml) |

---

## 10. Testing & Quality Assurance

### 10.1 Test Coverage

- **Total tests:** 438
- **Code coverage:** 90% (exceeds NFR-401 target of ≥80%)
- **Test framework:** pytest with fixtures in `tests/conftest.py`

### 10.2 Test Categories

| Category          | Description                                   | Count |
| ----------------- | --------------------------------------------- | ----- |
| Unit tests        | Individual functions and classes              | ~350  |
| Integration tests | Multi-module pipeline flows                   | ~60   |
| End-to-end        | HAR → full pipeline → report                  | ~20   |
| Edge cases        | Empty inputs, malformed data, boundary values | ~8    |

### 10.3 Key Test Areas

- **HAR Parser:** All 3 content types (urlencoded, multipart, JSON), `postData.params` fallback
- **Auth Detector:** Cookie-only, bearer-only, API-key, mixed, and no-auth cases
- **Static Rules:** Each of the 11 rules tested with positive and negative cases
- **Token Identification:** Three-tier strategy with entropy calculations
- **ML Pipeline:** Training, prediction, heuristic adjustments
- **Risk Scorer:** Base score calculation, context modifiers, clamping
- **IPC Server:** All 8 methods with golden fixture validation

### 10.4 Code Quality

- **Linting:** Flake8 with 79-char line limit
- **Type checking:** mypy for type annotation verification
- **Docstrings:** All public functions documented (Google-style)
- **Coding standard:** PEP 8 compliant

---

## 11. Results & Evaluation

### 11.1 Objective Achievement

All five primary objectives from the proposal have been achieved:

| Objective       | Target                  | Result                                                     |
| --------------- | ----------------------- | ---------------------------------------------------------- |
| HAR parsing     | Parse HAR 1.2 files     | ✅ Supports all content types + `postData.params` fallback |
| Static analysis | ≥5 CSRF categories      | ✅ 11 rules implemented and tested                         |
| ML accuracy     | ≥80% accuracy           | ✅ 100% Random Forest, 99.56% XGBoost                      |
| Risk scoring    | 0–100 quantified scores | ✅ Base score + modifier formula with 4 risk levels        |
| Usable tool     | End-to-end CLI + TUI    | ✅ Both CLI and interactive TUI operational                |

### 11.2 Requirements Compliance

All **MUST-priority** requirements from `spec/Requirements.md` have been implemented:

- **FR-1xx (Input):** HAR parsing, flow reconstruction, auth detection ✅
- **FR-2xx (Static Analysis):** All 11 rules ✅
- **FR-3xx (ML):** Training, prediction, heuristics ✅
- **FR-4xx (Risk Scoring):** Formula, modifiers, short-circuit ✅
- **FR-5xx (Output):** JSON/HTML reports, CLI, TUI ✅
- **NFR-xxx:** Test coverage ≥80%, docstrings, configurable rules ✅

### 11.3 Sample Analysis Output

When analyzing `data/sample_har/vulnerable.har`:

```
🔍 Analyzing: vulnerable.har
📥 Parsed 3 exchange(s)
🔗 Reconstructed 1 session flow(s)
🔐 Auth mechanism: cookie
📊 Static analysis: 3 findings (CSRF-001, CSRF-005, CSRF-009)
🤖 ML probability: 0.92
📈 Risk score: 87 — 🔴 CRITICAL
💾 Report saved to: report.json
```

---

## 12. Discussion

### 12.1 Strengths

1. **Comprehensive coverage:** 11 rules cover the full spectrum of CSRF protection mechanisms
2. **Hybrid approach:** Combining ML + static analysis reduces false positives compared to either alone
3. **Explainability:** Risk scores come with detailed findings and per-rule remediation recommendations
4. **Performance:** Full pipeline completes in <10 seconds for typical HAR files
5. **Dual interface:** CLI for automation, TUI for interactive exploration

### 12.2 Limitations

1. **GraphQL support:** All GraphQL requests go to a single `/graphql` endpoint as POST, breaking URL-based heuristics. Requires body-level inspection not yet implemented.
2. **Training data size:** While 1,500 samples achieved excellent metrics, the model may not generalize to all web frameworks and authentication patterns.
3. **High ML accuracy concern:** 100% accuracy on the test set may indicate the model has perfectly learned the feature patterns in the training data. Real-world performance should be validated with unseen HAR captures.
4. **No active scanning:** The tool only analyzes captured traffic. It cannot discover endpoints or test for actual exploitability.

### 12.3 Lessons Learned

- **Short-circuit design pays off:** The JWT/header-only auth bypass saved significant development complexity and improved both accuracy and performance.
- **Synthetic data was invaluable:** Auto-generating 600 feature vectors in Phase 1 unblocked ML training early.
- **Two-process architecture works well:** Decoupling the Go TUI from the Python backend via IPC allowed independent development and testing.

---

## 13. Future Work

1. **GraphQL mutation detection** — Parse JSON bodies to distinguish mutations from queries
2. **Real-time proxy mode** — Integrate mitmproxy for live traffic analysis
3. **Multi-framework support** — Add framework-specific token detection (Django CSRF middleware, Spring Security, etc.)
4. **Confidence calibration** — Platt scaling or isotonic regression to calibrate ML probabilities
5. **Web dashboard** — Flask-based interface for non-CLI users (partially implemented)
6. **CI/CD integration** — GitHub Actions workflow for automated CSRF scanning in pipelines

---

## 14. Conclusion

CSRF Shield AI successfully demonstrates that a **hybrid static analysis + heuristic ML approach** can effectively detect CSRF vulnerabilities with high accuracy and practical usability. The tool analyzes HTTP traffic captures through a three-phase pipeline, producing quantified risk scores (0–100) with detailed, actionable findings.

All primary objectives were achieved: 11 CSRF detection rules, ML classification exceeding all accuracy targets, a 0–100 risk scoring system with context modifiers, and dual CLI/TUI interfaces for both automated and interactive use. The 438-test suite with 90% coverage ensures reliability and maintainability.

The project demonstrates that classical ML (Random Forest) with careful feature engineering can match or exceed deep learning approaches for structured security data, while maintaining the explainability that security tools demand.

---

## 15. References

1. OWASP Foundation. "Cross-Site Request Forgery (CSRF)." OWASP Top 10, 2021.
2. Zeller, W., and Felten, E.W. "Cross-Site Request Forgeries: Exploitation and Prevention." Princeton University Technical Report, 2008.
3. Barth, A., Jackson, C., and Mitchell, J.C. "Robust Defenses for Cross-Site Request Forgery." ACM CCS, 2008.
4. HAR 1.2 Specification. W3C Web Performance Working Group, 2012.
5. Pedregosa, F. et al. "Scikit-learn: Machine Learning in Python." JMLR 12, 2011.
6. Chen, T. and Guestrin, C. "XGBoost: A Scalable Tree Boosting System." KDD, 2016.
7. OWASP. "CSRF Prevention Cheat Sheet." OWASP Cheat Sheet Series, 2024.
8. Mozilla Developer Network. "SameSite cookies." MDN Web Docs, 2024.

---

> **Deliverable:** D8 — Final Project Report
> **Requirement Reference:** PROPOSAL.md §14
