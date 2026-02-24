# 📋 Project Proposal: AI-Powered CSRF Risk Scoring Tool

> **Subject:** IAW (Web Application Security / Bảo mật ứng dụng Web)
> **Project Type:** Final Project
> **Date:** February 24, 2026
> **Version:** 1.2 (Revised — addresses peer review feedback)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Objectives](#3-objectives)
4. [Scope & Boundaries](#4-scope--boundaries)
5. [Background & Related Work](#5-background--related-work)
6. [Methodology](#6-methodology)
7. [System Architecture](#7-system-architecture)
8. [Technical Design](#8-technical-design)
9. [AI/ML Component](#9-aiml-component)
10. [Risk Scoring Model](#10-risk-scoring-model)
11. [Implementation Plan](#11-implementation-plan)
12. [Technology Stack](#12-technology-stack)
13. [Testing Strategy](#13-testing-strategy)
14. [Expected Deliverables](#14-expected-deliverables)
15. [Timeline](#15-timeline)
16. [Risk Assessment](#16-risk-assessment)
17. [References](#17-references)

---

## 1. Project Overview

### 1.1 Project Title

**CSRF Shield AI** — An Intelligent CSRF Risk Scoring Tool Based on Request Flow Analysis

### 1.2 Summary

This project develops an intelligent security analysis tool that **detects Cross-Site Request Forgery (CSRF) vulnerabilities** in web applications by analyzing HTTP request/response flows. The tool combines **static analysis** of request patterns with **heuristic Machine Learning (ML)** techniques to identify missing or improperly implemented CSRF protection mechanisms.

The primary output is a **CSRF Risk Scoring Tool** that assigns quantified risk scores to endpoints, enabling developers and security professionals to prioritize remediation efforts.

### 1.3 Key Innovation

Unlike traditional CSRF scanners that rely on simple signature matching, this tool:

- **Analyzes the full request/response flow** (not just individual requests)
- **Uses heuristic ML** to learn patterns of CSRF-vulnerable vs. protected endpoints
- **Produces a quantified risk score** (0–100) rather than binary yes/no detection
- **Explains its reasoning** with detailed findings for each flagged endpoint

---

## 2. Problem Statement

### 2.1 The CSRF Threat

Cross-Site Request Forgery (CSRF) remains one of the most prevalent web application vulnerabilities. CSRF attacks exploit the trust that a web application has in the user's browser, allowing attackers to perform unauthorized actions on behalf of authenticated users.

According to OWASP, CSRF is consistently listed among the top web application security risks. Despite well-known mitigation strategies (CSRF tokens, SameSite cookies, Origin/Referer validation), many applications still fail to implement them correctly.

### 2.2 Limitations of Current Approaches

| Approach | Limitation |
| --- | --- |
| **Manual Code Review** | Time-consuming, error-prone, doesn't scale |
| **Traditional Scanners** (e.g., OWASP ZAP, Burp Suite) | Rule-based, high false positive rate, misses contextual vulnerabilities |
| **Static Analysis Tools** | Cannot understand runtime request flows, limited to code patterns |
| **Penetration Testing** | Expensive, point-in-time, requires expert knowledge |

### 2.3 Gap Addressed

There is a need for a tool that:

1. **Automates** CSRF detection with higher accuracy than rule-based scanners
2. **Analyzes request flows** holistically (not just individual endpoints)
3. **Quantifies risk** to help prioritize security efforts
4. **Learns and adapts** to different application architectures and CSRF protection patterns

---

## 3. Objectives

### 3.1 Primary Objectives

| # | Objective | Measurable Outcome |
| --- | --- | --- |
| O1 | Develop a request flow analyzer that captures and parses HTTP request/response pairs | Successfully parse HAR files and live proxy traffic |
| O2 | Implement static analysis rules to detect missing CSRF tokens | Detect at least 5 categories of CSRF protection failures |
| O3 | Build a heuristic ML model for CSRF risk classification | Achieve ≥ 80% accuracy on test dataset |
| O4 | Create a risk scoring system (0–100) | Produce actionable, ranked risk reports |
| O5 | Deliver a usable CLI/Web-based tool | End-to-end functional tool with documentation |

### 3.2 Secondary Objectives

- Provide educational value by explaining CSRF vulnerabilities and mitigations
- Generate exportable reports (JSON, HTML)
- Support analysis of multiple web frameworks (Django, Flask, Express, Spring, Laravel)

---

## 4. Scope & Boundaries

### 4.1 In Scope ✅

| Area | Details |
| --- | --- |
| **Input Sources** | HAR files (HTTP Archive), intercepted proxy traffic (mitmproxy integration) |
| **Analysis Targets** | State-changing requests (POST, PUT, DELETE, PATCH) |
| **CSRF Patterns Detected** | Missing CSRF tokens, predictable tokens, token not validated, missing SameSite cookie attribute, missing Origin/Referer checks |
| **ML Approach** | Heuristic ML with feature engineering (moderate complexity) |
| **Output** | Risk score (0–100), detailed findings report, recommendations |
| **UI** | CLI tool + Web dashboard for results visualization |

### 4.2 Out of Scope ❌

| Area | Reason |
| --- | --- |
| Active exploitation / attack execution | Ethical and legal boundaries |
| Other vulnerability types (XSS, SQLi, etc.) | Focused scope on CSRF |
| Deep learning / neural networks | Exceeds "moderate level" ML requirement |
| Real-time MITM attack prevention | This is a detection/analysis tool, not a WAF |
| Mobile application analysis | Focus on web application HTTP traffic only |

---

## 5. Background & Related Work

### 5.1 CSRF Attack Mechanism

```shell
┌───────────┐          ┌──────────────┐          ┌──────────────┐
│  Victim   │          │   Attacker   │          │  Target Web  │
│  Browser  │          │   Website    │          │  Application │
└─────┬─────┘          └──────┬───────┘          └──────┬───────┘
      │   1. Victim logs in   │                         │
      │───────────────────────┼────────────────────────>│
      │   2. Session cookie   │                         │
      │<──────────────────────┼─────────────────────────│
      │                       │                         │
      │  3. Victim visits     │                         │
      │     attacker site     │                         │
      │──────────────────────>│                         │
      │  4. Malicious page    │                         │
      │<──────────────────────│                         │
      │                       │                         │
      │  5. Auto-submit form with session cookie        │
      │─────────────────────────────────────────────────>
      │  6. Action performed (e.g., transfer money)     │
      │<─────────────────────────────────────────────────
```

### 5.2 Standard CSRF Mitigations

1. **Synchronizer Token Pattern** — Unique token per session/request embedded in forms
2. **Double Submit Cookie** — Token in both cookie and request parameter
3. **SameSite Cookie Attribute** — `SameSite=Strict` or `SameSite=Lax`
4. **Origin/Referer Header Validation** — Server checks request origin
5. **Custom Request Headers** — Using headers like `X-Requested-With`

### 5.3 Related Tools & Research

| Tool/Paper | Approach | Limitation vs. Our Approach |
| --- | --- | --- |
| **OWASP ZAP** | Active/passive scanning with rules | No ML, limited flow analysis |
| **Burp Suite Pro** | Proxy-based scanning | Commercial, rule-based |
| **CSRFGuard** | Prevention library | Not a detection tool |
| **CSRF Scanner** (academic) | Pattern matching | No risk quantification |
| **DeepCSRF** (Kim et al., 2023) | Deep learning for CSRF detection | Requires large labeled datasets, heavy compute |

Our approach bridges the gap between simple rule-based scanners and heavy ML systems by using **heuristic ML at a moderate level** — practical, explainable, and efficient.

---

## 6. Methodology

### 6.1 Overall Approach: Hybrid Analysis Pipeline

The system follows a **three-phase analysis pipeline**:

```shell
┌─────────────────────────────────────────────────────────────────────┐
│                     CSRF SHIELD AI - Analysis Pipeline              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Phase 1: Data Collection & Parsing                                 │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐            │
│  │ HAR File │───>│  Flow Parser │───>│ Request/Response│            │
│  │ or Proxy │    │              │    │    Objects      │            │
│  └──────────┘    └──────────────┘    └───────┬─────────┘            │
│                                              │                      │
│  Phase 2: Static Analysis + Feature Extraction                      │
│  ┌───────────────────────────────────────────┼──────────────┐       │
│  │                                           ▼              │       │
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │       │
│  │  │ Token Check  │    │ Header Check │    │ Cookie     │  │       │
│  │  │ (form/header)│    │ (Origin/Ref) │    │ Analysis   │  │       │
│  │  └──────┬───────┘    └──────┬───────┘    └─────┬──────┘  │       │
│  │         └───────────────────┼──────────────────┘         │       │
│  │                             ▼                            │       │
│  │                    ┌────────────────┐                    │       │
│  │                    │ Feature Vector │                    │       │
│  │                    └────────┬───────┘                    │       │
│  └─────────────────────────────┼────────────────────────────┘       │
│                                │                                    │
│  Phase 3: ML Classification + Risk Scoring                          │
│  ┌─────────────────────────────┼────────────────────────────┐       │
│  │                             ▼                            │       │
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │       │
│  │  │  Heuristic   │───>│    Risk      │───>│   Report   │  │       │
│  │  │  ML Model    │    │   Scorer     │    │  Generator │  │       │
│  │  └──────────────┘    └──────────────┘    └────────────┘  │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Phase Details

#### Phase 1: Data Collection & Parsing

- **Input formats:** HAR files (exported from browser DevTools or proxy tools), mitmproxy dump files
- **Parsing:** Extract HTTP method, URL, headers, cookies, form/body parameters, response headers and body
- **Flow construction:** Group related requests into sessions/flows (e.g., login → dashboard → action)

#### Phase 2: Static Analysis + Feature Extraction

Apply rule-based checks and extract features for ML:

| Feature | Type | Description |
| --- | --- | --- |
| `has_csrf_token_in_form` | Boolean | Hidden form field with CSRF token pattern |
| `has_csrf_token_in_header` | Boolean | Custom header (X-CSRF-Token, X-XSRF-Token) |
| `has_samesite_cookie` | Categorical | SameSite attribute value (None/Lax/Strict/Missing) |
| `has_origin_check` | Boolean | Evidence of Origin header validation |
| `has_referer_check` | Boolean | Evidence of Referer header validation |
| `http_method` | Categorical | GET/POST/PUT/DELETE/PATCH |
| `is_state_changing` | Boolean | Heuristic: does the endpoint modify state? |
| `content_type` | Categorical | Form-urlencoded, multipart, JSON, etc. |
| `requires_auth` | Boolean | Session cookie or auth header present |
| `token_entropy` | Float | Shannon entropy of token value (if present) |
| `token_changes_per_request` | Boolean | Does token change between requests? |
| `response_sets_cookie` | Boolean | Does the response set new cookies? |
| `auth_mechanism` | Categorical | Authentication type: `cookie` / `bearer_header` / `mixed` (see §8.4) |
| `endpoint_sensitivity` | Float | Heuristic score based on URL patterns (e.g., `/admin`, `/transfer`, `/delete`) and query parameters (e.g., `?action=remove`, `?op=update`) |

#### Phase 3: ML Classification + Risk Scoring

- Train a **heuristic ML classifier** (Random Forest / Gradient Boosting) on labeled feature vectors
- Output: probability of CSRF vulnerability
- Combine ML probability with static analysis findings → **Risk Score (0–100)**

---

## 7. System Architecture

### 7.1 High-Level Architecture

```shell
┌─────────────────────────────────────────────────────────────────────┐
│                        CSRF SHIELD AI                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                       INPUT LAYER                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │   │
│  │  │  HAR File   │  │  mitmproxy  │  │  Manual URL Input   │   │   │
│  │  │  Importer   │  │  Listener   │  │  (Crawl & Capture)  │   │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │   │
│  └─────────┼────────────────┼────────────────────┼──────────────┘   │
│            └────────────────┼────────────────────┘                  │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    ANALYSIS ENGINE                           │   │
│  │                                                              │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐   │   │
│  │  │  Flow Parser   │  │  Static        │  │  Feature      │   │   │
│  │  │  & Session     │──│  Analyzer      │──│  Extractor    │   │   │
│  │  │  Reconstructor │  │  (Rule Engine) │  │               │   │   │
│  │  └────────────────┘  └────────────────┘  └───────┬───────┘   │   │
│  │                                                  │           │   │
│  │  ┌────────────────┐  ┌────────────────┐          │           │   │
│  │  │  Heuristic ML  │  │  Risk Score    │◄─────────┘           │   │
│  │  │  Classifier    │──│  Calculator    │                      │   │
│  │  └────────────────┘  └───────┬────────┘                      │   │
│  └──────────────────────────────┼───────────────────────────────┘   │
│                                 ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     OUTPUT LAYER                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │   │
│  │  │  CLI Report │  │  JSON/HTML  │  │  Web Dashboard      │   │   │
│  │  │             │  │  Export     │  │  (Results Viewer)   │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Component Breakdown

| Component | Responsibility | Key Technology |
| --- | --- | --- |
| **HAR Importer** | Parse HAR files into internal request objects | Python `json` module |
| **Proxy Listener** | Capture live traffic via mitmproxy | `mitmproxy` Python API |
| **Flow Parser** | Reconstruct request sequences, session tracking | Custom Python module |
| **Static Analyzer** | Rule-based CSRF protection checks | Custom rule engine |
| **Feature Extractor** | Transform analysis results into ML feature vectors | `pandas`, `numpy` |
| **ML Classifier** | Predict CSRF vulnerability probability | `scikit-learn` |
| **Risk Scorer** | Calculate weighted risk score (0–100) | Custom scoring formula |
| **Report Generator** | Produce human-readable reports | `Jinja2`, `json` |
| **Web Dashboard** | Visualize results in browser | `Flask` + vanilla JS |

---

## 8. Technical Design

### 8.1 Data Models

#### RequestFlow Object

```python
@dataclass
class HttpExchange:
    """Represents a single HTTP request/response pair."""
    request_method: str           # GET, POST, PUT, DELETE, PATCH
    request_url: str              # Full URL
    request_headers: Dict[str, str]
    request_cookies: Dict[str, str]
    request_body: Optional[str]
    request_content_type: str
    
    response_status: int
    response_headers: Dict[str, str]
    response_body: Optional[str]
    
    timestamp: datetime

@dataclass
class SessionFlow:
    """Represents a sequence of exchanges within a session."""
    session_id: str
    exchanges: List[HttpExchange]
    session_cookies: Dict[str, str]

@dataclass
class AnalysisResult:
    """Result of analyzing a single exchange for CSRF risk."""
    exchange: HttpExchange
    findings: List[Finding]
    feature_vector: Optional[Dict[str, Any]]  # None if short-circuited (§8.4)
    ml_probability: Optional[float] = None    # None if short-circuited, else 0.0–1.0
    risk_score: int               # 0 - 100
    risk_level: str               # LOW / MEDIUM / HIGH / CRITICAL
    recommendations: List[str]
```

#### Finding Object

```python
@dataclass
class Finding:
    """A specific CSRF-related finding."""
    rule_id: str                  # e.g., "CSRF-001"
    title: str                    # e.g., "Missing CSRF Token in Form"
    severity: str                 # LOW / MEDIUM / HIGH / CRITICAL
    description: str
    evidence: str                 # Specific data from the request/response
    recommendation: str
```

### 8.2 Static Analysis Rules

| Rule ID | Rule Name | Severity | Description |
| --- | --- | --- | --- |
| CSRF-001 | Missing CSRF Token in Form | HIGH | State-changing request without CSRF token in form body |
| CSRF-002 | Missing CSRF Token in Header | MEDIUM | No custom anti-CSRF header present |
| CSRF-003 | Predictable CSRF Token | HIGH | Token has low entropy (< 3.0 bits/char) |
| CSRF-004 | Static CSRF Token | CRITICAL | Same token used across multiple requests |
| CSRF-005 | Missing SameSite Cookie | MEDIUM | Session cookie without SameSite attribute |
| CSRF-006 | SameSite=None Without Secure | HIGH | SameSite=None but Secure flag not set |
| CSRF-007 | No Origin Header Validation | MEDIUM | Server doesn't reject cross-origin requests |
| CSRF-008 | GET Request with Side Effects | HIGH | State-changing operation via GET method (detected via URL patterns: `/delete`, `/update`, `/add`, `/remove`, `/transfer`; and query params: `?action=`, `?op=`, `?do=`) |
| CSRF-009 | Missing Referer Validation | LOW | No evidence of Referer header checking |
| CSRF-010 | JSON Endpoint Without CORS | MEDIUM | JSON API without proper CORS restrictions |
| CSRF-011 | Non-Cookie Auth (CSRF N/A) | INFO | Session uses `Authorization: Bearer` header exclusively — CSRF risk is inherently LOW (short-circuit) |

### 8.3 Request Flow Analysis Logic

```shell
For each SessionFlow:
  0. SHORT-CIRCUIT CHECK (JWT/Bearer Auth):
     - If ALL requests use Authorization: Bearer header
       AND no session cookies are set → flag CSRF-011,
       assign risk = LOW, skip ML pipeline for this flow.
  1. Identify authentication point (login request)
  2. Track session cookies from authentication
  3. For each subsequent exchange:
     a. Is it state-changing? (POST/PUT/DELETE/PATCH)
     b. Does it carry auth cookies? (needs CSRF protection)
     c. Check all CSRF-xxx rules
     d. Extract feature vector
     e. Run ML classifier
     f. Calculate risk score
  4. Cross-reference findings across the flow:
     - Does token change per request?
     - Are there endpoints with inconsistent protection?
     - Are GET requests doing writes while POST is protected?
```

### 8.4 Authentication Mechanism Detection

Modern SPAs often use JWT Bearer tokens stored in `localStorage` instead of session cookies. Since CSRF fundamentally exploits the browser's automatic cookie attachment, applications using **purely header-based auth** are inherently not vulnerable to CSRF.

The Flow Parser detects auth mechanism **early, before the ML pipeline**:

```python
# Common custom auth headers beyond just "Authorization: Bearer"
CUSTOM_AUTH_HEADERS = [
    'Authorization',   # Bearer tokens, Basic auth
    'X-API-Key',       # REST API key auth
    'X-Auth-Token',    # Custom token auth
    'Api-Key',         # Alternative API key header
    'X-Access-Token',  # Access token pattern
]

def detect_auth_mechanism(session_flow: SessionFlow) -> str:
    """Classify the authentication mechanism used in this session flow.
    
    This runs in Phase 1 (Flow Parsing). If the result is 'header_only',
    the system short-circuits: it yields a final AnalysisResult immediately
    and bypasses Phases 2 (Static Analysis) and 3 (ML) entirely.
    """
    has_session_cookies = any(
        'session' in k.lower() or 'sid' in k.lower() or 'auth' in k.lower()
        for exchange in session_flow.exchanges
        for k in exchange.request_cookies.keys()
    )
    has_header_auth = any(
        any(exchange.request_headers.get(h) for h in CUSTOM_AUTH_HEADERS)
        for exchange in session_flow.exchanges
    )
    
    if has_header_auth and not has_session_cookies:
        return 'header_only'     # CSRF not applicable → short-circuit
    elif has_session_cookies and not has_header_auth:
        return 'cookie'          # Classic CSRF risk → full analysis
    elif has_session_cookies and has_header_auth:
        return 'mixed'           # Hybrid auth → analyze cookie paths
    else:
        return 'none'            # No auth detected
```

**Short-circuit behavior** — When `auth_mechanism == 'header_only'`:

- The Flow Parser immediately yields a final `AnalysisResult` with:
  - Finding: **CSRF-011** (Info level)
  - Risk score: **5** (LOW)
  - Risk level: LOW
- **Phases 2 and 3 are completely bypassed** — no static analysis, no feature extraction, no ML inference
- Report message: *"This session uses header-based authentication exclusively (Bearer token / API key). CSRF risk is inherently low because the browser does not auto-attach these headers to cross-origin requests."*

> **⚠️ Design Note:** The JWT/API-key short-circuit logic lives **only** in the Flow Parser (Phase 1). It does NOT appear in `apply_heuristics()` (§9.6) to avoid a logical contradiction — if Phase 1 already short-circuited, Phase 3 never executes.

---

## 9. AI/ML Component

### 9.1 Approach: Heuristic ML (Moderate Level)

The ML component operates at a **moderate complexity level**, using classical ML algorithms with carefully engineered features rather than deep learning.

### 9.2 Training Data

| Source | Method | Expected Volume |
| --- | --- | --- |
| **Synthetic data** ⭐ | Auto-generated via `scripts/generate_synthetic_data.py` (built in Phase 1) | ~600 unique feature vectors |
| **OWASP Benchmark** | Known vulnerable/safe endpoints | ~400 samples |
| **DVWA / WebGoat** | Captured traffic + **data augmentation** (see note below) | ~200 unique feature vectors |
| **Real-world HAR files** | Manually labeled traffic captures | ~300 samples |
| **Total** | | **~1,500 samples** |

> [!WARNING] **Overfitting Prevention (DVWA/WebGoat):**
> DVWA and WebGoat have a limited number of distinct endpoints (e.g., ~5-10 unique forms). Capturing 200 raw requests to the same 3 endpoints would cause **data leakage** — the model would memorize URLs instead of learning CSRF patterns. To mitigate this, we apply **data augmentation**: programmatically mutating captured HAR files by randomizing parameter names, URL paths, header values, and token formats to produce 200 *unique feature vectors* from a small set of vulnerable endpoints. This ensures the model learns *structural patterns* (e.g., "POST without token") rather than *specific URLs* (e.g., "/dvwa/vulnerabilities/csrf").

---
> [!NOTE] **Review Note:**
> Synthetic data generation is prioritized in Phase 1 (not Phase 3) to ensure a training baseline is available early. This avoids the data collection bottleneck identified in peer review.

Each sample is labeled as:

- `0` = **Protected** (adequate CSRF protection)
- `1` = **Vulnerable** (missing/weak CSRF protection)

### 9.3 Feature Engineering

#### 9.3.1 Token Identification Strategy (Prerequisite)

Before extracting the `token_entropy` feature, the system must first **identify which parameter is the CSRF token**. This is a non-trivial prerequisite — if the wrong parameter is selected, the entropy calculation feeds garbage data to the ML model.

The token identification pipeline uses a three-tier strategy:

```python
CSRF_TOKEN_NAMES = [
    'csrf_token', 'csrfmiddlewaretoken', '_token', '_csrf',
    'authenticity_token', '__RequestVerificationToken',
    'xsrf_token', 'anti_forgery_token', 'csrf', 'xsrf',
]

def identify_csrf_token(form_params: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """Identify the CSRF token parameter from form data.
    
    Returns (param_name, param_value) or None if no token found.
    Uses a 3-tier identification strategy.
    """
    # Tier 1: Exact name match against known CSRF token names
    for name, value in form_params.items():
        if name.lower() in CSRF_TOKEN_NAMES:
            return (name, value)
    
    # Tier 2: Fuzzy name match (contains 'csrf', 'xsrf', 'token')
    for name, value in form_params.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in ['csrf', 'xsrf', 'forgery']):
            return (name, value)
    
    # Tier 3: High-entropy string detection in hidden fields
    # Look for values that are long (>16 chars) and high-entropy
    for name, value in form_params.items():
        if len(value) >= 16 and shannon_entropy(value) >= 3.5:
            return (name, value)  # Likely a cryptographic token
    
    return None  # No token found → has_csrf_token_in_form = False
```

If no token is identified, `token_entropy` is set to **0.0** and `has_csrf_token_in_form` is set to **False**.

#### 9.3.2 Feature Vector

The 14 features are extracted and preprocessed:

```python
features = [
    'has_csrf_token_in_form',      # bool → 0/1
    'has_csrf_token_in_header',    # bool → 0/1
    'has_samesite_cookie',         # categorical → one-hot encoded
    'has_origin_check',            # bool → 0/1
    'has_referer_check',           # bool → 0/1
    'http_method',                 # categorical → one-hot encoded
    'is_state_changing',           # bool → 0/1
    'content_type',                # categorical → one-hot encoded
    'requires_auth',               # bool → 0/1
    'token_entropy',               # float (normalized, 0.0 if no token found)
    'token_changes_per_request',   # bool → 0/1
    'response_sets_cookie',        # bool → 0/1
    'auth_mechanism',              # categorical → one-hot (cookie/header_only/mixed)
    'endpoint_sensitivity',        # float (0.0 - 1.0)
]
# Total: 14 features (13 original + auth_mechanism)
```

### 9.4 Model Selection

| Model | Reason for Consideration |
| --- | --- |
| **Random Forest** ⭐ | Good accuracy, interpretable, handles mixed features well |
| **Gradient Boosting (XGBoost)** | Higher accuracy potential, good with imbalanced data |
| **Decision Tree** | Baseline comparison, fully explainable |
| **Logistic Regression** | Baseline comparison, probability calibration |

**Primary model:** Random Forest (with XGBoost as secondary)

### 9.5 Model Training & Validation

```shell
Dataset Split:
├── Training Set:   70% (~1,050 samples)
├── Validation Set: 15% (~225 samples)
└── Test Set:       15% (~225 samples)

Evaluation Metrics:
├── Accuracy:    Target ≥ 80%
├── Precision:   Target ≥ 75% (minimize false positives)
├── Recall:      Target ≥ 85% (minimize false negatives — security critical)
├── F1-Score:    Target ≥ 80%
└── AUC-ROC:     Target ≥ 0.85
```

### 9.6 Heuristic Boost

Beyond pure ML classification, the system applies **heuristic rules** that boost/reduce the ML probability.

> **Note:** This function is only called for sessions that passed the Flow Parser's auth check (i.e., `auth_mechanism != 'header_only'`). The JWT/API-key short-circuit is handled exclusively in §8.4 and never reaches this stage.

```python
def apply_heuristics(ml_probability, static_findings, url, http_method):
    """Apply heuristic rules to adjust ML probability.
    
    PRECONDITION: This function is NEVER called for 'header_only' auth sessions.
    Those are short-circuited in the Flow Parser (§8.4) before reaching Phase 3.
    """
    score = ml_probability
    
    # Critical static findings override ML
    if has_finding("CSRF-004"):  # Static token
        score = max(score, 0.95)
    
    # Sensitive endpoint boost
    if endpoint_matches(url, "/admin", "/transfer", "/delete", "/password",
                        "/update", "/remove", "/add", "/settings"):
        score *= 1.2
    
    # GET with state-changing query params
    if http_method == 'GET' and has_action_params(url, ['action', 'op', 'do', 'cmd']):
        score *= 1.3
    
    # Multiple protections reduce risk
    protection_count = count_protections(static_findings)
    if protection_count >= 2:
        score *= 0.6  # Defense in depth
    
    return clamp(score, 0.0, 1.0)
```

---

## 10. Risk Scoring Model

### 10.1 Scoring Formula

The final risk score uses a **Base Score + Modifier** model to ensure the result always stays within the 0–100 range:

```shell
Step 1: Calculate Base Score (normalized to 0–100)
  Base Score = (W_ml × ML_Probability + W_static × Static_Normalized_Score) × 100

  Where:
    W_ml     = 0.50  (ML model confidence, float 0.0 - 1.0)
    W_static = 0.50  (Static analysis severity, normalized to 0.0 - 1.0)

  Static_Normalized_Score = sum(triggered_rule_severities) / max_possible_severity
    - Each rule severity mapped: CRITICAL=1.0, HIGH=0.75, MEDIUM=0.5, LOW=0.25, INFO=0.0
    - Divided by max possible severity (if all rules triggered)

Step 2: Apply Context Modifiers (flat integer adjustments)
  Final Score = Clamp(Base Score + Context_Modifier_Sum, 0, 100)
```

**Example calculations:**

```shell
# Example 1: Vulnerable endpoint (no token, no SameSite)
  ML_Probability = 0.85
  Static_Normalized = 0.70  (CSRF-001 HIGH + CSRF-005 MEDIUM triggered)
  Base = (0.50 × 0.85 + 0.50 × 0.70) × 100 = 77.5
  Context = +10 (modifies user data)
  Final = Clamp(77.5 + 10, 0, 100) = 87 → 🔴 CRITICAL

# Example 2: Well-protected endpoint
  ML_Probability = 0.15
  Static_Normalized = 0.10  (only CSRF-009 LOW triggered)
  Base = (0.50 × 0.15 + 0.50 × 0.10) × 100 = 12.5
  Context = -5 (uses HTTPS)
  Final = Clamp(12.5 + (-5), 0, 100) = 7 → 🟢 LOW
```

### 10.2 Score Interpretation

| Score Range | Risk Level | Color | Action |
| --- | --- | --- | --- |
| **0 – 20** | 🟢 LOW | Green | Acceptable risk, monitor only |
| **21 – 40** | 🟡 MEDIUM | Yellow | Review recommended, may need adjustment |
| **41 – 70** | 🟠 HIGH | Orange | Remediation required before production |
| **71 – 100** | 🔴 CRITICAL | Red | Immediate action required, exploitable |

### 10.3 Context Modifiers

Context modifiers are **flat integer adjustments** applied after the base score calculation. The `Clamp(0, 100)` ensures the final score never exceeds 0–100.

| Factor | Modifier (points) |
| --- | --- |
| Endpoint handles financial data | +15 |
| Endpoint modifies user data | +10 |
| Endpoint is admin-only | +10 |
| Application uses HTTPS | -5 |
| Multiple CSRF protections present | -15 |
| GET-based state change | +20 |

---

## 11. Implementation Plan

### 11.1 Module Structure

```shell
csrf-shield-ai/
├── README.md
├── requirements.txt
├── setup.py
├── config/
│   ├── rules.yaml              # Static analysis rules configuration
│   └── settings.yaml           # Application settings
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point
│   ├── input/
│   │   ├── __init__.py
│   │   ├── har_parser.py       # HAR file parser
│   │   ├── proxy_listener.py   # mitmproxy integration
│   │   ├── models.py           # Data models (HttpExchange, SessionFlow)
│   │   └── auth_detector.py    # JWT/Cookie auth mechanism detection (§8.4)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── flow_analyzer.py    # Session/flow reconstruction
│   │   ├── static_analyzer.py  # Rule-based CSRF checks
│   │   ├── feature_extractor.py # ML feature extraction
│   │   └── rules/
│   │       ├── __init__.py
│   │       ├── csrf_001.py     # Individual rule implementations
│   │       ├── csrf_002.py
│   │       └── ...
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── trainer.py          # Model training pipeline
│   │   ├── predictor.py        # Inference engine
│   │   ├── heuristics.py       # Heuristic boost logic
│   │   └── models/
│   │       └── csrf_rf_model.pkl  # Serialized model
│   ├── scoring/
│   │   ├── __init__.py
│   │   └── risk_scorer.py      # Risk score calculation
│   ├── output/
│   │   ├── __init__.py
│   │   ├── report_generator.py # Report generation (JSON, HTML)
│   │   └── templates/
│   │       └── report.html     # HTML report template
│   └── web/
│       ├── __init__.py
│       ├── app.py              # Flask web dashboard
│       ├── static/
│       │   ├── css/
│       │   └── js/
│       └── templates/
│           └── dashboard.html
├── data/
│   ├── training/               # Training datasets
│   │   ├── vulnerable/         # Labeled vulnerable samples
│   │   └── protected/          # Labeled safe samples
│   ├── sample_har/             # Sample HAR files for testing
│   └── synthetic/              # Synthetically generated data
├── scripts/
│   └── generate_synthetic_data.py  # Synthetic training data generator (Phase 1)
├── tests/
│   ├── __init__.py
│   ├── test_har_parser.py
│   ├── test_static_analyzer.py
│   ├── test_feature_extractor.py
│   ├── test_ml_predictor.py
│   ├── test_risk_scorer.py
│   └── test_integration.py
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_analysis.ipynb
│   └── 03_model_evaluation.ipynb
├── docs/
│   ├── proposal/
│   │   └── PROPOSAL.md             # This document
│   ├── defense/
│   │   └── DEFENSE_NOTES.md        # Defense preparation Q&A
│   ├── guides/
│   │   ├── USER_GUIDE.md           # Usage instructions (Phase 6)
│   │   └── API_REFERENCE.md        # API documentation (Phase 6)
│   ├── reports/                    # Task/milestone completion reports
│   │   └── README.md
│   └── reviews/
│       └── other_review.md         # Peer review feedback
├── spec/
│   ├── Design.md               # Architecture & design decisions
│   ├── Requirements.md         # Functional & non-functional requirements
│   └── Tasks.md                # Task breakdown & assignments
└── .agent/instructions
    ├── Roadmap.instructions.md                      # Development roadmap & milestones
    ├── coding_standards.instructions.md             # Code style, naming, conventions
    ├── git_workflow.instructions.md                 # Git branching & commit conventions
    ├── testing_strategy.instructions.md             # Testing approach & coverage targets
    ├── task_completion_workflow.instructions.md     # Mandatory task completion workflow
    └── documentation_standards.instructions.md     # Where & how to organize docs
```

### 11.2 Development Phases

#### Phase 1: Foundation (Core Infrastructure)

- Set up project structure and development environment
- Implement data models (`HttpExchange`, `SessionFlow`, `Finding`)
- Build HAR file parser
- Build flow parser / session reconstructor
- **Build synthetic data generator** (`scripts/generate_synthetic_data.py`) — generates labeled HTTP flows (both vulnerable and protected) for ML training baseline *(moved here per review feedback to avoid data collection bottleneck in Phase 3)*
- Implement auth mechanism detector (`auth_detector.py`) for JWT vs. cookie classification

#### Phase 2: Static Analysis Engine

- Implement all 10 CSRF detection rules
- Build rule engine with configurable severity
- Implement feature extraction pipeline
- Create sample HAR files for testing

#### Phase 3: ML Pipeline

- Leverage synthetic data generated in Phase 1 as training baseline
- Supplement with manually labeled HAR captures from DVWA/WebGoat
- Implement feature engineering pipeline (14 features including `auth_mechanism`)
- Train and evaluate ML models
- Implement heuristic boost logic (including JWT short-circuit)
- Serialize best model

#### Phase 4: Risk Scoring & Reporting

- Implement risk scoring formula
- Build report generator (JSON + HTML)
- Create CLI interface with argument parsing
- Implement exportable reports

#### Phase 5: Web Dashboard & Polish

- Build Flask-based web dashboard
- Implement interactive results viewer
- Add visualization charts (risk distribution, endpoint map)
- End-to-end testing and documentation

---

## 12. Technology Stack

| Layer | Technology | Version | Purpose |
| --- | --- | --- | --- |
| **Language** | Python | 3.10+ | Primary development language |
| **ML Framework** | scikit-learn | 1.3+ | ML model training and inference |
| **ML Boost** | XGBoost | 2.0+ | Gradient boosting classifier |
| **Data Processing** | pandas, numpy | Latest | Feature processing and data manipulation |
| **Web Framework** | Flask | 3.0+ | Web dashboard backend |
| **Frontend** | HTML/CSS/JS | — | Dashboard UI (vanilla, no framework) |
| **Proxy** | mitmproxy | 10.0+ | Live traffic capture |
| **Reporting** | Jinja2 | 3.1+ | HTML report templating |
| **Testing** | pytest | 7.0+ | Unit and integration testing |
| **Serialization** | joblib | 1.3+ | Model serialization |
| **CLI** | argparse / click | Built-in / 8.0+ | Command-line interface |
| **Data Visualization** | Chart.js | 4.0+ | Dashboard charts |

---

## 13. Testing Strategy

### 13.1 Test Categories

| Category | Scope | Method |
| --- | --- | --- |
| **Unit Tests** | Individual functions and classes | pytest |
| **Integration Tests** | Component interaction (parser → analyzer → ML) | pytest |
| **ML Validation** | Model accuracy on held-out test set | scikit-learn metrics |
| **Functional Tests** | End-to-end tool execution | CLI + sample HAR files |
| **Benchmark Tests** | Against known vulnerable apps (DVWA, WebGoat) | Manual verification |

### 13.2 Test Targets

| Metric | Target |
| --- | --- |
| Unit test coverage | ≥ 80% |
| ML accuracy | ≥ 80% |
| ML recall (vulnerability detection) | ≥ 85% |
| False positive rate | ≤ 20% |
| E2E test pass rate | 100% |

### 13.3 Test Datasets

1. **DVWA (Damn Vulnerable Web Application)** — Known CSRF-vulnerable endpoints
2. **WebGoat** — OWASP training application with CSRF exercises
3. **Juice Shop** — Modern vulnerable application
4. **Custom Flask/Django apps** — Purpose-built test applications with and without CSRF protection

---

## 14. Expected Deliverables

| # | Deliverable | Format |
| --- | --- | --- |
| D1 | **Source code** — Complete tool source code | Python package (GitHub repository) |
| D2 | **Trained ML model** — Serialized classifier | `.pkl` file |
| D3 | **Documentation** — User guide + API reference | Markdown (.md) |
| D4 | **Sample reports** — Generated risk scoring reports | JSON + HTML |
| D5 | **Test suite** — Comprehensive tests | pytest |
| D6 | **Presentation** — Project presentation slides | PDF/PPTX |
| D7 | **Demo** — Live demonstration video | Video recording |
| D8 | **Report** — Final project report | PDF document |

---

## 15. Timeline

### 15.1 Project Schedule (Estimated: 10 weeks)

Each `██` block = 1 week. Total = 20 blocks across 10 weeks.

```shell
          W1  W2  W3  W4  W5  W6  W7  W8  W9  W10
Phase 1   ██──██──░░──░░──░░──░░──░░──░░──░░──░░   Foundation
Phase 2   ░░──░░──██──██──░░──░░──░░──░░──░░──░░   Static Analysis
Phase 3   ░░──░░──░░──░░──██──██──░░──░░──░░──░░   ML Pipeline
Phase 4   ░░──░░──░░──░░──░░──░░──██──██──░░──░░   Risk Scoring & Reports
Phase 5   ░░──░░──░░──░░──░░──░░──░░──░░──██──░░   Web Dashboard
Polish    ░░──░░──░░──░░──░░──░░──░░──░░──░░──██   Testing & Documentation
```

### 15.2 Milestones

| Week | Milestone | Key Deliverable |
| --- | --- | --- |
| Week 2 | ✅ M1: Core infrastructure ready | HAR parser, data models, flow analyzer |
| Week 4 | ✅ M2: Static analyzer complete | All 10 rules implemented + tested |
| Week 6 | ✅ M3: ML pipeline trained | Model with ≥ 80% accuracy |
| Week 8 | ✅ M4: Risk scoring functional | End-to-end CLI tool working |
| Week 9 | ✅ M5: Web dashboard live | Interactive results visualization |
| Week 10 | ✅ M6: Project complete | Full documentation + presentation |

---

## 16. Risk Assessment

### 16.1 Project Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Insufficient training data | Medium | High | Use synthetic data generation + data augmentation |
| ML model accuracy below target | Medium | Medium | Fall back to stronger static analysis weighting in scoring formula |
| Complex HAR format variations | Low | Medium | Support major browsers (Chrome, Firefox) format first |
| mitmproxy integration issues | Medium | Low | Make proxy optional, HAR files as primary input |
| Scope creep | Medium | High | Strict adherence to in-scope boundaries |
| Time overrun | Medium | Medium | Prioritize core features, dashboard is optional bonus |

### 16.2 Risk Contingency

If ML accuracy falls short:

1. **Increase static analysis weight** in scoring formula (W_static = 0.60, W_ml = 0.20)
2. **Add more heuristic rules** to compensate
3. **Use ensemble approach** — combine multiple simpler models

---

## 17. References

1. OWASP. (2021). *Cross-Site Request Forgery Prevention Cheat Sheet*. <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
2. OWASP. (2021). *OWASP Top 10*. <https://owasp.org/www-project-top-ten/>
3. Barth, A., Jackson, C., & Mitchell, J. (2008). *Robust defenses for cross-site request forgery*. ACM CCS.
4. HAR 1.2 Specification. *HTTP Archive format*. <http://www.softwareishard.com/blog/har-12-spec/>
5. scikit-learn. (2023). *Random Forest Classifier Documentation*. <https://scikit-learn.org/stable/modules/ensemble.html>
6. mitmproxy. (2024). *mitmproxy Documentation*. <https://docs.mitmproxy.org/>
7. Zeller, W., & Felten, E. W. (2008). *Cross-Site Request Forgeries: Exploitation and Prevention*. Princeton University.
8. OWASP. (2023). *OWASP ZAP*. <https://www.zaproxy.org/>
9. XGBoost. (2024). *XGBoost Documentation*. <https://xgboost.readthedocs.io/>
10. Jovanovic, N., Kruegel, C., & Kirda, E. (2006). *Preventing cross-site request forgery attacks*. IEEE SecureComm.

---

> **Document Status:** DRAFT v1.2 (Revised)
> **Last Updated:** February 24, 2026
> **Author:** Group 9 — IAW Course
> **Supervisor:** Ho Hai
>
> **Revision History:**
>
> | Version | Date | Changes |
> | --- | --- | --- |
> | v1.0 | 2026-02-24 | Initial proposal |
> | v1.1 | 2026-02-24 | Addressed peer review: (1) Moved synthetic data generation to Phase 1, (2) Added JWT/Bearer auth short-circuit detection (CSRF-011), (3) Enhanced endpoint sensitivity with explicit URL/query patterns for GET state-change detection |
> | v1.2 | 2026-02-24 | Critical fixes: (1) Resolved JWT short-circuit logic contradiction between §8.4 and §9.6, (2) Fixed broken scoring formula — replaced with Base Score + Modifier model, (3) Added data augmentation for DVWA/WebGoat overfitting prevention, (4) Added Token Identification Strategy prerequisite (§9.3.1), (5) Corrected Gantt chart alignment, (6) Expanded auth detection to cover API keys and custom headers |
