# ✅ Tasks Breakdown — CSRF Shield AI

> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Version:** 1.1
> **Last Updated:** February 24, 2026
> **Proposal Reference:** `docs/PROPOSAL.md` v1.2, `docs/proposal/CLI_TUI_PROPOSAL.md` v2.3

---

## Task Legend

| Symbol | Status |
| --- | --- |
| ⬜ | Not started |
| 🔵 | In progress |
| ✅ | Complete |
| ❌ | Blocked |
| 🔄 | Needs revision |

---

## Phase 1: Foundation (Week 1–2)

### 1.1 Project Setup

- ✅ **T-101:** Initialize project repository with directory structure
- ✅ **T-102:** Create `requirements.txt` with all dependencies
- ✅ **T-103:** Create `setup.py` / `pyproject.toml` for package installation
- ✅ **T-104:** Set up `config/settings.yaml` with default configuration
- ✅ **T-105:** Set up `config/rules.yaml` with all 11 CSRF rule definitions
- ✅ **T-106:** Configure pytest and create test directory with fixtures

### 1.2 Data Models

- ✅ **T-111:** Implement `HttpExchange` dataclass — *Ref: FR-101*
- ✅ **T-112:** Implement `SessionFlow` dataclass — *Ref: FR-105*
- ✅ **T-113:** Implement `Finding` dataclass — *Ref: FR-201*
- ✅ **T-114:** Implement `AnalysisResult` dataclass — *Ref: FR-401*
- ✅ **T-115:** Write unit tests for all data models

### 1.3 HAR Parser

- ✅ **T-121:** Implement HAR 1.2 file reading and validation — *Ref: FR-101*
- ✅ **T-122:** Parse request/response pairs into `HttpExchange` objects
- ✅ **T-123:** Handle `application/x-www-form-urlencoded` body parsing — *Ref: FR-102*
- ✅ **T-124:** Handle `multipart/form-data` body parsing (text fields only) — *Ref: FR-103*
- ✅ **T-125:** Handle `application/json` body parsing — *Ref: FR-104*
- ✅ **T-126:** Implement `postData.params` fallback for truncated bodies — *Ref: FR-107*
- ✅ **T-127:** Write unit tests for HAR parser (all content types)

### 1.4 Flow Reconstructor

- ✅ **T-131:** Implement session identification from cookies
- ✅ **T-132:** Group exchanges into `SessionFlow` objects — *Ref: FR-105*
- ✅ **T-133:** Sort exchanges chronologically within each flow
- ✅ **T-134:** Write unit tests for flow reconstruction

### 1.5 Auth Mechanism Detector

- ✅ **T-141:** Implement `detect_auth_mechanism()` with all 5 custom auth headers — *Ref: FR-106*
- ✅ **T-142:** Implement short-circuit logic for `header_only` auth — *Ref: FR-212, FR-404*
- ✅ **T-143:** Generate `AnalysisResult` with CSRF-011 finding for short-circuited flows
- ✅ **T-144:** Write unit tests for auth detection (cookie, bearer, API key, mixed, none)

### 1.6 Synthetic Data Generator

- ✅ **T-151:** Implement `generate_synthetic_data.py` script — *Ref: FR-306*
- ✅ **T-152:** Generate ~300 vulnerable samples (various missing protections)
- ✅ **T-153:** Generate ~300 protected samples (various protection combinations)
- ✅ **T-154:** Output labeled CSV/JSON files to `data/synthetic/`
- ✅ **T-155:** Validate synthetic data quality and feature distribution

### 1.7 CLI Entry Point

- ✅ **T-161:** Implement `main.py` with argparse CLI — *Ref: FR-504*
- ✅ **T-162:** Add `analyze` subcommand skeleton
- ✅ **T-163:** Add `train` subcommand skeleton

---

## Phase 2: Static Analysis (Week 3–4)

### 2.1 Token Identification

- ⬜ **T-201:** Implement 3-tier token identification strategy — *Ref: FR-302*
- ⬜ **T-202:** Implement Shannon entropy calculation
- ⬜ **T-203:** Build known token name registry (Django, Laravel, Spring, Rails, ASP.NET)
- ⬜ **T-204:** Write unit tests for token identification (all 3 tiers)

### 2.2 Static Analysis Rules

