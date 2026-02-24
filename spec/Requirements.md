# 📋 Requirements Document — CSRF Shield AI

> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Version:** 1.1
> **Last Updated:** February 24, 2026
> **Proposal Reference:** `docs/PROPOSAL.md` v1.2, `docs/proposal/CLI_TUI_PROPOSAL.md` v2.3

---

## 1. Functional Requirements

### 1.1 Input Processing (FR-1xx)

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-101 | Parse HAR 1.2 format files and extract HTTP request/response pairs | MUST | 1 |
| FR-102 | Handle `application/x-www-form-urlencoded` request bodies | MUST | 1 |
| FR-103 | Handle `multipart/form-data` request bodies (extract text fields, skip binary) | MUST | 1 |
| FR-104 | Handle `application/json` request bodies | MUST | 1 |
| FR-105 | Reconstruct user sessions from cookie-based session IDs | MUST | 1 |
| FR-106 | Detect authentication mechanism (cookie / header_only / mixed / none) | MUST | 1 |
| FR-107 | Support HAR files with truncated bodies (use `postData.params` fallback) | SHOULD | 1 |
| FR-108 | Accept input from mitmproxy for live traffic analysis | COULD | 5 |

### 1.2 Static Analysis (FR-2xx)

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-201 | Implement 11 CSRF detection rules (CSRF-001 through CSRF-011) | MUST | 2 |
| FR-202 | Detect missing CSRF tokens in form bodies (CSRF-001) | MUST | 2 |
| FR-203 | Detect missing CSRF tokens in request headers (CSRF-002) | MUST | 2 |
| FR-204 | Detect low-entropy (predictable) CSRF tokens (CSRF-003) | MUST | 2 |
| FR-205 | Detect static (non-rotating) CSRF tokens across requests (CSRF-004) | MUST | 2 |
| FR-206 | Detect missing SameSite cookie attribute (CSRF-005) | MUST | 2 |
| FR-207 | Detect SameSite=None without Secure flag (CSRF-006) | MUST | 2 |
| FR-208 | Detect missing Origin header validation (CSRF-007) | SHOULD | 2 |
| FR-209 | Detect state-changing GET requests via URL/query patterns (CSRF-008) | MUST | 2 |
| FR-210 | Detect missing Referer validation (CSRF-009) | SHOULD | 2 |
| FR-211 | Detect JSON endpoints without CORS restrictions (CSRF-010) | SHOULD | 2 |
| FR-212 | Flag non-cookie auth as CSRF N/A — short-circuit (CSRF-011) | MUST | 1 |

### 1.3 ML Classification (FR-3xx)

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-301 | Extract 14 features from each HTTP exchange for ML input | MUST | 2 |
| FR-302 | Identify CSRF tokens via 3-tier strategy (exact → fuzzy → entropy) | MUST | 2 |
| FR-303 | Train Random Forest classifier on labeled dataset (~1,500 samples) | MUST | 3 |
| FR-304 | Achieve ≥80% accuracy, ≥85% recall on test set | MUST | 3 |
| FR-305 | Apply heuristic boost rules to adjust ML probability | MUST | 3 |
| FR-306 | Generate synthetic training data via script | MUST | 1 |
| FR-307 | Apply data augmentation to DVWA/WebGoat captures | SHOULD | 3 |
| FR-308 | Evaluate XGBoost as secondary model and compare performance | SHOULD | 3 |

### 1.4 Risk Scoring (FR-4xx)

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-401 | Calculate risk score (0–100) using Base Score + Modifier model | MUST | 4 |
| FR-402 | Classify risk into 4 levels: LOW, MEDIUM, HIGH, CRITICAL | MUST | 4 |
| FR-403 | Apply context modifiers (financial data, admin endpoint, HTTPS, etc.) | MUST | 4 |
| FR-404 | Short-circuited sessions receive fixed score of 5 (LOW) | MUST | 1 |

