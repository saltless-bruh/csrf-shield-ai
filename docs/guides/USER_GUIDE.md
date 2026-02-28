# 📖 User Guide — CSRF Shield AI

> **Status:** Final
> **Last Updated:** February 28, 2026

---

## 1. Installation

### 1.1 Prerequisites

- **Python:** 3.10 or higher
- **Go:** 1.21 or higher (optional, for TUI)
- **Git**

### 1.2 Setup Instructions

Clone the repository and install the backend:

```bash
git clone https://github.com/your-org/csrf-shield-ai.git
cd csrf-shield-ai
pip install -e .
```

To build the Go TUI (Terminal User Interface):

```bash
cd cmd/tui
go build -o ../../csrf-shield-tui main.go
cd ../..
```

---

## 2. Quick Start

CSRF Shield AI offers both an interactive Terminal UI (TUI) and a non-interactive CLI.

### 2.1 Interactive Analysis (TUI)

The TUI is the recommended way to explore your HAR files interactively.

```bash
./csrf-shield-tui --input traffic.har
```

### 2.2 CLI Analysis

Ideal for CI/CD pipelines or batch processing.

```bash
csrf-shield analyze --input traffic.har --output report.json --format json
```

---

## 3. Analyzing a HAR File

### 3.1 Exporting a HAR File

1. Open your browser's Developer Tools (F12).
2. Go to the **Network** tab.
3. Check **Preserve log**.
4. Perform the actions you want to analyze (e.g., login, form submission, API calls).
5. Right-click any request and select **Save all as HAR with content**.

### 3.2 Running the Analysis

Pass the exported HAR file to CSRF Shield AI:

```bash
csrf-shield analyze -i traffic.har -o my_report.json
```

The tool will automatically:

1. Parse the requests and responses.
2. Group them into session flows based on cookies/tokens.
3. Detect the authentication mechanism.
4. Run 11 static analysis rules.
5. Apply the ML model to predict the CSRF risk.
6. Generate a final risk score.

---

## 4. Understanding Risk Scores

Risk scores are quantified on a scale from 0 to 100:

- **0–20 (LOW):** Fully protected against CSRF (e.g., valid Anti-CSRF tokens + SameSite=Lax/Strict cookies).
- **21–40 (MEDIUM):** Partially protected or relies on weaker defenses (e.g., missing tokens but relying heavily on Referer validation).
- **41–70 (HIGH):** Vulnerable to typical CSRF attacks. High likelihood of side-effects.
- **71–100 (CRITICAL):** Extremely vulnerable with definitive state-changing operations and zero protection.

_Note: Flows using `Authorization: Bearer` or `X-API-Key` headers exclusively are short-circuited to a LOW risk score (5), as CSRF relies on ambient credentials (cookies)._

---

## 5. Reading Reports

The standard JSON report contains the following schema:

- `flows`: A list of analyzed session flows.
  - `session_id`: Unique identifier for the session.
  - `short_circuited`: Boolean indicating if the flow bypassed full analysis due to its auth mechanism.
  - `auth_mechanism`: Detected auth method (`cookie`, `header_only`, `mixed`, etc.).
  - `risk_score`: Final calculated risk score (0-100).
  - `risk_level`: Severity tier.
  - `findings`: List of triggered static analysis rules and their details.
- `total_flows`: Number of flows analyzed.

---

## 6. Configuration Options

Configuration is managed via `config/settings.yaml` and `config/rules.yaml`. You can customize:

- `token_entropy_threshold`: Minimum entropy for a token to be considered secure.
- `static_weights`: How much the static analysis affects the final risk score vs. the ML model.
- `rule_definitions`: Toggle specific rules on or off based on your application's architecture.

---

## 7. Web Dashboard Usage

_(Optional feature)_
If the Web Dashboard is enabled, you can start it via:

```bash
python -m src.dashboard.app
```

Then visit `http://localhost:5000` in your browser. You can upload HAR files directly to the web interface and view visualizations of the risk distribution.

---

## 8. Troubleshooting

- **"File not found" Error:** Ensure the path to your `.har` file is correct and accessible.
- **Empty Report / No Flows Detected:** Make sure your HAR file contains requests with authentication credentials (cookies or headers). Anonymous traffic is ignored.
- **TUI Not Rendering Correctly:** Ensure your terminal supports a minimum size of 100x24 characters.

---

## 9. FAQ

**Q: Does the tool execute the requests in the HAR file?**  
A: No, CSRF Shield AI performs _offline, static analysis_ on the captured traffic. It does not replay requests or modify your application state.

**Q: Why did my API receive a low score even though it lacks CSRF tokens?**  
A: If the API solely uses `Authorization: Bearer` headers and no cookies, it is inherently immune to CSRF, thus receiving a low risk score automatically.