- ⬜ **T-211:** Implement `csrf_001.py` — Missing CSRF Token in Form — *Ref: FR-202*
- ⬜ **T-212:** Implement `csrf_002.py` — Missing CSRF Token in Header — *Ref: FR-203*
- ⬜ **T-213:** Implement `csrf_003.py` — Predictable CSRF Token (low entropy) — *Ref: FR-204*
- ⬜ **T-214:** Implement `csrf_004.py` — Static CSRF Token (non-rotating) — *Ref: FR-205*
- ⬜ **T-215:** Implement `csrf_005.py` — Missing SameSite Cookie — *Ref: FR-206*
- ⬜ **T-216:** Implement `csrf_006.py` — SameSite=None Without Secure — *Ref: FR-207*
- ⬜ **T-217:** Implement `csrf_007.py` — No Origin Header Validation — *Ref: FR-208*
- ⬜ **T-218:** Implement `csrf_008.py` — GET Request with Side Effects — *Ref: FR-209*
- ⬜ **T-219:** Implement `csrf_009.py` — Missing Referer Validation — *Ref: FR-210*
- ⬜ **T-220:** Implement `csrf_010.py` — JSON Endpoint Without CORS — *Ref: FR-211*
- ⬜ **T-221:** Write unit tests for each rule (positive + negative cases)

### 2.3 Feature Extraction

- ⬜ **T-231:** Implement `feature_extractor.py` — extract all 14 features — *Ref: FR-301*
- ⬜ **T-232:** Implement categorical feature encoding (one-hot for SameSite, method, content_type, auth_mechanism)
- ⬜ **T-233:** Implement feature normalization
- ⬜ **T-234:** Write unit tests for feature extraction

### 2.4 Static Analyzer Orchestrator

- ⬜ **T-241:** Implement `static_analyzer.py` — run all rules against a SessionFlow
- ⬜ **T-242:** Implement rule loading from `config/rules.yaml`
- ⬜ **T-243:** Write integration test: HAR → parse → static analysis → findings

---

## Phase 3: ML Pipeline (Week 5–6)

### 3.1 Data Preparation

- ⬜ **T-301:** Collect and label OWASP Benchmark samples (~400)
- ⬜ **T-302:** Capture and augment DVWA/WebGoat traffic (~200) — *Ref: FR-307*
- ⬜ **T-303:** Collect and label real-world HAR files (~300)
- ⬜ **T-304:** Merge all data sources into unified training dataset
- ⬜ **T-305:** Implement train/validation/test split (70/15/15)

### 3.2 Model Training

- ⬜ **T-311:** Implement `trainer.py` — training pipeline — *Ref: FR-303*
- ⬜ **T-312:** Train Random Forest classifier
- ⬜ **T-313:** Train XGBoost classifier (secondary) — *Ref: FR-308*
- ⬜ **T-314:** Evaluate models against accuracy targets — *Ref: FR-304*
- ⬜ **T-315:** Serialize best model to `.pkl` file
- ⬜ **T-316:** Document model performance metrics

### 3.3 Inference Engine

- ⬜ **T-321:** Implement `predictor.py` — load model and predict — *Ref: FR-303*
- ⬜ **T-322:** Implement `heuristics.py` — heuristic boost logic — *Ref: FR-305*
- ⬜ **T-323:** Write unit tests for prediction + heuristic adjustments

---

## Phase 4: Risk Scoring, Reports & TUI (Week 7–8)

### 4.1 Risk Scoring

- ⬜ **T-401:** Implement `risk_scorer.py` — Base Score + Modifier formula — *Ref: FR-401*
- ⬜ **T-402:** Implement static score normalization (severity → 0.0–1.0 mapping)
- ⬜ **T-403:** Implement context modifier detection and application — *Ref: FR-403*
- ⬜ **T-404:** Implement risk level classification (LOW/MEDIUM/HIGH/CRITICAL) — *Ref: FR-402*
- ⬜ **T-405:** Write unit tests for scoring (verify math with proposal examples)

### 4.2 Report Generation

- ⬜ **T-411:** Implement JSON report output — *Ref: FR-501*
- ⬜ **T-412:** Design HTML report template (`templates/report.html`)
- ⬜ **T-413:** Implement HTML report generation with Jinja2 — *Ref: FR-502*
- ⬜ **T-414:** Include remediation recommendations per finding — *Ref: FR-503*
- ⬜ **T-415:** Write tests for report generation

### 4.3 End-to-End Integration

- ⬜ **T-421:** Implement full pipeline: HAR → parse → analyze → score → report
- ⬜ **T-422:** Write integration test with sample HAR file
- ⬜ **T-423:** Validate output against manually calculated expected scores

### 4.4 IPC Server *(Ref: CLI_TUI_PROPOSAL.md §3.2)*

