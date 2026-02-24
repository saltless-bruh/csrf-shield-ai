# 🏗️ Design Document — CSRF Shield AI

> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Version:** 1.1
> **Last Updated:** February 24, 2026
> **Proposal Reference:** `docs/PROPOSAL.md` v1.2, `docs/proposal/CLI_TUI_PROPOSAL.md` v2.3

---

## 1. System Overview

CSRF Shield AI is a passive security analysis tool that detects Cross-Site Request Forgery vulnerabilities by analyzing HTTP traffic captures. It combines static rule-based analysis with machine learning classification to produce quantified risk scores (0–100) for each endpoint.

### 1.1 Design Philosophy

| Principle | Description |
| --- | --- |
| **Passive-only** | Never sends requests to target applications — analyzes captured traffic only |
| **Explainable** | Every risk score can be traced back to specific rules and features |
| **Modular** | Each analysis phase is independent and testable in isolation |
| **Fail-safe** | Inconclusive results lower confidence rather than producing false positives |

---

## 2. Architecture

### 2.1 High-Level Pipeline

```shell
┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────┐
│  Input   │───>│ Flow Parser │───>│ Static       │───>│ ML         │───>│ Risk     │
│ HAR/Proxy│    │ + Auth Det. │    │ Analyzer     │    │ Classifier │    │ Scorer   │
└──────────┘    └─────────────┘    └──────────────┘    └────────────┘    └──────────┘
                     │                                                        │
                     │  [header_only auth?]                                   │
                     │  YES → Short-circuit                                   ▼
                     └──────────────────────────────────────────────────> ┌──────────┐
                                                                          │  Report  │
                                                                          │ Generator│
                                                                          └──────────┘
```

### 2.2 Phase Responsibilities

| Phase | Module(s) | Input | Output |
| --- | --- | --- | --- |
| **Phase 1** | `har_parser.py`, `models.py`, `auth_detector.py` | HAR file / proxy stream | `SessionFlow` objects |
| **Phase 2** | `static_analyzer.py`, `feature_extractor.py`, `rules/` | `SessionFlow` | `Finding[]` + feature vectors |
| **Phase 3** | `predictor.py`, `heuristics.py` | Feature vectors + findings | ML probability + heuristic-adjusted score |
| **Scoring** | `risk_scorer.py` | ML prob + static severity + context | Final risk score (0–100) |
| **Output** | `report_generator.py` | All findings + scores | JSON / HTML reports |

### 2.3 Short-Circuit Path

When `auth_detector.py` identifies a session using **purely header-based authentication** (Bearer tokens, API keys, etc.), the pipeline short-circuits:

- Skip Phases 2 and 3 entirely
- Emit `CSRF-011` finding (INFO)
- Assign fixed risk score = **5** (LOW)
- Produce final `AnalysisResult` directly

This is a conscious design trade-off: we sacrifice depth of analysis for correctness — CSRF is simply not applicable to header-only auth, so running the full pipeline would waste compute and potentially produce misleading results.

### 2.4 TUI ↔ Backend Architecture *(Ref: CLI_TUI_PROPOSAL.md §2–3)*

The interactive interface uses a **two-process architecture**:

```shell
┌───────────────────┐    stdin (NDJSON)    ┌───────────────────┐
│   Go TUI Process  │ ──────────────────>  │  Python Backend   │
│   (gocui, panels, │ <──────────────────  │  (ipc_server.py)  │
│    keybindings)   │    stdout (NDJSON)   │  Wraps Phases 1-4 │
└───────────────────┘                      └───────────────────┘
```

- **Go TUI** spawns `python src/ipc_server.py` as a child process
- Communication uses **NDJSON** (one JSON object per line) over stdin/stdout
- Python stderr is captured separately for logging (`~/.csrf-shield/backend.log`)
- Go side manages process lifecycle: health pings (every 5s), crash detection, restart
- 8 IPC methods: `ping`, `load_har`, `list_flows`, `analyze_flow`, `analyze_all`, `get_results`, `cancel`, `export_report`

---

## 3. Data Models

### 3.1 Core Entities

```python
@dataclass
class HttpExchange:
    """A single HTTP request/response pair."""
    request_method: str              # GET, POST, PUT, DELETE, PATCH
    request_url: str                 # Full URL
    request_headers: Dict[str, str]  # Request headers
    request_cookies: Dict[str, str]  # Parsed cookies from Cookie header
    request_body: Optional[str]      # Raw request body
    request_content_type: str        # Content-Type header
    response_status: int             # HTTP status code
    response_headers: Dict[str, str] # Response headers
    response_body: Optional[str]     # Raw response body
    timestamp: datetime              # When the exchange occurred

@dataclass
class SessionFlow:
    """An ordered sequence of exchanges belonging to one user session."""
    session_id: str                  # Derived from session cookie or auto-generated
    exchanges: List[HttpExchange]    # Chronologically ordered
    auth_mechanism: str              # 'cookie' | 'header_only' | 'mixed' | 'none'

@dataclass
class Finding:
    """A single security finding from static analysis."""
    rule_id: str                     # e.g., 'CSRF-001'
    rule_name: str                   # Human-readable name
    severity: str                    # CRITICAL | HIGH | MEDIUM | LOW | INFO
    description: str                 # What was found
    evidence: str                    # Supporting data/quote
    exchange: HttpExchange           # The exchange that triggered this finding

@dataclass
class AnalysisResult:
    """The final analysis output for a single endpoint/flow."""
    endpoint: str                    # URL path
    http_method: str                 # Method
    risk_score: int                  # 0–100
    risk_level: str                  # LOW | MEDIUM | HIGH | CRITICAL
    findings: List[Finding]          # All triggered rules
    ml_probability: Optional[float]  # ML prediction (None if short-circuited)
    feature_vector: Optional[Dict]   # Extracted features (None if short-circuited)
    recommendations: List[str]       # Remediation suggestions
```

