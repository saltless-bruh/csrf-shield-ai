# 🛡️ Defense Preparation Notes — CSRF Shield AI

> **Purpose:** Prepared answers for edge cases and tough questions likely to arise during the project defense with Supervisor Ho Hai.
> **Status:** Living document — update as new edge cases are discovered.
> **Last Updated:** February 24, 2026

---

## Table of Contents

1. [GraphQL Endpoints](#1-graphql-endpoints)
2. [multipart/form-data Parsing](#2-multipartform-data-parsing)
3. [Why Not Deep Learning?](#3-why-not-deep-learning)
4. [False Positive Management](#4-false-positive-management)
5. [Token Extraction Accuracy](#5-token-extraction-accuracy)
6. [Ethical Considerations](#6-ethical-considerations)
7. [Scalability & Performance](#7-scalability--performance)
8. [Comparison with Commercial Tools](#8-comparison-with-commercial-tools)

---

## 1. GraphQL Endpoints

### 1.1 Likely Question

> *"How does your tool handle GraphQL applications where all requests go to a single `/graphql` endpoint as POST?"*

### 1.2 The Challenge

GraphQL breaks several core assumptions in our Flow Parser:

| Our Assumption | GraphQL Reality |
| --- | --- |
| URL patterns reveal intent (`/delete`, `/admin`) | All traffic goes to **one** URL: `/graphql` |
| HTTP method indicates state change (POST = write) | **Everything** is POST, even read-only queries |
| URL path identifies the resource | The **JSON body** contains the actual operation |

Example — two requests that look identical at the HTTP level but have completely different security needs:

```json
// State-changing (NEEDS CSRF protection):
{"query": "mutation { updateProfile(name: \"attacker\") { id } }"}

// Read-only (does NOT need CSRF protection):
{"query": "query { user(id: 1) { name email } }"}
```

Both are `POST /graphql` with `Content-Type: application/json`. Our current static analyzer would treat them identically.

### 1.3 Prepared Answer

> *"We recognize GraphQL as a growing architectural pattern. Our system's modular design supports this through the Flow Parser's extensibility. To handle GraphQL, we would add a body-inspection module that:*
>
> 1. *Detects `/graphql` or `/gql` URL endpoints*
> 2. *Parses the JSON body to extract the `query` field*
> 3. *Classifies the operation as `mutation` (state-changing) or `query` (read-only)*
> 4. *Sets the `is_state_changing` feature accordingly*
>
> *For the current project scope, we focus on REST APIs and traditional form-based web applications, which represent the vast majority of web applications encountered in IAW coursework and real-world legacy systems. GraphQL support would be a natural Phase 2 enhancement."*

### 1.4 Implementation Sketch

```python
import json
import re

def is_graphql_mutation(exchange: HttpExchange) -> bool:
    """Check if a request to a GraphQL endpoint is a state-changing mutation."""
    # Only applies to GraphQL endpoints
    if not re.search(r'/graphql|/gql', exchange.request_url, re.IGNORECASE):
        return False

    try:
        body = json.loads(exchange.request_body)
        query = body.get('query', '')
        # GraphQL mutations start with 'mutation' keyword
        return query.strip().startswith('mutation')
    except (json.JSONDecodeError, AttributeError):
        return False
```

### 1.5 Risk Level

🟢 **LOW** — GraphQL is niche in the IAW course context. Our tool's primary value is with REST/form-based apps (Django, Flask, Laravel, Spring), which dominate real-world web applications and course exercises.

---

## 2. multipart/form-data Parsing

### 2.1 Likely Question

> *"What happens when a form has file uploads? Can your tool still find CSRF tokens in multipart request bodies?"*

### 2.2 The Challenge

File upload forms use `Content-Type: multipart/form-data`, which structures the body with MIME boundaries instead of simple `key=value` pairs:

```shell
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="csrf_token"

a1b2c3d4e5f6
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="avatar"
Content-Type: image/png

<binary data — possibly truncated in HAR file>
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**Three complications:**

1. **HAR truncation** — Browsers/proxies often truncate large binary bodies, potentially cutting off the CSRF token if it appears after the file field
2. **Boundary parsing** — CSRF token is buried in MIME boundaries, not simple `key=value`
3. **Encoding** — Binary content may be base64-encoded, making raw text search unreliable

### 2.3 Prepared Answer

> *"Our HAR parser handles multipart bodies through a two-layer strategy:*
>
> 1. **Primary:** *We first check the HAR's `postData.params` array, which the HAR format provides as pre-parsed key-value pairs — this works regardless of body encoding or truncation.*
> 2. **Fallback:** *If `params` is unavailable, we parse the raw body using Python's standard `email.parser` module to extract text fields from MIME boundaries, ignoring binary file content.*
> 3. **Inconclusive handling:** *If the body is truncated and we cannot determine whether a token exists, we flag it as `token_inconclusive` rather than `token_missing` to avoid false positives. This is reflected as a reduced confidence score in the ML feature vector rather than a hard binary judgment."*

### 2.4 Implementation Sketch

```python
from email.parser import BytesParser
from email.policy import default as default_policy
import re

def extract_form_params(exchange: HttpExchange) -> dict:
    """Extract form parameters, handling multipart/form-data correctly."""
    content_type = exchange.request_content_type

    if 'multipart/form-data' in content_type:
        return _parse_multipart(exchange.request_body, content_type)
    elif 'application/x-www-form-urlencoded' in content_type:
        return _parse_urlencoded(exchange.request_body)
    elif 'application/json' in content_type:
        return _parse_json(exchange.request_body)
    return {}

def _parse_multipart(body: str, content_type: str) -> dict:
    """Parse multipart body, extracting only text fields."""
    params = {}
    # Extract boundary from Content-Type header
    boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
    if not boundary_match or not body:
        return params  # Inconclusive — body may be truncated

    boundary = boundary_match.group(1)
    parts = body.split(f'--{boundary}')

    for part in parts:
        # Only extract text fields (skip binary file uploads)
        if 'Content-Type:' in part and 'text/' not in part:
            continue
        name_match = re.search(r'name="([^"]+)"', part)
        if name_match:
            name = name_match.group(1)
            # Value is after the double newline
            value_parts = part.split('\r\n\r\n', 1)
            if len(value_parts) == 2:
                params[name] = value_parts[1].strip()
    return params
```

### 2.5 HAR `postData.params` Strategy

The HAR 1.2 specification includes a `params` array that pre-parses form fields:

```json
{
  "postData": {
    "mimeType": "multipart/form-data; boundary=----WebKitFormBoundary...",
    "params": [
      {"name": "csrf_token", "value": "a1b2c3d4e5f6"},
      {"name": "avatar", "fileName": "photo.png", "contentType": "image/png"}
    ],
    "text": "<raw body — possibly truncated>"
  }
}
```

By checking `postData.params` **first**, we bypass all multipart parsing complexity. This is the most reliable approach.

### 2.6 Risk Level

🟡 **MEDIUM** — File uploads are common in real-world apps. This must be handled correctly in `har_parser.py` during Phase 1 implementation, otherwise every file upload form would trigger false positives on `CSRF-001 (Missing CSRF Token in Form)`.

---

## 3. Why Not Deep Learning?

### 3.1 Likely Question

> *"Why did you choose Random Forest over a neural network or deep learning model?"*

### 3.2 Prepared Answer

> *"We chose classical ML (Random Forest / XGBoost) for four specific reasons:*
>
> 1. **Data constraint:** *Deep learning typically requires 10,000+ samples for stable training. Our dataset is ~1,500 samples — ideal for classical ML, insufficient for deep learning.*
> 2. **Explainability:** *Security tools must explain WHY something is risky. Random Forest provides feature importance scores (e.g., 'this was flagged because has_csrf_token_in_form=False contributed 35% to the prediction'). Neural networks are black boxes.*
> 3. **Course requirement:** *The project specifies 'moderate level ML.' Random Forest with heuristic boosting fits this precisely — sophisticated enough to demonstrate ML competence, practical enough for a course project.*
> 4. **Performance:** *Random Forest inference is ~1ms per sample. A trained model can analyze thousands of endpoints in seconds with no GPU required."*

### 3.3 Supporting Data

| Criteria | Random Forest | Deep Learning (LSTM/Transformer) |
| --- | --- | --- |
| Min training samples | ~500-1,000 | ~10,000+ |
| Explainability | ✅ Feature importance | ❌ Black box |
| Inference speed | ~1ms/sample (CPU) | ~50ms/sample (GPU needed) |
| Training time | Minutes | Hours/days |
| Complexity level | Moderate ✅ | Advanced ❌ |

---

## 4. False Positive Management

### 4.1 Likely Question

> *"How do you handle false positives? What if the tool flags a safe endpoint as vulnerable?"*

### 4.2 Prepared Answer

> *"We manage false positives through three mechanisms:*
>
> 1. **Risk scoring (not binary):** *Instead of 'vulnerable: yes/no', our 0–100 score lets users set their own threshold. An endpoint at score 25 (MEDIUM) can be triaged differently than one at 85 (CRITICAL).*
> 2. **Multi-signal validation:** *We don't rely on a single check. The scoring formula weights ML (40%), static analysis (40%), and context (20%). A false positive would need to fool ALL three signals simultaneously.*
> 3. **Defense-in-depth discount:** *If an endpoint has multiple CSRF protections (e.g., token + SameSite cookie), the heuristic boost applies a 0.6x multiplier, reducing false positive risk on well-protected endpoints.*
> 4. **`token_inconclusive` state:** *When we can't definitively determine if a token is present (e.g., truncated multipart body), we use an inconclusive state rather than assuming 'missing', avoiding false flags."*

---

## 5. Token Extraction Accuracy

### 5.1 Likely Question

> *"How do you identify what IS a CSRF token? Not every hidden form field is a CSRF token."*

### 5.2 Prepared Answer

> *"We use a multi-heuristic approach to identify CSRF tokens:*
>
> 1. **Name matching:** *Check field names against common patterns: `csrf_token`, `_token`, `csrfmiddlewaretoken` (Django), `_csrf` (Spring), `authenticity_token` (Rails), `__RequestVerificationToken` (.NET)*
> 2. **Entropy analysis:** *Legitimate CSRF tokens have high entropy (randomness). We calculate Shannon entropy — a value ≥ 3.5 bits/char suggests a cryptographic token, while < 3.0 suggests a predictable value.*
> 3. **Token rotation:** *We check if the value changes between requests in the same session. True CSRF tokens typically rotate per-request or per-session.*
> 4. **Header patterns:** *For header-based tokens, we look for `X-CSRF-Token`, `X-XSRF-Token`, `X-Requested-With` headers."*

### 5.3 Common CSRF Token Field Names (by framework)

| Framework | Token Field Name |
| --- | --- |
| Django | `csrfmiddlewaretoken` |
| Laravel | `_token` |
| Spring | `_csrf` |
| Rails | `authenticity_token` |
| ASP.NET | `__RequestVerificationToken` |
| Express (csurf) | `_csrf` |
| Generic | `csrf_token`, `csrf`, `token`, `xsrf_token` |

---

## 6. Ethical Considerations

### 6.1 Likely Question

> *"Could this tool be misused to find and exploit CSRF vulnerabilities in production applications?"*

### 6.2 Prepared Answer

> *"Our tool is strictly a defensive analysis tool — it has several design constraints that prevent misuse:*
>
> 1. **Passive analysis only:** *The tool analyzes HAR files and captured traffic. It does NOT send any requests to target applications — it cannot exploit anything.*
> 2. **No payload generation:** *Unlike penetration testing tools, we do not generate attack payloads or proof-of-concept exploits.*
> 3. **Input requirement:** *The user must provide their own traffic captures (HAR files), meaning they already have legitimate access to the application being analyzed.*
> 4. **Educational output:** *Risk reports include remediation recommendations, focusing on how to FIX vulnerabilities rather than exploit them.*
>
> *This is analogous to a security linter (like Bandit for Python) — it finds potential issues in code/traffic the developer already owns."*

---

## 7. Scalability & Performance

### 7.1 Likely Question

> *"How does your tool perform with large HAR files or high-traffic applications?"*

### 7.2 Prepared Answer

> *"Our pipeline is designed for efficiency:*
>
> | Stage | Complexity | Bottleneck | Mitigation |
> | --- | --- | --- | --- |
> | HAR Parsing | O(n) where n = entries | File I/O | Streaming JSON parser |
> | Static Analysis | O(n × r) where r = rules | CPU | Rules are independent — parallelizable |
> | Feature Extraction | O(n × f) where f = features | CPU | Vectorized with numpy |
> | ML Inference | O(n × log(trees)) | CPU | Random Forest is fast (~1ms/sample) |
>
> *For a typical web application HAR file (~500-2,000 entries), the entire pipeline completes in under 10 seconds on a standard laptop. The ML model file is ~2MB — no GPU required.*
>
> *The JWT short-circuit (§8.4) also improves performance by skipping the entire ML pipeline for Bearer-token-authenticated sessions."*

---

## 8. Comparison with Commercial Tools

### 8.1 Likely Question

> *"How does your tool compare to OWASP ZAP or Burp Suite?"*

### 8.2 Prepared Answer

> *"Our tool occupies a different niche:*
>
> | Feature | CSRF Shield AI | OWASP ZAP | Burp Suite Pro |
> | --- | --- | --- | --- |
> | Analysis type | Passive (HAR-based) | Active + Passive | Active + Passive |
> | CSRF-specific | ✅ Dedicated | ❌ General scanner | ❌ General scanner |
> | ML-powered | ✅ Random Forest + heuristics | ❌ Rule-based only | ❌ Rule-based only |
> | Risk quantification | ✅ Score 0–100 | ❌ Alert levels only | ❌ Severity levels |
> | Flow analysis | ✅ Full session flows | ⚠️ Limited | ⚠️ Limited |
> | Cost | Free (open source) | Free | ~$449/year |
> | Scope | CSRF only | All web vulns | All web vulns |
>
> *We don't replace ZAP or Burp — we complement them. Our focused approach provides deeper CSRF analysis than what general-purpose scanners offer, while general scanners cover breadth across all vulnerability types."*

---

## Quick Reference — Defense Cheat Sheet

If pressed for time, remember these **three core differentiators**:

1. **"We analyze flows, not just requests"** — Session-level analysis catches what endpoint-level scanners miss
2. **"We quantify risk, not just detect it"** — 0–100 scoring enables prioritization
3. **"We combine ML + static, not either/or"** — Heuristic boost prevents ML blind spots, ML catches patterns rules miss

---

> **Tip:** Practice answering each question in **under 60 seconds**. If the supervisor wants more detail, they'll ask follow-ups — don't over-explain unprompted.