### 1.5 Output & Reporting (FR-5xx)

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-501 | Generate JSON report with all findings, scores, and recommendations | MUST | 4 |
| FR-502 | Generate HTML report with visual risk indicators | MUST | 4 |
| FR-503 | Include remediation recommendations per finding | MUST | 4 |
| FR-504 | Provide CLI interface for non-interactive analysis | MUST | 1 |
| FR-505 | Provide interactive TUI for browsing sessions, exchanges, and analysis results | MUST | 4 |
| FR-506 | TUI communicates with Python backend via NDJSON IPC over stdin/stdout | MUST | 4 |
| FR-507 | TUI supports keyboard-driven navigation (Vim-style h/j/k/l + Tab) | MUST | 4 |
| FR-508 | TUI displays real-time analysis progress with per-session and per-step granularity | SHOULD | 4 |
| FR-509 | TUI supports export to JSON/HTML from within the interface | MUST | 4 |
| FR-510 | TUI supports copying exchange as cURL command to clipboard | SHOULD | 4 |

### 1.6 Web Dashboard (FR-6xx)

> **Note:** Demoted from flagship per CLI_TUI_PROPOSAL.md §11. The Go TUI (FR-505) is the primary interactive interface.

| ID | Requirement | Priority | Phase |
| --- | --- | --- | --- |
| FR-601 | Upload HAR files via web interface | COULD | 5 |
| FR-602 | Display analysis results with interactive visualizations | COULD | 5 |
| FR-603 | Export reports from dashboard | COULD | 5 |

---

## 2. Non-Functional Requirements

### 2.1 Performance (NFR-1xx)

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-101 | Analyze a typical HAR file (500–2,000 entries) in under 10 seconds | <10s |
| NFR-102 | ML inference time per sample | <5ms |
| NFR-103 | Total model file size | <5MB |
| NFR-104 | No GPU requirement — CPU-only inference | ✅ |

### 2.2 Accuracy (NFR-2xx)

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-201 | ML model accuracy | ≥80% |
| NFR-202 | ML model recall (minimize false negatives) | ≥85% |
| NFR-203 | ML model precision (minimize false positives) | ≥75% |
| NFR-204 | ML model F1-Score | ≥80% |
| NFR-205 | ML model AUC-ROC | ≥0.85 |

### 2.3 Usability (NFR-3xx)

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-301 | CLI requires no configuration for basic usage | ✅ |
| NFR-302 | Reports are self-contained (no external dependencies) | ✅ |
| NFR-303 | Risk scores include natural-language explanations | ✅ |
| NFR-304 | TUI minimum terminal size | 100×24 |
| NFR-305 | TUI keyboard response latency | <50ms |
| NFR-306 | TUI compiles to single static binary (Go) | ✅ |

### 2.4 Maintainability (NFR-4xx)

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-401 | Test coverage for core modules | ≥80% |
| NFR-402 | All public functions have docstrings | ✅ |
| NFR-403 | Rules are configurable via YAML files | ✅ |
| NFR-404 | New rules can be added without modifying core code | ✅ |

### 2.5 Security & Ethics (NFR-5xx)

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-501 | Tool performs passive analysis only (no active requests) | ✅ |
| NFR-502 | No attack payload generation | ✅ |
| NFR-503 | Input requires user-provided HAR files (no unauthorized scanning) | ✅ |

---

## 3. Constraints

| Constraint | Description |
| --- | --- |
| **C-01** | Python 3.10+ required |
| **C-02** | Training data limited to ~1,500 samples |
| **C-03** | No deep learning — classical ML only (course requirement) |
| **C-04** | 10-week development timeline |
| **C-05** | Single-developer / small team capacity |
| **C-06** | Go 1.21+ required for TUI component |

---

## 4. Out of Scope

The following are explicitly **not** part of this project:

- Active exploitation or proof-of-concept generation
- Non-CSRF vulnerability detection (XSS, SQLi, etc.)
- Authentication/authorization testing
- GraphQL body inspection (documented as future work)
- Real-time WAF integration
- Automated remediation (tool provides recommendations only)

---

## 5. Acceptance Criteria

The project is considered complete when:

1. ✅ All MUST-priority requirements are implemented and tested
2. ✅ ML model meets NFR-2xx accuracy targets on the test set
3. ✅ End-to-end analysis of a sample HAR file produces a valid risk report
4. ✅ Documentation (User Guide + API Reference) is complete
5. ✅ Live demo successfully analyzes a DVWA traffic capture
6. ✅ TUI can load HAR, analyze sessions, display findings, and export reports interactively

---

*Requirements are tracked using MoSCoW prioritization (MUST/SHOULD/COULD). All MUST items are required for project completion.*
