# 🖥️ Addendum: Terminal User Interface (TUI) Design Specification

> **Project:** CSRF Shield AI
> 
> **Reference:** PROPOSAL.md v1.2
> 
> **Document Status:** Extension Specification

## 1. Design Philosophy & Inspiration

The primary operational interface for CSRF Shield AI will be a **Terminal User Interface (TUI)**. While the Web Dashboard (Phase 5) remains an option for presenting final html reports to non-technical stakeholders, the core tool is designed for security engineers who live in the terminal.

The UI architecture is heavily inspired by **`lazygit`** (by Jesse Duffield). It adheres to the following core principles:

1. **Panel-Based Context:** The screen is divided into fixed panes. Selecting an item in a left-hand pane instantly updates the detail views in the right-hand panes.
    
2. **Keyboard-Driven (Vim-style):** 100% mouse-free operation using `h/j/k/l`, `Tab`, and single-key action bindings (`a` for analyze, `e` for export).
    
3. **Discoverability:** Always visible keybindings in a bottom status bar and a modal help menu mapped to `?`.
    
4. **Color-Coded Feedback:** Native terminal colors strictly tied to the Risk Scoring Model (Green/Yellow/Orange/Red).
    

## 2. Technical Stack

To mirror the exact performance, responsiveness, and architecture of `lazygit`, the TUI component will adopt Jesse Duffield's core stack:

- **Language:** **Go (Golang)**. Go's compiled nature and lightweight concurrency (goroutines/channels) ensure the UI remains instantly responsive and never blocks, even when parsing massive HAR files or waiting on ML inference.
    
- **UI Framework:** **`gocui`** (specifically utilizing `jesseduffield/gocui`, the custom fork built for lazygit). This library allows for overlapping views, custom keybindings, and raw terminal manipulation.
    
- **State Management:** Reactive state handling via Go channels, decoupling the UI rendering loop from the heavy lifting of the analysis engine.
    
- **Integration Strategy (Go + Python):** Since the core CSRF ML engine requires Python (`scikit-learn`, `pandas`), the Go TUI will act as a lightning-fast client. It will execute the Python core as a background sub-process, receiving streaming JSON analysis results via `stdout` or a local socket to populate the UI panes.
    

## 3. UI Layout & Architecture

The TUI is divided into three primary vertical sections: **Context (Left)**, **Main Detail (Center/Right)**, and **Global Controls (Bottom)**.

To ensure the user always knows how to interact with the tool, **the currently active panel is highlighted with a double-line border**, and the bottom control bar dynamically updates to show available actions for that specific panel.

### 3.1 Screen Mockup

```
╔═ Sessions (Flows) ──[Filter: "api/"]════[1]═╗┌─ Analysis Engine ───────────────[3]─┐
║ > Session: abc123_xyz (api.target.com)      ║│ RISK SCORE: 87/100  [X] CRITICAL    │
║   Auth: Mixed (Cookie+JWT)    [12 reqs]     ║│ ML Confidence: 85% | Static: 70%    │
║                                             ║├─────────────────────────────────────┤
║   Session: qwe890_rty (auth.target.com)     ║│ [!] STATIC FINDINGS:                │
║   Auth: Header Only (Bypass)  [4 reqs]      ║│ [CSRF-001] Missing Form Token (HIGH)│
║                                             ║│   ↳ form param 'account_to'         │
║   Session: zxc456_bnm (api.target.com)      ║│ [CSRF-005] Missing SameSite (MED)   │
║   Auth: Cookie                [2 reqs]      ║│   ↳ cookie 'session_id'             │
╠═════════════════════════════════════════════╣│                                     │
┌─ Exchanges (Requests) ─────────[2]──────────┐│ [*] ML FEATURE VECTOR:              │
│   GET  /dashboard              [None]  200  ││ has_csrf_token_in_form   : False    │
│   GET  /api/user               [None]  200  ││ has_samesite_cookie      : False    │
│   POST /api/transfer           [JSON]  200  ││ token_entropy            : 0.00     │
│   POST /api/upload             [Form]  200  ││ is_state_changing        : True     │
│   PUT  /api/settings           [JSON]  200  ││ auth_mechanism           : mixed    │
│   DELETE /api/remove           [JSON]  200  ││ endpoint_sensitivity     : 0.95     │
└─────────────────────────────────────────────┘└─────────────────────────────────────┘
[Sessions] <a> analyze | <x> delete | <f> filter | <c> copy cURL | <Enter> view raw
[Global]   <q> quit | <tab> next panel | <e> export | <?> menu        [ML: Idle]
```

