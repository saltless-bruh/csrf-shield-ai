# Presentation Slides — CSRF Shield AI

> **Course:** IAW (Web Application Security)
> **Project:** AI-Powered CSRF Risk Scoring Tool
> **Group:** 9 — FPT University
> **Date:** March 2026

---

## Slide 1 — Title

**CSRF Shield AI**
_An Intelligent CSRF Risk Scoring Tool Based on Request Flow Analysis_

- Course: IAW — Web Application Security
- Group 9, FPT University
- March 2026

---

## Slide 2 — The CSRF Problem

**Cross-Site Request Forgery** exploits the browser's trust in session cookies.

```
Victim logs into BankApp → gets session cookie
Victim visits attacker's page → hidden form auto-submits
→ POST /transfer?amount=10000 with victim's cookies
→ Money transferred without victim's knowledge
```

**Why it matters:**

- OWASP Top 10 web vulnerability
- Common mitigations (tokens, SameSite) are often incorrectly implemented
- Existing scanners: rule-based only, high false positives, no flow analysis

---

## Slide 3 — Project Objectives

| #   | Objective                       | Result                     |
| --- | ------------------------------- | -------------------------- |
| O1  | Parse HAR traffic captures      | ✅ Full HAR 1.2 support    |
| O2  | Detect CSRF protection failures | ✅ 11 detection rules      |
| O3  | ML classification ≥80% accuracy | ✅ 100% (Random Forest)    |
| O4  | Quantified risk scoring (0–100) | ✅ Base + Modifier formula |
| O5  | Usable CLI + TUI tool           | ✅ Both operational        |

---

## Slide 4 — System Architecture

**Two-Process Architecture:**

```
┌──────────────────┐     NDJSON/stdin/stdout     ┌──────────────────┐
│   Go TUI (gocui) │ ◄──────────────────────────► │  Python Backend  │
│   Interactive UI  │                              │  Analysis Engine │
└──────────────────┘                              └──────────────────┘
```

**Pipeline:**

```
HAR File → Parse → Flows → Auth Check
  ├─ [header_only] → Score=5 (skip ML)
  └─ [cookie] → Static Analysis → ML → Risk Score → Report
```

---

## Slide 5 — Static Analysis: 11 CSRF Rules

| Rule     | Name                         | Severity |
| -------- | ---------------------------- | -------- |
| CSRF-001 | Missing CSRF Token in Form   | HIGH     |
| CSRF-002 | Missing CSRF Token in Header | MEDIUM   |
| CSRF-003 | Predictable CSRF Token       | HIGH     |
| CSRF-004 | Static (non-rotating) Token  | CRITICAL |
| CSRF-005 | Missing SameSite Cookie      | MEDIUM   |
| CSRF-006 | SameSite=None Without Secure | HIGH     |
| CSRF-007 | No Origin Validation         | MEDIUM   |
| CSRF-008 | GET with Side Effects        | HIGH     |
| CSRF-009 | Missing Referer Validation   | LOW      |
| CSRF-010 | JSON Without CORS            | MEDIUM   |
| CSRF-011 | Non-Cookie Auth (N/A)        | INFO     |

---

## Slide 6 — ML Component

**14 Features extracted per request:**

- Token presence (form + header), SameSite cookie, Origin/Referer checks
- HTTP method, content type, auth mechanism, endpoint sensitivity
- Token entropy, token rotation, state-changing heuristic

**Why Random Forest (not Deep Learning)?**

| Criteria        | Random Forest         | Deep Learning |
| --------------- | --------------------- | ------------- |
| Min samples     | ~500                  | ~10,000+      |
| Explainability  | ✅ Feature importance | ❌ Black box  |
| Inference speed | ~1ms (CPU)            | ~50ms (GPU)   |
| Complexity      | Moderate ✅           | Advanced      |

---

## Slide 7 — Training Results

| Metric    | Target | Random Forest  | XGBoost        |
| --------- | ------ | -------------- | -------------- |
| Accuracy  | ≥80%   | **100.00%** ✅ | **99.56%** ✅  |
| Precision | ≥75%   | **100.00%** ✅ | **99.13%** ✅  |
| Recall    | ≥85%   | **100.00%** ✅ | **100.00%** ✅ |
| F1-Score  | ≥80%   | **100.00%** ✅ | **99.56%** ✅  |
| AUC-ROC   | ≥85%   | **100.00%** ✅ | **100.00%** ✅ |

