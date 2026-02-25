# [TUI] Addendum: Terminal User Interface (TUI) Design Specification

> **Project:** CSRF Shield AI
>
> **Reference:** PROPOSAL.md v1.2, Design.md v1.0
>
> **Document Status:** Extension Specification (v2.3 — Revised)

---

## 1. Design Philosophy & Inspiration

The primary operational interface for CSRF Shield AI will be a **Terminal User Interface (TUI)**. While the Web Dashboard (Phase 5) remains an option for presenting final HTML reports to non-technical stakeholders, the core tool is designed for security engineers who live in the terminal.

The UI architecture is heavily inspired by **`lazygit`** (by Jesse Duffield). It adheres to the following core principles:

1. **Panel-Based Context:** The screen is divided into fixed panes. Selecting an item in a left-hand pane instantly updates the detail views in the right-hand panes. This creates a "drill-down" workflow: Sessions > Exchanges > Findings.

2. **Keyboard-Driven (Vim-style):** 100% mouse-free operation using `h/j/k/l`, `Tab`, and single-key action bindings. The keyboard was chosen because the target user — a pentester or developer — already operates in a terminal workflow (shell > editor > tools > shell), so a mouse-based interaction would break their flow.

3. **Discoverability:** Every available action is always visible. The bottom status bar dynamically updates to show context-specific keys, and a `?` key opens a full command palette. This eliminates the "hidden command" problem that plagues many TUI tools.

4. **Color-Coded Feedback:** Terminal colors are strictly tied to the Risk Scoring Model (PROPOSAL.md §10.2). Green, Yellow, Orange, Red are never used for decoration — they always represent risk severity. This creates instant visual parsing of threat levels.

5. **Information Density:** Every pixel of screen real estate serves a purpose. The user should be able to glance at the TUI and immediately understand: how many sessions were loaded, which have been analyzed, what the most critical finding is, and whether the ML engine is idle or working.

---

## 2. Technical Stack

To mirror the exact performance, responsiveness, and architecture of `lazygit`, the TUI component will adopt Jesse Duffield's core stack:

- **Language:** **Go (Golang)**. Go's compiled nature and lightweight concurrency (goroutines/channels) ensure the UI remains instantly responsive and never blocks, even when parsing massive HAR files or waiting on ML inference. Go also compiles to a single static binary, making distribution trivial.

- **UI Framework:** **`gocui`** (specifically utilizing `jesseduffield/gocui`, the custom fork built for lazygit). This library allows for overlapping views, custom keybindings, and raw terminal manipulation.

- **State Management:** Reactive state handling via Go channels, decoupling the UI rendering loop from the heavy lifting of the analysis engine. When the Python backend sends a result, a goroutine receives it and pushes a UI update to the main thread via channel — the UI thread never blocks.