### 3.2 Panel Breakdown

- **Panel 1: Sessions (Top Left)**
    
    - Lists all grouped `SessionFlow` objects. Now includes **Target Host** and **Request Count** for immediate context.
        
    - _UI Indicators:_ The top border dynamically shows active search strings (e.g., `[Filter: "api/"]`).
        
    - _Active Interactions:_ Pressing `a` triggers the ML analysis for the selected flow. Pressing `x` discards the flow from the workspace.
        
- **Panel 2: Exchanges (Bottom Left)**
    
    - Lists all `HttpExchange` objects associated with the selected `SessionFlow`.
        
    - _UI Indicators:_ Shows the payload type (`[JSON]`, `[Form]`, `[None]`) next to the request path to clarify how data is structured.
        
    - _Active Interactions:_ Pressing `Enter` opens a full-screen, scrollable modal showing the raw HTTP Request/Response bodies. Pressing `c` copies the selected request as a fully-formatted `cURL` command to the clipboard.
        
- **Panel 3: Analysis Engine (Main Right)**
    
    - Displays the final `AnalysisResult` for the currently selected session/exchange.
        
    - _UI Indicators:_ Appends **Evidence Strings** (e.g., `↳ form param 'account_to'`) directly beneath findings so the pentester knows exactly what triggered the rule.
        
    - _Active Interactions:_ Pressing `Enter` on a specific Static Finding opens the remediation advice modal.
        
- **Global Controls / Modals:**
    
    - **Engine Status:** The bottom right corner displays `[ML: Idle]` or `[ML: Analyzing...]` to indicate subprocess status.
        
    - `Shift+E`: Opens an "Export Report" dialog (prompts for JSON or HTML output).
        
    - `?`: Opens a searchable Command Palette (similar to VS Code) listing every available action.
        

## 4. Interaction Model (Keybindings)

Following the `lazygit` convention, standard keybindings are divided into Global actions and Context-Specific actions.

### Global Keybindings (Always Available)

|   |   |
|---|---|
|**Key**|**Action**|
|`Tab` / `Shift+Tab`|Cycle focus between Panel 1, 2, and 3|
|`h`, `j`, `k`, `l`|Vim-style navigation (Left, Down, Up, Right)|
|`Up` / `Down`|Standard list navigation|
|`e`|Export current analysis to HTML/JSON|
|`?`|Show command menu / keybindings overlay|
|`q`|Quit the application|

### Context-Specific Keybindings (Change based on active panel)

|   |   |   |
|---|---|---|
|**Key**|**Active Panel**|**Action**|
|`a`|Panel 1 (Sessions)|**Trigger ML Analysis** for the selected SessionFlow|
|`A`|Panel 1 (Sessions)|**Trigger ML Analysis** for ALL SessionFlows|
|`x`|Panel 1 (Sessions)|Remove the selected session from the workspace|
|`/`|Panel 1 or 2|Open fuzzy-finder to search by URL or Session ID|
|`c`|Panel 2 (Exchanges)|Copy the selected request to clipboard as a `cURL` command|
|`Enter`|Panel 2 (Exchanges)|Open raw HTTP Request/Response detail modal|
|`Enter`|Panel 3 (Analysis)|View detailed explanation for selected static finding|

## 5. Visual Language & Risk Mapping

The terminal colors will strictly map to the scoring model defined in `PROPOSAL.md` Section 10.2:

- `[bold green]` (0–20): **LOW** Risk. Used for safely protected endpoints and CSRF-011 short-circuits.
    
- `[bold yellow]` (21–40): **MEDIUM** Risk.
    
- `[bold dark_orange]` (41–70): **HIGH** Risk.
    
- `[bold red]` (71–100): **CRITICAL** Risk. Used for static tokens and severe vulnerabilities.
    
- `[dim white]`: Used for non-state-changing GET requests.
    

## 6. Revised Implementation Plan Impact

This TUI specification modifies the deliverables for **Phase 4**:

- **Current Phase 4 Goal:** Risk Scoring & Reports.
    
- **Added Task:** Implement Go-based TUI architecture (`cmd/tui/main.go`).
    
- **Added Task:** Set up Inter-Process Communication (IPC) utilizing JSON streams to connect the Go frontend with the Python ML backend.
    
- **Phase 5 Adjustment:** The Web Dashboard (Phase 5) is now explicitly relegated to an "optional extra" or simply a static HTML output viewer, solidifying the TUI as the flagship interface of the project.