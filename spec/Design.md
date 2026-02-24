# 🏗️ Design Document — CSRF Shield AI

> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Version:** 1.0
> **Last Updated:** February 24, 2026
> **Proposal Reference:** `docs/PROPOSAL.md` v1.2

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

```
┌─────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────┐
│  Input   │───>│ Flow Parser │───>│ Static       │───>│ ML         │───>│ Risk     │
│ HAR/Proxy│    │ + Auth Det. │    │ Analyzer     │    │ Classifier │    │ Scorer   │
└─────────┘    └─────────────┘    └──────────────┘    └────────────┘    └──────────┘
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
| **ML Framework** | scikit-learn, XGBoost | Classical ML, well-suited for tabular data |
| **Data Processing** | pandas, numpy | Feature engineering and data manipulation |
| **Web Framework** | Flask 3.0+ | Lightweight dashboard, minimal overhead |
| **Proxy Integration** | mitmproxy | Industry-standard traffic interception |
| **Templating** | Jinja2 | HTML report generation |
| **Testing** | pytest | Python testing standard |
| **Config** | YAML | Human-readable rule configuration |

---

## 6. Interface Design

### 6.1 CLI Interface

```shell
# Analyze a HAR file
csrf-shield analyze --input traffic.har --output report.json --format json

# Analyze with HTML report
csrf-shield analyze --input traffic.har --output report.html --format html

# Start proxy listener
csrf-shield proxy --port 8080 --output live_report.html

# Train model
csrf-shield train --data data/training/ --output src/ml/models/csrf_rf_model.pkl
```

### 6.2 Web Dashboard (Phase 5)

The Flask dashboard provides:
- Upload HAR files via drag-and-drop
- Real-time analysis progress
- Interactive risk score visualization
- Finding details with evidence excerpts
- Export reports in JSON/HTML/PDF

---

*This design document is maintained alongside the codebase and updated as architecture evolves.*