- ⬜ **T-431:** Implement `src/ipc_server.py` — NDJSON server over stdin/stdout wrapping Phases 1–4 — *Ref: FR-506*
- ⬜ **T-432:** Implement IPC serialization (enum `.value` strings, `Finding.exchange` compact refs, `static_score` on-the-fly computation)
- ⬜ **T-433:** Create IPC golden fixtures in `tests/fixtures/ipc/` for cross-language testing
- ⬜ **T-434:** Write unit tests for `ipc_server.py` (all 8 methods + error responses + progress events)

### 4.5 Go TUI *(Ref: CLI_TUI_PROPOSAL.md §4–8)*

- ⬜ **T-435:** Initialize Go module (`cmd/tui/main.go`, `internal/`, `go.mod`) — *Ref: FR-505*
- ⬜ **T-436:** Implement Go data models mirroring Python dataclasses (`internal/models/types.go`)
- ⬜ **T-437:** Implement IPC client: process spawn, NDJSON stream, health ping, crash detection (`internal/ipc/`)
- ⬜ **T-438:** Implement TUI layout + panel rendering: Sessions, Exchanges, Analysis Engine (`internal/ui/panels/`)
- ⬜ **T-439:** Implement keybindings + modal system (help, export, raw view, finding detail, quit confirm) — *Ref: FR-507*
- ⬜ **T-440:** Implement status bar + toast notifications + clipboard strategy — *Ref: FR-510*
- ⬜ **T-441:** Implement state machine lifecycle (LAUNCH → LOADING → BROWSING → ANALYZING → EXPORTING → EXIT → ERROR)
- ⬜ **T-442:** Write TUI integration tests (Go ↔ Python IPC round-trip)

---

## Phase 5: Polish & Optional Dashboard (Week 9)

### 5.1 TUI Polish *(Ref: CLI_TUI_PROPOSAL.md §9)*

- ⬜ **T-501:** Handle terminal resize events and minimum size enforcement (100x24)
- ⬜ **T-502:** Implement virtual scrolling for large sessions (200+ exchanges)
- ⬜ **T-503:** Handle all empty/degenerate states (0 sessions, 0 exchanges, GETs only)
- ⬜ **T-504:** Test TUI across minimum (100x24) and large (200x50) terminal sizes

### 5.2 Web Dashboard (Optional)

> **Note:** The Go TUI is the flagship interactive interface per CLI_TUI_PROPOSAL.md §11. The Flask dashboard is demoted to optional.

- ⬜ **T-511:** *(Optional)* Set up Flask app with file upload — *Ref: FR-601*
- ⬜ **T-512:** *(Optional)* Implement results visualization — *Ref: FR-602*
- ⬜ **T-513:** *(Optional)* Implement report export — *Ref: FR-603*

---

## Phase 6: Testing, Polish & Documentation (Week 10)

### 6.1 Testing

- ⬜ **T-601:** Run full test suite and achieve ≥80% coverage — *Ref: NFR-401*
- ⬜ **T-602:** Fix any failing tests
- ⬜ **T-603:** Run end-to-end test against DVWA live capture

### 6.2 Documentation

- ⬜ **T-611:** Write `docs/USER_GUIDE.md`
- ⬜ **T-612:** Write `docs/API_REFERENCE.md`
- ⬜ **T-613:** Ensure all public functions have docstrings — *Ref: NFR-402*
- ⬜ **T-614:** Update `README.md` with installation and usage instructions

### 6.3 Deliverables

- ⬜ **T-621:** Prepare final project report (PDF)
- ⬜ **T-622:** Create presentation slides
- ⬜ **T-623:** Record demo video
- ⬜ **T-624:** Final code review and cleanup

---

## Task Dependency Graph

```shell
T-101 (Project Setup)
  └─> T-111–T-115 (Data Models)
        ├─> T-121–T-127 (HAR Parser)
        │     └─> T-131–T-134 (Flow Reconstructor)
        │           └─> T-141–T-144 (Auth Detector)
        │                 └─> T-241–T-243 (Static Analyzer)
        │                       └─> T-311–T-316 (Model Training)
        │                             └─> T-401–T-405 (Risk Scoring)
        │                                   └─> T-421–T-423 (Integration)
        │                                         ├─> T-431–T-434 (IPC Server)
        │                                         │     └─> T-435–T-442 (Go TUI)
        │                                         │           └─> T-501–T-504 (TUI Polish)
        │                                         └─> T-411–T-415 (Reports)
        └─> T-151–T-155 (Synthetic Data)
              └─> T-301–T-305 (Data Prep)
                    └─> T-311 (Training)
```

---

*Tasks are tracked with IDs matching requirement IDs (e.g., T-121 implements FR-101). Update status symbols as work progresses.*