- **Integration Strategy (Go + Python):** The Go TUI acts as a lightning-fast frontend client. It executes the Python analysis engine as a background sub-process, communicating via **newline-delimited JSON (NDJSON)** over stdin/stdout. This follows the same line-delimited pattern used by [JSON Lines](https://jsonlines.org/) and tools like `ndjson-cli` — simple, debuggable, and language-agnostic.

---

## 3. Data Flow: Backend to TUI

Before describing the panels, it is essential to understand what data the TUI will display and where it comes from. Every piece of text on screen maps to a specific Python dataclass field:

### 3.1 Data Source Mapping

```shell
Python Backend                          TUI Panel
--------------------------------------------------------------
parse_har_file()
  -> List[HttpExchange]                -> Panel 2: Exchanges list

reconstruct_flows()
  -> List[SessionFlow]                 -> Panel 1: Sessions list
    .session_id                       ->   Session label
    .exchanges                        ->   Request count badge
    .auth_mechanism                   ->   Auth type badge

detect_auth_mechanism()
  -> AuthMechanism enum                -> Panel 1: Auth badge color
    HEADER_ONLY -> short-circuit       ->   "(H) Header" label (green)
    COOKIE -> full analysis            ->   "(C) Cookie" label
    MIXED -> full analysis             ->   "(M) Mixed" label
    NONE -> full analysis              ->   "(?) None" label

static_analyzer (Phase 2)
  -> List[Finding]                     -> Panel 3: Findings section
    .rule_id                          ->   [CSRF-001] badge
    .severity                         ->   Color: HIGH=orange, CRITICAL=red
    .evidence                         ->   > evidence line beneath finding

feature_extractor (Phase 2)
  -> Dict[str, Any]                    -> Panel 3: Feature vector section

predictor (Phase 3)
  -> float (ml_probability)            -> Panel 3: ML Confidence bar
    + risk_scorer
  -> int (risk_score)                  -> Panel 3: RISK SCORE header
  -> str (risk_level)                  -> Panel 3: Color of score header

AnalysisResult
  .recommendations                    -> Panel 3: Recommendations section
```

### 3.2 IPC Protocol (Go <-> Python)

The Go TUI spawns `python src/ipc_server.py` as a child process. Communication uses **NDJSON** (one JSON object per line) over stdin/stdout.

#### Serialization Rules

Python Enum types (`Severity`, `RiskLevel`, `AuthMechanism`) are serialized to their `.value` strings. `datetime` objects are serialized as ISO 8601 strings. `frozen=True` dataclasses are serialized to plain dicts via a custom `to_dict()` helper. The Go side maps these to equivalent Go structs with `json` struct tags.

**Enum serialization values** (Go must match against these exact strings):

| Python Enum | Enum Name | Serialized `.value` |
| --- | --- | --- |
| `Severity` | `CRITICAL` | `"CRITICAL"` |
| `Severity` | `HIGH` | `"HIGH"` |
| `Severity` | `MEDIUM` | `"MEDIUM"` |
| `Severity` | `LOW` | `"LOW"` |
| `Severity` | `INFO` | `"INFO"` |
| `RiskLevel` | `CRITICAL` | `"CRITICAL"` |
| `RiskLevel` | `HIGH` | `"HIGH"` |
| `RiskLevel` | `MEDIUM` | `"MEDIUM"` |
| `RiskLevel` | `LOW` | `"LOW"` |
| `AuthMechanism` | `COOKIE` | `"cookie"` |
| `AuthMechanism` | `HEADER_ONLY` | `"header_only"` |
| `AuthMechanism` | `MIXED` | `"mixed"` |
| `AuthMechanism` | `NONE` | `"none"` |

> **Caution:** `AuthMechanism` values are **lowercase** (e.g., `"header_only"`), while `Severity` and `RiskLevel` values are **UPPERCASE** (e.g., `"CRITICAL"`). This matches the Python definitions in `models.py`. Go struct tags must use these exact strings.

**`Finding.exchange` serialization:** The `Finding` dataclass contains an `exchange: HttpExchange` field, which is a full request/response pair. To avoid bloating IPC payloads (each finding would duplicate the entire exchange), the IPC server serializes `Finding.exchange` as a **compact reference** instead of the full object:

```json
{"exchange": {"method": "POST", "url": "/api/transfer", "status": 200}}
```

The Go side can match this reference back to the full exchange data it already holds from `list_flows`.

#### Methods

**Core lifecycle:**

```json
{"id": 1, "method": "ping", "params": {}}
{"id": 2, "method": "load_har", "params": {"path": "/path/to/file.har"}}
{"id": 3, "method": "list_flows", "params": {}}
{"id": 4, "method": "analyze_flow", "params": {"session_id": "abc123"}}
{"id": 5, "method": "analyze_all", "params": {}}
{"id": 6, "method": "get_results", "params": {"session_id": "abc123"}}
{"id": 7, "method": "cancel", "params": {}}
{"id": 8, "method": "export_report", "params": {"format": "json", "scope": "selected", "session_id": "abc123", "path": "report.json"}}
```

| Method | Purpose | When Called |
| --- | --- | --- |
| `ping` | Health check — confirms Python process is alive | On startup, and periodically (every 5s) |
| `load_har` | Parse HAR file, reconstruct flows, detect auth | On TUI launch with `--input` |
| `list_flows` | Return current list of SessionFlow summaries | After initial load only. Filtering is client-side in Go. |
| `analyze_flow` | Run full pipeline on one session. Returns `List[AnalysisResult]` (one per state-changing exchange) plus a `summary` object with aggregated risk score. | User presses `a` |
| `analyze_all` | Run full pipeline on all sessions sequentially | User presses `A` |
| `get_results` | Retrieve ALL cached `AnalysisResult` objects for a session. The Go side filters by exchange for Mode B display — no server round-trip needed. | User switches selection in Panel 1 (to populate Panel 3 from cache) |
| `cancel` | Abort the current `analyze_all` batch. Cancellation is cooperative: it takes effect between sessions, not mid-analysis. The session currently being analyzed will finish. | User presses `Esc` during `analyze_all` |
| `export_report` | Generate report file. When `scope` = `"selected"`, the `session_id` param identifies which session. When `scope` = `"all"`, `session_id` is omitted. | User confirms in Export dialog |

**Response (Python -> Go via stdout):**

```json
{"id": 1, "result": {"status": "ok", "version": "1.0"}}
{"id": 2, "result": {"flows": [...], "total_flows": 3, "total_exchanges": 18}}
{"id": 4, "result": {"session_id": "abc123", "summary": {"risk_score": 87, "risk_level": "CRITICAL", "ml_probability_max": 0.85, "static_score_max": 0.70}, "results": [{"endpoint": "/api/transfer", "http_method": "POST", "risk_score": 92, "risk_level": "CRITICAL", "findings": [...], "ml_probability": 0.85, "static_score": 0.75, "feature_vector": {...}, "recommendations": [...]}, {"endpoint": "/api/upload", "http_method": "POST", "risk_score": 45, "risk_level": "HIGH", "findings": [...], "ml_probability": 0.52, "static_score": 0.40, "feature_vector": {...}, "recommendations": [...]}]}}
{"id": 5, "progress": {"status": "analyzing", "session_id": "abc123", "session_index": 1, "session_total": 3, "step": "static_analysis", "step_current": 2, "step_total": 5, "percent": 40}}
{"id": 6, "result": {"session_id": "abc123", "status": "not_analyzed"}}
{"id": 7, "result": {"status": "cancelled", "completed": 2, "total": 5}}
{"id": 8, "result": {"status": "ok", "path": "report.json", "size_bytes": 4521}}
```

> **Key design decision:** `analyze_flow` returns a `results` array containing one `AnalysisResult` per state-changing exchange, plus a `summary` object with session-level aggregates. Each per-exchange result includes a `static_score` field (the normalized static analysis severity, 0.0-1.0, as defined in PROPOSAL.md §10.1). The summary contains `ml_probability_max` and `static_score_max` — the max values across all exchange results — so Mode A can display them without re-computation. Non-state-changing exchanges produce no `AnalysisResult`. The Go side caches these results locally; switching sessions calls `get_results` to retrieve from cache without re-running analysis.
>
> **Required backend change:** The current `AnalysisResult` dataclass in `models.py` does not have a `static_score` field. The IPC server (`ipc_server.py`) must compute it during serialization using the formula from PROPOSAL.md §10.1: `static_score = sum(triggered_rule_severities) / max_possible_severity`. This is computed on-the-fly and does NOT require modifying the frozen dataclass.
>
> **`get_results` for never-analyzed sessions:** If `get_results` is called for a session that has not been analyzed, the response includes `"status": "not_analyzed"` with no `summary` or `results` fields (see id=6 example above). The Go side uses this to show the "Press `<a>` to analyze" placeholder in Panel 3.

**Error (Python -> Go via stdout):**

```json
{"id": 2, "error": {"code": "FILE_NOT_FOUND", "message": "File does not exist: /bad/path.har"}}
{"id": 2, "error": {"code": "PARSE_ERROR", "message": "Invalid JSON in HAR file at line 42"}}
{"id": 4, "error": {"code": "IMPORT_ERROR", "message": "Missing dependency: scikit-learn"}}
```

**Progress events** (sent during `analyze_flow` and `analyze_all`):

```json
{"id": 5, "progress": {"status": "analyzing", "session_id": "abc123", "session_index": 2, "session_total": 3, "step": "ml_inference", "step_current": 3, "step_total": 5, "percent": 80}}
```

Progress events have **two levels of granularity**:

| Field | Meaning | Example | Status Bar Display |
| --- | --- | --- | --- |
| `session_index` / `session_total` | Batch progress (which session, out of how many) | `2 / 3` | `[ML: Analyzing 2/3...]` |
| `step_current` / `step_total` | Pipeline progress within the current session | `3 / 5` | (internal use, for progress bar in Panel 3) |
| `percent` | Overall completion % across both levels | `80` | Progress bar fill |

For `analyze_flow` (single session), `session_index` = 1 and `session_total` = 1.

**Pipeline steps** (the 5 stages that `step_current`/`step_total` refer to):

| Step | `step` value | Description |
| --- | --- | --- |
| 1 | `static_analysis` | Run all CSRF rules (CSRF-001 through CSRF-011) against each exchange |
| 2 | `feature_extraction` | Extract the 14-feature vector per state-changing exchange |
| 3 | `ml_inference` | Run the trained classifier to get `ml_probability` |
| 4 | `risk_scoring` | Combine static + ML scores using the Base Score + Modifier formula |
| 5 | `recommendations` | Generate remediation suggestions based on findings |

The TUI listens on a goroutine and pushes updates to the UI thread via channel, so the UI never freezes. If the Python process exits unexpectedly (exit code != 0), the Go side transitions to the ERROR state (see §8).

#### stderr Handling

The IPC protocol uses stdin/stdout exclusively. Python's **stderr** is captured separately by the Go process via `cmd.StderrPipe()`. stderr output is:

1. **Written to a log file** at `~/.csrf-shield/backend.log` (rotated, max 1MB) for debugging.
2. **Stored in memory** (last 50 lines) for display in the ERROR state screen if the backend crashes.
3. **Never mixed with stdout** — any Python code that writes to stderr (warnings, tracebacks) does not corrupt the NDJSON stream.

---

## 4. UI Layout & Architecture

The TUI is divided into three primary sections: **Context (Left Column)**, **Detail (Right Column)**, and **Global Controls (Bottom Bar)**.

- The **left column** contains two stacked panels: Sessions (top) and Exchanges (bottom).
- The **right column** is a single tall panel showing the Analysis Engine output.
- The **bottom bar** spans the full width and shows keybinding hints.

The **currently active panel is highlighted with a bright double-line border** (`══`), while inactive panels use a dim single-line border (`──`). This is how the user always knows which panel has keyboard focus.

**Minimum terminal size:** 100 columns x 24 rows. If the terminal is smaller, the TUI shows a centered message: `"Terminal too small. Need 100x24, got WxH. Please resize."` and re-checks on every resize event.

### 4.1 Screen Mockup --- Loading State

When the TUI first launches, it shows a loading indicator while spawning Python and parsing the HAR file:

```shell
+----------------------------------------------------------------------+
|                                                                      |
|                         CSRF Shield AI v1.0                          |
|                                                                      |
|              Loading: traffic.har                                    |
|              [========>                    ] 35%                     |
|              Spawning analysis backend...                            |
|                                                                      |
|              Press <q> to abort.                                     |
|                                                                      |
+----------------------------------------------------------------------+
```

If the Python backend fails to start (e.g., Python not installed, missing dependency), the loading screen transitions to an error:

```shell
+----------------------------------------------------------------------+
|                                                                      |
|                         CSRF Shield AI v1.0                          |
|                                                                      |
|              [ERROR] Backend failed to start                         |
|                                                                      |
|              Python process exited with code 1:                      |
|              ModuleNotFoundError: No module named 'scikit-learn'     |
|                                                                      |
|              Press <q> to quit.                                      |
|                                                                      |
+----------------------------------------------------------------------+
```

### 4.2 Screen Mockup --- Initial State (HAR Loaded, No Analysis Yet)

When the user first loads a HAR file, sessions and exchanges are visible, but the analysis panel is empty:

```shell
+= Sessions ========================================++-- Analysis Engine -------------------------------+
|                                                   ||                                                  |
| > abc123  api.target.com   (C) Cookie [12]        ||         Not analyzed yet.                        |
|   qwe890  auth.target.com  (H) Header  [4]        ||                                                  |
|   zxc456  api.target.com   (C) Cookie  [2]        ||    Select a session and press <a> to             |
|                                                   ||    run CSRF analysis.                            |
|                                                   ||                                                  |
|                                                   ||                                                  |
+===================================================+|                                                  |
+-- Exchanges --------------------------------------+|                                                  |
|                                                   ||                                                  |
|  GET    /dashboard              --- 200           ||                                                  |
|  GET    /api/user               --- 200           ||                                                  |
|  POST   /api/transfer    [Form] --- 200           ||                                                  |
|  POST   /api/upload      [JSON] --- 201           ||                                                  |
|  PUT    /api/settings    [JSON] --- 200           ||                                                  |
|  DELETE /api/remove      [JSON] --- 200           ||                                                  |
|                                                   ||                                                  |
+---------------------------------------------------++--------------------------------------------------+
 <a> analyze  <A> analyze all  <f> filter  <x> remove  <e> export  <q> quit  <?> help     [ML: Idle]
```

### 4.3 Screen Mockup --- After Analysis (Session Summary View)

After pressing `a` to analyze a session, the right panel shows the **session-level summary** (aggregated across all exchanges). This view is active when **Panel 1 (Sessions)** has focus:

```shell
+== Sessions =======================================++-- Analysis Engine -------------------------------+
|                                                   ||                                                  |
| > abc123  api.target.com   (C) Cookie [12]  [!!]  ||  RISK SCORE: 87 / 100        [!!] CRITICAL       |
|   qwe890  auth.target.com  (H) Header  [4]  [*]   ||  ML Confidence: 85%  |  Static: 70%              |
|   zxc456  api.target.com   (C) Cookie  [2]  --    ||                                                  |
|                                                   || --- Static Findings (2) -------------------------|
|                                                   ||                                                  |
|                                                   ||  [!] [CSRF-001] Missing Form Token          HIGH |
+===================================================+|      > POST /api/transfer                        |
+-- Exchanges --------------------------------------+|      > param 'amount', 'account_to'              |
|                                                   ||                                                  |
|  GET    /dashboard              --- 200           ||  [~] [CSRF-005] Missing SameSite             MED |
|  GET    /api/user               --- 200           ||      > cookie 'session_id'                       |
|  POST   /api/transfer    [Form] --- 200  [!]      ||                                                  |
|  POST   /api/upload      [JSON] --- 201  [~]      || --- Recommendations -----------------------------|
|  PUT    /api/settings    [JSON] --- 200  [~]      ||                                                  |
|  DELETE /api/remove      [JSON] --- 200  [!]      ||  1. Add a CSRF token to POST /api/transfer       |
|                                                   ||  2. Set SameSite=Strict on session cookie        |
+---------------------------------------------------++--------------------------------------------------+
 <a> analyze  <A> analyze all  <f> filter  <x> remove  <e> export  <q> quit  <?> help  [ML: Idle]
```

### 4.4 Screen Mockup --- After Analysis (Per-Exchange Detail View)

When the user presses `Tab` to move focus to **Panel 2 (Exchanges)** and selects a specific exchange, Panel 3 switches to show the **per-exchange detail** — the findings and feature vector for that single request:

```shell
+-- Sessions ---------------------------------------++-- Analysis: POST /api/transfer --------------------+
|                                                   ||                                                    |
| > abc123  api.target.com   (C) Cookie [12]  [!!]  ||  RISK SCORE: 92 / 100        [!!] CRITICAL         |
|   qwe890  auth.target.com  (H) Header  [4]  [*]   ||  ML Confidence: 89%  |  Static: 75%                |
|   zxc456  api.target.com   (C) Cookie  [2]  --    ||                                                    |
|                                                   || --- Static Findings (1) -------------------------  |
|                                                   ||                                                    |
|                                                   ||  [!] [CSRF-001] Missing Form Token          HIGH   |
+---------------------------------------------------+|      > param 'amount', 'account_to'                |
+== Exchanges ======================================+|                                                    |
|                                                   || --- ML Feature Vector (14) ----------------------  |
|  GET    /dashboard              --- 200           ||                                                    |
|  GET    /api/user               --- 200           ||  has_csrf_token_in_form  : false                   |
|> POST   /api/transfer    [Form] --- 200  [!]      ||  has_csrf_token_in_header: false                   |
|  POST   /api/upload      [JSON] --- 201  [~]      ||  has_samesite_cookie     : none                    |
|  PUT    /api/settings    [JSON] --- 200  [~]      ||  has_origin_check        : false                   |
|  DELETE /api/remove      [JSON] --- 200  [!]      ||  has_referer_check       : false                   |
|                                                   ||  http_method             : POST                    |
+===================================================+|  is_state_changing       : true                    |
                                                     |  content_type            : form-urlencoded         |
                                                     |  requires_auth           : true                    |
                                                     |  token_entropy           : 0.00                    |
                                                     |  token_changes_per_req   : false                   |
                                                     |  response_sets_cookie    : true                    |
                                                     |  auth_mechanism          : cookie                  |
                                                     |  endpoint_sensitivity    : 0.95                    |
                                                     |                                                    |
                                                     +----------------------------------------------------+
 <Enter> view raw  <c> copy cURL  <f> filter  <e> export  <q> quit  <?> help              [ML: Idle]
```

> **Design note:** Panel 3 shows a **session summary** (aggregated findings, no feature vector) when Panel 1 is focused. It switches to **per-exchange detail** (that exchange's findings + full 14-feature vector) when Panel 2 is focused. This mirrors lazygit's pattern: selecting a commit shows its summary; selecting a file within that commit shows the diff.

### 4.5 Screen Mockup --- Short-Circuited Session (Header-Only Auth)

When a `HEADER_ONLY` session is selected (either loaded or after pressing `a`), the analysis panel shows the short-circuit result immediately:

```shell
+== Sessions =======================================++-- Analysis Engine --------------------------------+
|                                                   ||                                                   |
|   abc123  api.target.com   (C) Cookie [12]  [!!]  ||  RISK SCORE: 5 / 100         [*] LOW              |
| > qwe890  auth.target.com  (H) Header  [4]  [*]   ||  >> SHORT-CIRCUITED (Header-Only Auth)            |
|   zxc456  api.target.com   (C) Cookie  [2]  --    ||                                                   |
|                                                   || --- Finding ------------------------------------- |
|                                                   ||                                                   |
|                                                   ||  [*] [CSRF-011] Non-Cookie Auth             INFO  |
+===================================================+|      > Authorization: Bearer eyJhbG...            |
+-- Exchanges --------------------------------------+|                                                   |
|                                                   ||  This session uses header-based auth              |
|  GET  /api/me           [None]  --- 200           ||  exclusively. CSRF is not applicable              |
|  GET  /api/settings     [None]  --- 200           ||  because browsers do not auto-attach              |
|  POST /api/preferences  [JSON]  --- 200           ||  these headers to cross-origin requests.          |
|  PUT  /api/profile      [JSON]  --- 200           ||                                                   |
|                                                   || --- ML Feature Vector --------------------------- |
|                                                   ||                                                   |
|                                                   ||  (Skipped -- pipeline short-circuited)            |
+---------------------------------------------------+|                                                   |
                                                     | --- Recommendations ----------------------------- |
                                                     |                                                   |
                                                     |  No action needed -- CSRF N/A.                    |
                                                     |                                                   |
                                                     +---------------------------------------------------+
 <a> analyze  <f> filter  <Enter> view raw  <c> copy cURL  <e> export  <q> quit  <?> help  [ML: Idle]
```

---

## 5. Panel Specifications

### 5.1 Panel 1: Sessions (Top Left)

**Purpose:** Provide a high-level overview of all loaded session flows. This is the "entry point" panel — the user starts here and drills down.

**Data source:** `List[SessionFlow]` from `reconstruct_flows()` + `update_flow_auth()`.

**Each row displays:**

| Element | Source | Example |
| --- | --- | --- |
| Selection indicator | UI state | `>` (selected) or blank |
| Session ID | `SessionFlow.session_id` (truncated to 7 chars) | `abc123` |
| Target host | Extracted from first exchange URL | `api.target.com` |
| Auth badge | `SessionFlow.auth_mechanism` | `(C) Cookie`, `(H) Header`, `(M) Mixed`, `(?) None` |
| Request count | `len(SessionFlow.exchanges)` | `[12]` |
| Risk indicator | `summary.risk_level` (after analysis) | `[!!]` `[!]` `[~]` `[*]` or `--` (not analyzed) |

**Risk indicator rule:** Once a session has been analyzed, it **always** shows a risk dot based on `summary.risk_level` — even if the session has zero findings (in which case the risk score is near 0 and the dot is `[*]` LOW). The `--` indicator is **only** shown for sessions that have never been analyzed. This ensures the user can always distinguish "analyzed and safe" from "not yet analyzed".

**Why this design:** The pentester's first question is "what sessions did I capture?" and "which ones are risky?" This panel answers both at a glance. The auth badge immediately tells them which sessions will be short-circuited (`(H) Header`) vs. fully analyzed (`(C) Cookie`), and the risk indicator after analysis lets them sort by threat priority.

**Behavior when active:**

- `j`/`k` or Up/Down moves the selection cursor
- Changing selection **immediately updates Panel 2** (exchanges for the selected session) and **Panel 3** (session-level analysis summary, if available)
- The bottom status bar updates to show session-specific actions

**Empty state:** If the HAR file contains zero `SessionFlow` objects (e.g., an empty or malformed file), the panel shows: `"No sessions found. Check your HAR file."`

### 5.2 Panel 2: Exchanges (Bottom Left)

**Purpose:** Show all HTTP exchanges within the currently selected session, with enough context to identify interesting requests without opening a detail view.

**Data source:** `SessionFlow.exchanges` (the selected session from Panel 1).

**Each row displays:**

| Element | Source | Example |
| --- | --- | --- |
| HTTP method | `HttpExchange.request_method` | `POST` |
| URL path | Parsed from `HttpExchange.request_url` | `/api/transfer` |
| Body type | Derived from `HttpExchange.request_content_type` | `[Form]`, `[JSON]`, `[None]` |
| Response status | `HttpExchange.response_status` | `200` |
| Risk dot | Highest severity of any `Finding` where `finding.exchange == this exchange` | `[!]` (has HIGH finding) |

**Risk dot derivation:** After analysis, each exchange row shows the risk indicator of the *most severe* finding that references it (via `Finding.exchange`). If an exchange has both a `MEDIUM` and a `HIGH` finding, only `[!]` (HIGH) is shown. Exchanges with no findings show no dot. Exchanges that were not analyzed (e.g., GETs with no state-changing behavior) show `--`.

**Why this design:** The pentester needs to quickly identify which specific requests within a session are interesting. The body type badge (`[Form]`, `[JSON]`, `[None]`) is critical because CSRF exploitability differs by content type — form-urlencoded is trivially exploitable, JSON requires CORS misconfiguration, and GET requests with no body may indicate state-changing GETs (CSRF-008). The `[Text]` badge is also security-relevant: `text/plain` content type bypasses CORS preflight checks, making cross-origin form submissions possible without triggering an OPTIONS request.

**Body type derivation logic:**

| `request_content_type` | Badge |
| --- | --- |
| Contains `form-urlencoded` | `[Form]` |
| Contains `multipart` | `[Multi]` |
| Contains `json` | `[JSON]` |
| Contains `text/plain` | `[Text]` |
| Empty / None (GET requests) | `[None]` |

**Behavior when active:**

- `j`/`k` or Up/Down scrolls through exchanges
- Selecting an exchange **updates Panel 3** to show **per-exchange detail** (that exchange's findings + full 14-feature vector)
- The bottom status bar shows exchange-specific actions

**Scrolling:** If a session has more exchanges than fit on screen, the list scrolls with the selected item always visible (centered when possible). A scroll indicator appears on the right edge: `[3/47]` showing position.

**Empty state:** If the selected session has zero exchanges (shouldn't happen, but defensively), show: `"No exchanges in this session."`

### 5.3 Panel 3: Analysis Engine (Right Column)

**Purpose:** Show the analysis output. This panel has **two display modes** depending on which left-side panel currently has focus.

#### Mode A: Session Summary (when Panel 1 is focused)

Shows aggregated results across the entire session:

- **Risk Score Header** *(pinned)* — The highest risk score across all exchanges, with risk level badge. Sourced from `summary.risk_score` and `summary.risk_level`.
- **Score Breakdown** *(pinned)* — ML confidence and static analysis percentages. Sourced from `summary.ml_probability_max` (displayed as %, e.g., 0.85 → "85%") and `summary.static_score_max` (displayed as %, e.g., 0.70 → "70%").
- **Static Findings** *(scrollable)* — All unique findings across all exchanges, grouped, with counts
- **Recommendations** *(scrollable)* — Aggregated remediation steps (deduplicated)

The Risk Score Header and Score Breakdown are **pinned** at the top of the panel and never scroll. Findings and Recommendations scroll beneath them via `j`/`k`.

Feature vector is **not shown** in this mode because there are multiple vectors (one per exchange) and showing an arbitrary one would be misleading.

#### Mode B: Per-Exchange Detail (when Panel 2 is focused)

Shows results for the single selected exchange:

- **Risk Score Header** *(pinned)* — That exchange's individual `risk_score` and `risk_level`
- **Score Breakdown** *(pinned)* — `ml_probability` (as %) and `static_score` (as %) for that exchange
- **Static Findings** *(scrollable)* — Only findings triggered by this specific exchange
- **ML Feature Vector** *(scrollable)* — All 14 features for this exchange (see table below)
- **Recommendations** *(scrollable)* — Remediation steps for this specific exchange

As in Mode A, the header is pinned. Findings, Feature Vector, and Recommendations scroll together beneath.

**Feature vector display (all 14 features from PROPOSAL.md §9.3.2):**

| Feature | Display Format | Example |
| --- | --- | --- |
| `has_csrf_token_in_form` | bool | `false` |
| `has_csrf_token_in_header` | bool | `false` |
| `has_samesite_cookie` | category | `none` / `lax` / `strict` |
| `has_origin_check` | bool | `false` |
| `has_referer_check` | bool | `false` |
| `http_method` | string | `POST` |
| `is_state_changing` | bool | `true` |
| `content_type` | string | `form-urlencoded` |
| `requires_auth` | bool | `true` |
| `token_entropy` | float (2dp) | `0.00` |
| `token_changes_per_request` | bool | `false` |
| `response_sets_cookie` | bool | `true` |
| `auth_mechanism` | category | `cookie` |
| `endpoint_sensitivity` | float (2dp) | `0.95` |

> **Why two modes:** A session may contain 50 exchanges. Showing a single aggregated feature vector would be meaningless — features are per-exchange. Showing all 50 vectors would overflow the panel. The lazygit pattern (commit summary vs. file diff) solves this naturally: the summary gives the big picture, the detail gives the specifics.

**Data source mapping:**

| TUI Section | Mode A Source (Session Summary) | Mode B Source (Per-Exchange) |
| --- | --- | --- |
| Risk Score Header | `summary.risk_score`, `summary.risk_level` | `results[i].risk_score`, `results[i].risk_level` |
| ML Confidence | `summary.ml_probability_max` | `results[i].ml_probability` |
| Static Score | `summary.static_score_max` | `results[i].static_score` |
| Static Findings | All `results[*].findings[]` (deduplicated) | `results[i].findings[]` |
| Feature Vector | *(not shown)* | `results[i].feature_vector` |
| Recommendations | All `results[*].recommendations[]` (deduplicated) | `results[i].recommendations[]` |

**Color mapping** (strictly follows PROPOSAL.md §10.2):

| Score Range | risk_level | TUI Color | Terminal Code |
| --- | --- | --- | --- |
| 0--20 | LOW | Bright Green | `\033[1;32m` |
| 21--40 | MEDIUM | Bright Yellow | `\033[1;33m` |
| 41--70 | HIGH | Dark Orange (256-color) | `\033[38;5;208m` |
| 71--100 | CRITICAL | Bright Red | `\033[1;31m` |

**Special states:**

- **Not analyzed yet:** Shows placeholder text "Select a session and press `<a>` to analyze"
- **Short-circuited:** Shows `>> SHORT-CIRCUITED` banner, CSRF-011 finding, and "pipeline skipped" indicator
- **Analysis in progress:** Shows animated spinner with step label (`[ML: Analyzing... static_analysis 45%]`)

### 5.4 Bottom Status Bar (Full Width)

**Purpose:** Eliminate guesswork about available actions. Dynamically shows keybindings relevant to the currently active panel.

**Layout:**

```shell
[context-specific keys]                                              [engine status]
```

**Examples by active panel:**

| Active Panel | Bar Content |
| --- | --- |
| Panel 1 (Sessions) | `<a> analyze  <A> analyze all  <f> filter  <x> remove  <e> export  <q> quit  <?> help [ML: Idle]` |
| Panel 2 (Exchanges) | `<Enter> view raw  <c> copy cURL  <f> filter  <e> export  <q> quit  <?> help [ML: Idle]` |
| Panel 3 (Analysis) | `<Enter> finding detail  <e> export  <q> quit  <?> help [ML: Idle]` |
| During analysis | Same + `[ML: Analyzing 2/5...]` replaces `[ML: Idle]` |

**Engine status indicator:**

- `[ML: Idle]` — dim white, no work happening
- `[ML: Analyzing...]` — pulsing yellow, with optional progress
- `[ML: Error]` — red, IPC failure

### 5.5 Toast Notifications

Brief, non-blocking messages that appear on the **right side of the status bar** for 3 seconds, then fade. They overlay (replace) the engine status temporarily.

**Visual:**

```shell
 <a> analyze  <f> filter  <e> export  <q> quit  <?> help          [Session abc123 removed]
```

After 3 seconds, reverts to:

```shell
 <a> analyze  <f> filter  <e> export  <q> quit  <?> help                       [ML: Idle]
```

**Triggers:**

- `x` (remove session): `"Session abc123 removed"`
- `c` (copy cURL): `"cURL copied to clipboard"`
- Export complete: `"Exported to report.json (4.5 KB)"`
- Analysis complete: `"Analysis complete: 87/100 CRITICAL"`

---

## 6. Interaction Model (Keybindings & Visual Effects)

### 6.1 Global Keybindings (Always Available)

| Key | Action | Visual Effect |
| --- | --- | --- |
| `Tab` | Move focus to next panel (1>2>3>1) | Active panel border changes from dim `--` to bright `==`. Previous panel reverts to dim. Bottom bar updates. |
| `Shift+Tab` | Move focus to previous panel (1>3>2>1) | Same as Tab but reversed. |
| `h`, `j`, `k`, `l` | Vim-style navigation: Left panel, Down in list, Up in list, Right panel | `h`/`l` act as `Shift+Tab`/`Tab`. `j`/`k` move the selection cursor within the active panel's list. Selected row is highlighted with inverted colors. |
| Up / Down | Standard list navigation | Same as `k`/`j`. |
| `e` | Open Export dialog | **Opens a modal popup** centered on screen. See §7.1. |
| `?` | Open help/command palette | **Opens a modal popup** showing all keybindings grouped by context. See §7.2. |
| `q` | Quit the application | **Opens a confirmation dialog**: "Quit CSRF Shield AI? [y/n]". Pressing `y` exits. Pressing `n` or `Esc` cancels and returns to the TUI. |
| `Esc` | Close any open modal / cancel batch analysis | If a modal is open, closes it and returns focus to the previous panel. If `analyze_all` is running, sends a `cancel` IPC request (finishes current session, stops batch). If nothing is happening, `Esc` does nothing. |
| `r` | Restart backend (ERROR state only) | Only active when the TUI is in the ERROR state (§8). Re-spawns the Python process and re-loads the HAR file. Transitions back to LOADING. Ignored in all other states. |

> **Text input mode:** When a text input field has focus (e.g., the filter search bar in §6.2 or the path field in the Export dialog §7.1), **all global keybindings are suspended** except `Esc` (cancel) and `Enter` (confirm). This allows the user to type freely without triggering panel switches or actions. This matches lazygit's behavior in search/filter mode.

### 6.2 Context-Specific Keybindings

#### Panel 1: Sessions

| Key | Action | Visual Effect |
| --- | --- | --- |
| `a` | Analyze selected session | The risk indicator on the selected session row changes to a spinner (`-`, `\`, `\|`, `/`). Panel 3 shows "Analyzing..." with a progress bar. When complete, the spinner is replaced by the risk dot (`[!!]`/`[!]`/`[~]`/`[*]`) and Panel 3 populates with results. For `HEADER_ONLY` sessions, this is near-instant (short-circuit). **If pressed while already analyzing this session, the keypress is ignored.** If pressed on an already-analyzed session, the previous results are discarded and analysis re-runs. |
| `A` (Shift+A) | Analyze ALL sessions sequentially | Sessions are analyzed one at a time, in list order. The currently-processing session shows a spinner; others show `--` until their turn. A progress counter appears in the status bar: `[ML: Analyzing 2/5...]`. Spinners resolve to risk dots as each session completes. Press `Esc` to cancel the batch (current session finishes, remaining are skipped). |
| `x` | Remove selected session from workspace | The selected row immediately disappears. Selection moves to the next session. A toast notification appears: "Session abc123 removed". **This is a Go-side-only operation** — the Python backend is not notified. The Go side maintains its own filtered session list; `analyze_all` only sends non-removed session IDs to Python. |
| `f` or `/` | Open fuzzy filter | **An inline text input appears at the top of the Sessions panel border**, replacing the title. All global keybindings are suspended (text input mode). As the user types, sessions are filtered in real-time by session ID or target host. Press `Enter` to confirm filter, `Esc` to cancel and restore full list. The filter is shown in the panel border: `[Filter: "api/"]`. |

#### Panel 2: Exchanges

| Key | Action | Visual Effect |
| --- | --- | --- |
| `Enter` | View raw HTTP request/response | **Opens a full-screen modal** showing the raw HTTP request on the left half and raw HTTP response on the right half. Content is scrollable with `j`/`k`. Headers are syntax-highlighted. Press `Esc` or `q` to close. See §7.3. |
| `c` | Copy selected request as cURL command | Generates a `cURL` command from the exchange's method, URL, headers, cookies, and body. Copies to system clipboard (see Clipboard Strategy below). A toast notification appears: "cURL copied to clipboard". |
| `f` or `/` | Open fuzzy filter | Same as Panel 1, but filters exchanges by URL path or HTTP method. |

**Clipboard Strategy:** The Go TUI uses the following platform-specific strategy for clipboard access:

| Platform | Method |
| --- | --- |
| Linux (X11) | `xclip -selection clipboard` |
| Linux (Wayland) | `wl-copy` |
| macOS | `pbcopy` |
| WSL | `clip.exe` |
| Fallback | OSC 52 escape sequence (works in modern terminals: iTerm2, Alacritty, kitty) |

If no clipboard tool is available, the toast shows: `"cURL written to /tmp/csrf-shield-curl.txt"` and writes to a temp file instead.

#### Panel 3: Analysis Engine

| Key | Action | Visual Effect |
| --- | --- | --- |
| `Enter` | View finding detail | If the cursor is on a static finding (e.g., `[CSRF-001]`), **opens a modal popup** showing: full rule description (from `rules.yaml`), detailed evidence, the raw exchange that triggered it, and remediation advice. See §7.4. |
| `j`/`k` | Scroll within the analysis detail | Scrolls through the analysis content (findings, feature vector, recommendations). The scrollbar position updates on the right edge of the panel. |

---

## 7. Modal Popups

Modals are overlapping views that appear centered on screen on top of the panel layout. They dim the background panels to ~30% brightness to create visual focus. All modals close with `Esc` or `q`.

> **Modal keybinding override:** When any modal is open, **all global and context-specific keybindings are inactive**. The modal captures all keyboard input exclusively. Only the modal's own keybindings (`Esc` to close, `j`/`k` to scroll, etc.) are active. This is a different mechanism from text input mode (§6.1) — text input mode suspends keys within a panel, while modals suspend the entire panel layer.

### 7.1 Export Dialog (`e`)

```shell
+--- Export Report --------------------------------+
|                                                  |
|  Format:   (*) JSON    ( ) HTML (static file)    |
|                                                  |
|  Scope:    (*) Selected session                  |
|            ( ) All analyzed sessions             |
|                                                  |
|  Path:     [report.json________________]         |
|                                                  |
|           [ Cancel ]        [ Export ]           |
|                                                  |
+--------------------------------------------------+
```

**Format clarification:**

- **JSON** — Machine-readable output, suitable for CI/CD pipelines or further processing.
- **HTML (static file)** — Self-contained HTML report with inline CSS. No JavaScript, no external dependencies. Opens in any browser. Does NOT require a running server.

**Interaction:** Arrow keys or `j`/`k` to move between options, `Space` or `Enter` to select, `Tab` to move to the path input field. The path field is an editable text input (**text input mode active** — global keybindings suspended). `Enter` on `[ Export ]` triggers the export via IPC and shows a success toast. `Esc` cancels.

### 7.2 Help / Command Palette (`?`)

```shell
+--- Keybindings --------------------------------------------------------+
|                                                                        |
|  --- Global --------------------------------------------------------   |
|  Tab / Shift+Tab     Cycle panel focus                                 |
|  h / j / k / l       Vim-style navigation                              |
|  e                   Export report                                     |
|  ?                   This help menu                                    |
|  q                   Quit                                              |
|  Esc                 Close modal / cancel batch                        |
|  r                   Restart backend (ERROR state only)                |
|                                                                        |
|  --- Sessions Panel ------------------------------------------------   |
|  a                   Analyze selected session                          |
|  A (Shift+A)         Analyze all sessions (sequential)                 |
|  x                   Remove session from workspace                     |
|  f or /              Filter sessions                                   |
|                                                                        |
|  --- Exchanges Panel -----------------------------------------------   |
|  Enter               View raw HTTP request/response                    |
|  c                   Copy as cURL to clipboard                         |
|  f or /              Filter exchanges                                  |
|                                                                        |
|  --- Analysis Panel ------------------------------------------------   |
|  Enter               View finding detail                               |
|  j / k               Scroll analysis content                           |
|                                                                        |
|  Note: All keys except Esc/Enter are suspended during text input.      |
|                                                                        |
|                              [ Close ]                                 |
|                                                                        |
+------------------------------------------------------------------------+
```

**Interaction:** This is a read-only overlay. `Esc`, `q`, or `?` (toggle) closes it.

### 7.3 Raw HTTP View (`Enter` on Exchange)

```shell
+--- Raw HTTP -- POST /api/transfer ------------------------------------------------+
|                                                                                   |
|  --- Request -------------------------  --- Response ---------------------------  |
|                                                                                   |
|  POST /api/transfer HTTP/1.1            HTTP/1.1 200 OK                           |
|  Host: api.target.com                   Content-Type: application/json            |
|  Content-Type: application/x-www-       Set-Cookie: session_id=abc123;            |
|    form-urlencoded                        path=/; HttpOnly                        |
|  Cookie: session_id=abc123              Content-Length: 42                        |
|                                                                                   |
|  amount=1000&account_to=attacker        {"status": "ok", "tx_id": "789"}          |
|                                                                                   |
|                                                                                   |
|                                                            [ Close (Esc) ]        |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

**Interaction:** `j`/`k` scrolls vertically. `h`/`l` switches focus between Request and Response columns. Syntax highlighting on header names (bold) and values (dim). `Esc` or `q` closes.

### 7.4 Finding Detail (`Enter` on Finding in Panel 3)

```shell
+--- CSRF-001: Missing CSRF Token in Form -----------------------------------------+
|                                                                                  |
|  Severity:     [!] HIGH                                                          |
|  Rule ID:      CSRF-001                                                          |
|  Module:       csrf_001                                                          |
|                                                                                  |
|  --- Description --------------------------------------------------------------- |
|                                                                                  |
|  State-changing request without CSRF token in form body. The endpoint            |
|  POST /api/transfer accepts form-urlencoded data with parameters 'amount'        |
|  and 'account_to' but does not include any recognized CSRF token parameter.      |
|                                                                                  |
|  --- Evidence ------------------------------------------------------------------ |
|                                                                                  |
|  Exchange:     POST /api/transfer (200)                                          |
|  Body params:  amount=1000, account_to=attacker                                  |
|  CSRF token:   NOT FOUND (searched: csrf_token, _token, _csrf, ...)              |
|                                                                                  |
|  --- Remediation --------------------------------------------------------------- |
|                                                                                  |
|  1. Add a unique, unpredictable CSRF token to the form.                          |
|  2. Validate the token on the server for every state-changing request.           |
|  3. Consider using the Synchronizer Token Pattern or Double Submit Cookie.       |
|                                                                                  |
|                                                            [ Close (Esc) ]       |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

**Interaction:** `j`/`k` scrolls if content overflows. `Esc` or `q` closes.

---

## 8. State Machine: TUI Lifecycle

The TUI follows a state machine that includes both happy path and error recovery:

```shell
                    +------------------+
                    |     LAUNCH       |
                    |  Parse CLI args  |
                    +--------+---------+
                             |
              +--------------v--------------+
              |     LOADING                 |     Spawn Python backend,
              |     Show splash screen      |     parse HAR file.
              |     Progress bar visible    |
              +--------+----------+---------+
                       |          |
                  (success)    (failure)
                       |          |
          +------------v--+  +----v--------------+
          |   BROWSING    |  |   ERROR           |
          |   Panels show |  |   Show error msg  |<------+
          |   No analysis |  |   <q> to quit     |       |
          +---+-----------+  +---------+--------+        |
              |       |                |                 |
         <a>/<A>   <q>+<y>      <r> to retry             |
              |       |                |                 |
    +---------v-+  +--v--------+  +----v-----------+     |
    | ANALYZING |  |   EXIT    |  |   LOADING      |     |
    | Spinner   |  +-----^-----+  |   (retry)      +-----+
    | Progress  |        |        +----------------+
    +-----+-----+        |
          |              |
     (results arrive)    |
          |              |
    +-----v------+       |
    | BROWSING   |       |
    | + results  +--+    |
    +-----+------+  |    |
          |         |    |
     <e> export  <q>+<y> |
          |         |    |
    +-----v------+  |    |
    | EXPORTING  |  +----+
    | Modal open |
    +-----+------+
          |
     (done/cancel)
          |
    +-----v------+
    | BROWSING   |
    +------------+

  Any state -----(Python process dies)-----> ERROR
```

> **Note:** Export is optional. The user can quit directly from BROWSING via `<q>` then `<y>` at any time.

**Error state details:**

| Error Condition | Message Shown | Recovery |
| --- | --- | --- |
| Python not found | `"Python 3 not found. Install Python 3.10+ and try again."` | `<q>` to quit |
| Missing dependency | `"Backend error: ModuleNotFoundError: scikit-learn"` | `<q>` to quit, fix deps, restart |
| HAR file not found | `"File not found: /bad/path.har"` | `<q>` to quit |
| HAR parse error | `"Invalid HAR file at line 42: unexpected token"` | `<q>` to quit |
| Backend crash mid-analysis | `"Backend process exited unexpectedly (code 1)"` | `<r>` to restart backend, or `<q>` to quit |
| IPC timeout (>10s no ping response) | `"Backend not responding. Press <r> to restart."` | `<r>` to restart, `<q>` to quit |

---

## 9. Constraints & Edge Cases

### 9.1 Minimum Terminal Size

The 3-panel layout requires a terminal of at least **100 columns x 24 rows**. If the terminal is smaller:

- The TUI displays a centered, single-line message: `"Terminal too small (WxH). Need at least 100x24. Please resize."`
- The TUI listens for terminal resize events (`SIGWINCH` on Linux/macOS)
- When the terminal reaches adequate size, the panels render immediately

### 9.2 Large Session Handling

| Scenario | Behavior |
| --- | --- |
| Session with 200+ exchanges | Panel 2 scrolls, showing a scroll indicator `[3/247]` on the right edge. Only visible rows are rendered (virtual scrolling). |
| HAR file with 50+ sessions | Panel 1 scrolls, same virtual scrolling pattern. |
| Very long URL (>40 chars) | Truncated with `...`: `/api/v2/user/preferences/notific...` |
| Very long evidence string | Truncated in panel, full content visible in Finding Detail modal (§7.4). |

### 9.3 Empty & Degenerate States

| Scenario | Behavior |
| --- | --- |
| HAR file with 0 entries | Panel 1 shows: `"No sessions found."` Panel 2 & 3 are empty. |
| All requests are GET (no state-changing) | Analysis produces only INFO findings (no CSRF risk). Risk scores will be low (0-10). The TUI displays results normally. |
| Session with 1 exchange | Works normally — one row in Panel 2. |
| All sessions already analyzed | `<a>` re-analyzes (overwrites cached result). `<A>` re-analyzes all. |

### 9.4 Terminal Resize During Operation

The TUI recalculates panel dimensions on every resize event via `gocui`'s built-in resize handler. Panel widths are calculated using integer division:

```go
leftWidth   = termWidth / 2
rightWidth  = termWidth - leftWidth - 1   // 1 char for the divider
topHeight   = (termHeight - 1) / 2        // 1 row for status bar
botHeight   = termHeight - 1 - topHeight
rightHeight = termHeight - 1              // right panel spans full height
```

> **Note:** The right panel (Panel 3) spans the full terminal height (minus status bar), which is taller than either left panel individually. This is intentional — the analysis detail needs more vertical space than the session/exchange lists. The left panels share the left column height equally.

---

## 10. CLI Entry Point

The TUI is launched via a new `tui` subcommand:

```shell
# Launch TUI with a HAR file (--input is required)
csrf-shield tui --input traffic.har
```

> `--input` is **required**. Running `csrf-shield tui` without it prints usage help and exits. A TUI-based file picker may be added in a future version but is out of scope for the initial implementation.

**Startup error handling:**

- If `--input` path doesn't exist: Go-side catches this before spawning Python, shows error in LOADING state.
- If Python is not installed: Go attempts `python3 --version`, catches error, shows "Python not found" in ERROR state.
- If `ipc_server.py` has import errors: Python exits with non-zero code, Go captures stderr and displays it in ERROR state.

The existing `csrf-shield analyze` command remains for non-interactive CI/CD usage. The TUI is the interactive counterpart.

---

## 11. Revised Implementation Plan Impact

This TUI specification modifies the deliverables for **Phase 4**:

- **Current Phase 4 Goal:** Risk Scoring & Reports.

- **Added Task:** Implement Go-based TUI architecture (`cmd/tui/main.go`).

- **Added Task:** Implement Python IPC server (`src/ipc_server.py`) — a NDJSON server over stdin/stdout that wraps the existing Python modules.

- **Added Task:** Set up Inter-Process Communication (IPC) utilizing NDJSON streams to connect the Go frontend with the Python ML backend.

- **Phase 5 Adjustment:** The Web Dashboard (Phase 5) is now explicitly relegated to an "optional extra" or simply a static HTML output viewer, solidifying the TUI as the flagship interface of the project.

### Go Project Structure

```shell
IAW_Project/
+-- cmd/
|   +-- tui/
|       +-- main.go              # TUI entry point, CLI args, process spawn
+-- internal/
|   +-- ui/
|   |   +-- app.go               # gocui setup, layout manager, main loop
|   |   +-- panels/
|   |   |   +-- sessions.go      # Panel 1: SessionFlow list rendering
|   |   |   +-- exchanges.go     # Panel 2: HttpExchange list rendering
|   |   |   +-- analysis.go      # Panel 3: AnalysisResult detail rendering
|   |   +-- keybindings.go       # Global + context-specific key handlers
|   |   +-- statusbar.go         # Bottom bar with dynamic hints + ML status
|   |   +-- toast.go             # Toast notification manager (3s auto-dismiss)
|   |   +-- modals/
|   |       +-- help.go          # ? command palette
|   |       +-- export.go        # e export dialog
|   |       +-- rawview.go       # Enter raw HTTP viewer
|   |       +-- finding.go       # Enter finding detail
|   |       +-- confirm.go       # q quit confirmation
|   +-- ipc/
|   |   +-- client.go            # Spawns Python, manages process lifecycle
|   |   +-- protocol.go          # NDJSON message types (Request/Response/Error)
|   |   +-- stream.go            # Buffered NDJSON reader/writer over stdin/stdout
|   |   +-- health.go            # Ping loop, crash detection, restart logic
|   +-- clipboard/
|   |   +-- clipboard.go         # Platform-specific clipboard (xclip/pbcopy/etc.)
|   +-- models/
|       +-- types.go             # Go structs mirroring Python dataclasses
+-- go.mod
+-- go.sum
+-- src/
    +-- ipc_server.py            # NEW: Python-side NDJSON server
    +-- ...                      # (existing Python modules)
```

---

## Appendix: Version Changelog

| Version | Date | Changes |
| --- | --- | --- |
| v1.0 | Initial | Original TUI design specification: panel layout, keybindings, IPC protocol, state machine, mockups. |
| v2.0 | Revised | Renamed `get_result` to `get_results`. Redesigned `analyze_flow` response to return `summary` + `results[]` array. Made `cancel` cooperative. Made `--input` required. Fixed state machine (`BROWSING -> EXIT` direct path). Added `r` key for backend restart. Replaced percentage-based panel widths with Go integer division. |
| v2.1 | Revised | Added exchange risk dot derivation logic. Clarified `a`/`A` keypress edge cases. Updated `Esc` for batch cancellation. Added text input mode callout. |
| v2.2 | Revised | Added `static_score` field to per-exchange IPC results + `ml_probability_max` / `static_score_max` to `summary` (fixes Mode A data gap). Added `session_id` to `export_report` params. Added stderr handling spec. Added modal keybinding override rule. Fixed right panel height formula. Added `[Text]` badge security note. Specified pinned vs scrollable sections in Panel 3. Clarified analyzed-session risk dot always shows (never blank). |
| v2.3 | Revised | Added enum serialization value table (exact `.value` strings for Go). Added `Finding.exchange` compact serialization. Added `get_results` not-analyzed response format. Added dual-level progress events (`session_index`/`session_total` + `step_current`/`step_total`). Clarified `x` (remove) is Go-side only. Fixed "No session selected" mockup text. Fixed §4.3 status bar actions. Added `static_score` required backend change note. Added this changelog. |