**All FR-304 targets exceeded.** Model serialized as `.pkl` (~2MB, CPU-only).

---

## Slide 8 — Risk Scoring Formula

```
Base = (0.50 × ML_Probability + 0.50 × Static_Score) × 100
Final = Clamp(Base + Context_Modifiers, 0, 100)
```

| Score  | Level       | Action           |
| ------ | ----------- | ---------------- |
| 0–20   | 🟢 LOW      | Monitor          |
| 21–40  | 🟡 MEDIUM   | Review           |
| 41–70  | 🟠 HIGH     | Remediate        |
| 71–100 | 🔴 CRITICAL | Immediate action |

**Example:** No token + no SameSite + user data endpoint → Score **87** (CRITICAL)

---

## Slide 9 — Interactive TUI

**Go-based Terminal UI with Vim-style navigation:**

- **Three panels:** Sessions | Exchanges | Analysis Engine
- **Keyboard driven:** h/j/k/l, Tab, Enter
- **Modals:** Help (F1), Export (e), Raw View (r), Quit (q)
- **Real-time progress:** Per-session, per-step analysis updates

```bash
./csrf-shield-tui --input traffic.har
```

---

## Slide 10 — CLI Demo

```bash
# Analyze a HAR file
csrf-shield analyze -i traffic.har -o report.json

# Output:
#   🔍 Analyzing: traffic.har
#   📊 3 findings (CSRF-001, CSRF-005, CSRF-009)
#   📈 Risk score: 87 — 🔴 CRITICAL
#   💾 Report saved to: report.json

# Train ML model
csrf-shield train --data data/training/ --output models/
```

---

## Slide 11 — Testing & Quality

| Metric        | Value                  |
| ------------- | ---------------------- |
| Total tests   | **438**                |
| Code coverage | **90%** (target: ≥80%) |
| Python LOC    | 5,481 (36 files)       |
| Go LOC        | 2,236 (12 files)       |
| Test LOC      | 5,915 (20 files)       |

**Categories:** Unit (~350), Integration (~60), End-to-end (~20), Edge cases (~8)

---

## Slide 12 — Comparison with Existing Tools

| Feature       | CSRF Shield AI     | OWASP ZAP        | Burp Suite       |
| ------------- | ------------------ | ---------------- | ---------------- |
| Analysis type | Passive (HAR)      | Active + Passive | Active + Passive |
| CSRF-specific | ✅ Dedicated       | ❌ General       | ❌ General       |
| ML-powered    | ✅ RF + heuristics | ❌ Rules only    | ❌ Rules only    |
| Risk score    | ✅ 0–100           | ❌ Alert levels  | ❌ Severity      |
| Flow analysis | ✅ Full sessions   | ⚠️ Limited       | ⚠️ Limited       |
| Cost          | Free               | Free             | ~$449/year       |

---

## Slide 13 — Limitations & Future Work

**Current Limitations:**

- No GraphQL mutation detection (all requests to `/graphql`)
- No active scanning / exploit verification
- Training data ~1,500 samples (may not generalize to all frameworks)

**Future Enhancements:**

- GraphQL body inspection (detect mutations vs. queries)
- Real-time proxy mode (mitmproxy integration)
- CI/CD GitHub Actions integration
- Confidence calibration (Platt scaling)

---

## Slide 14 — Key Differentiators

### Three core strengths:

1. **"We analyze flows, not just requests"**
   Session-level analysis catches what endpoint-level scanners miss

2. **"We quantify risk, not just detect it"**
   0–100 scoring enables prioritization

3. **"We combine ML + static, not either/or"**
   Heuristic boost prevents ML blind spots; ML catches patterns rules miss

---

## Slide 15 — Q&A

**Thank you!**

🔗 GitHub: `github.com/your-org/csrf-shield-ai`
📖 User Guide: `docs/guides/USER_GUIDE.md`
📋 API Reference: `docs/guides/API_REFERENCE.md`

_Questions?_

---

> **Deliverable:** D6 — Presentation Slides
> **Requirement Reference:** PROPOSAL.md §14