> **IPC serialization note:** When transmitted over the NDJSON IPC protocol, each `AnalysisResult` includes an additional `static_score` field (computed on-the-fly by `ipc_server.py` as `sum(triggered_rule_severities) / max_possible_severity`). `Finding.exchange` is serialized as a compact reference `{"method": "POST", "url": "/path", "status": 200}` to avoid payload bloat. See CLI_TUI_PROPOSAL.md §3.2.

---

## 4. Key Design Decisions

### 4.1 Risk Scoring: Base + Modifier (not Weighted Average)

**Decision:** Use `Base Score = (W_ml × ML_Prob + W_static × Static_Norm) × 100` then `Final = Clamp(Base + Context_Modifiers, 0, 100)`.

**Rationale:** The original three-weight formula `(W_ml + W_static + W_context) × 100` was mathematically broken — context factors are flat integers (+15, -5), not 0.0–1.0 floats. Multiplying them by a weight and then by 100 would produce scores exceeding 400. The Base + Modifier model keeps the base score properly normalized and then applies context adjustments as simple additive bonuses.

### 4.2 Token Identification: 3-Tier Strategy

**Decision:** Identify CSRF tokens via (1) exact name match → (2) fuzzy keyword match → (3) high-entropy string detection.

**Rationale:** The `token_entropy` ML feature requires knowing *which* parameter is the token. If we guess wrong, we feed garbage data to the model. The 3-tier approach handles both standard framework tokens (Django's `csrfmiddlewaretoken`, Laravel's `_token`) and custom implementations.

### 4.3 Auth Detection: Broad Header Coverage

**Decision:** Check for `Authorization`, `X-API-Key`, `X-Auth-Token`, `Api-Key`, `X-Access-Token` — not just Bearer tokens.

**Rationale:** Many B2B APIs use custom API key headers. Only checking for `Authorization: Bearer` would miss these, causing false positives on API-key-authenticated endpoints.

### 4.4 DVWA Data: Augmentation Required

**Decision:** Apply data augmentation (randomize URLs, param names, headers) to DVWA/WebGoat captures.

**Rationale:** Capturing 200 raw requests to the same 3 endpoints causes data leakage. The model would memorize DVWA URLs instead of learning structural CSRF patterns.

---

## 5. Technology Stack

| Component | Technology | Justification |
| --- | --- | --- |
| **Language** | Python 3.10+ | Rich ML/security ecosystem, rapid development |
| **Language (TUI)** | Go 1.21+ | Compiled, single binary, goroutine concurrency for responsive UI |
| **TUI Framework** | gocui (jesseduffield/gocui) | Terminal UI with overlapping views, custom keybindings |
| **IPC Protocol** | NDJSON over stdin/stdout | Language-agnostic, debuggable, simple |
| **ML Framework** | scikit-learn, XGBoost | Classical ML, well-suited for tabular data |
| **Data Processing** | pandas, numpy | Feature engineering and data manipulation |
| **Web Framework** | Flask 3.0+ *(optional)* | Lightweight dashboard, demoted from flagship |
| **Proxy Integration** | mitmproxy | Industry-standard traffic interception |
| **Templating** | Jinja2 | HTML report generation |
| **Testing** | pytest (Python), `go test` (Go) | Standard testing for both languages |
| **Config** | YAML | Human-readable rule configuration |

---

## 6. Interface Design

### 6.1 CLI Interface

```shell
# Analyze a HAR file (non-interactive, CI/CD usage)
csrf-shield analyze --input traffic.har --output report.json --format json

# Analyze with HTML report
csrf-shield analyze --input traffic.har --output report.html --format html

# Launch interactive TUI (flagship interface)
csrf-shield tui --input traffic.har

# Start proxy listener
csrf-shield proxy --port 8080 --output live_report.html

# Train model
csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl
```

### 6.2 Terminal User Interface (TUI) — Flagship *(Ref: CLI_TUI_PROPOSAL.md)*

The Go TUI is the primary interactive interface, featuring:

- 3-panel layout: Sessions (top-left), Exchanges (bottom-left), Analysis Engine (right)
- Vim-style keyboard navigation (h/j/k/l, Tab, single-key actions)
- Real-time analysis progress with dual-level reporting (batch + pipeline)
- Modal popups for export, help, raw HTTP view, and finding detail
- Color-coded risk indicators: GREEN (LOW), YELLOW (MEDIUM), ORANGE (HIGH), RED (CRITICAL)

### 6.3 Web Dashboard *(Optional — Phase 5)*

> **Note:** Demoted from flagship per CLI_TUI_PROPOSAL.md §11. The TUI is the primary interactive interface.

The Flask dashboard provides:

- Upload HAR files via drag-and-drop
- Real-time analysis progress
- Interactive risk score visualization
- Finding details with evidence excerpts
- Export reports in JSON/HTML/PDF

---

*This design document is maintained alongside the codebase and updated as architecture evolves.*
