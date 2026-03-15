# TUI Exhaustive Runtime QA Report

## Feature/Scenario Tested
Full proposal-driven interactive validation of TUI workflows and hotkeys in the actual binary:
- Binary: `bin/csrf-shield-tui`
- Date: 2026-03-14
- Data inputs: `data/sample_har/mixed_auth.har`, `data/sample_har/bearer_auth.har`, `data/sample_har/vulnerable.har`, invalid path

## Reference Document
- `docs/proposal/CLI_TUI_PROPOSAL.md` (sections 4, 5, 6, 7, 8, 9, 10)
- `spec_tui_v2/Requirements.md` (FR-701 through FR-711)
- `spec_tui_v2/Design.md`

## Expected vs. Actual Behavior

### 1. FR-706 Quit Safety (`q`) — FAIL
- Expected:
  - `q` from base layout opens quit confirmation `Quit CSRF Shield AI? [y/n]`.
  - `n` cancels and returns to TUI.
- Actual:
  - TUI exits immediately after `q` in live runtime probe (EOF) with no confirmation modal.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=quit_confirm`, `see_quit_prompt` failed with EOF)
  - `docs/reports/_tui_probe_quit_confirm.clean.txt` (contains `q` then process termination, no quit modal text)

### 2. FR-705 Export Modal (`e`) — FAIL
- Expected:
  - `e` opens Export Report modal, allows format/scope/path selection and export.
- Actual:
  - Probe did not surface `Export Report`; action appears non-functional in this runtime path.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=export_path_input`, `export_opened` timeout)
  - `docs/reports/_tui_probe_export_path_input.clean.txt` (keypress `e` observed, no modal content)

### 3. FR-701 Filter Modal (`f` or `/`) — FAIL
- Expected:
  - `f` opens filter input modal; typing and submit applies filter.
- Actual:
  - Filter modal did not appear during probe.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=filter_text_input`, `filter_modal` timeout)
  - `docs/reports/_tui_probe_filter_text_input.clean.txt` (keypress `f` present, no filter modal text)

### 4. Global Focus Navigation (`Tab`) + FR-702 Raw View Reachability — FAIL
- Expected:
  - `Tab` moves active focus to Exchanges panel.
  - `Enter` on Exchanges opens raw request/response modal.
- Actual:
  - Probe did not observe Panel 2 hint/state transition; raw modal not reached.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=raw_view_modal`, `panel2_hint` timeout)
  - `docs/reports/_tui_probe_raw_view_modal.clean.txt`

### 5. Proposal §8 Error-State UX (bad `--input`) — FAIL (behavioral mismatch)
- Expected:
  - TUI transitions to loading/error state and allows in-app recovery (`r`) or quit prompt.
- Actual:
  - Immediate CLI stderr error and exit: `Error: file not found: data/sample_har/does_not_exist.har`.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=bad_input_behavior`)
  - `docs/reports/_tui_runtime_scenario_bad_input.clean.txt`

### 6. Help Modal (`?`) — PASS
- Expected:
  - `?` opens Keybindings modal and toggles close.
- Actual:
  - Works in live probe.
- Evidence:
  - `docs/reports/_tui_feature_probes.json` (`probe=help_modal` all steps passed)
  - `docs/reports/_tui_probe_help_modal.log`

### 7. Analyze-All Flow (`A`) and Analysis Rendering — PASS
- Expected:
  - Batch analysis triggers progress/result and renders risk score + findings.
- Actual:
  - Risk score and findings rendered (`RISK SCORE: 30/100`, findings/recommendations present).
- Evidence:
  - `docs/reports/_tui_probe_analyze_all.clean.txt`

### 8. Header-Only Short-Circuit Presentation — PASS
- Expected:
  - Header-only auth session short-circuits with LOW score and CSRF N/A messaging.
- Actual:
  - Correct short-circuit output observed (`RISK SCORE: 5/100`, `SHORT-CIRCUITED`, `No action needed - CSRF N/A`).
- Evidence:
  - `docs/reports/_tui_probe_header_short_circuit.clean.txt`

## Exhaustive Interaction Log

### Probe A: Quit Confirmation Behavior
1. Launch: `./bin/csrf-shield-tui --input data/sample_har/mixed_auth.har`
2. Wait for `Sessions`
3. Press `q`
4. Expected quit modal did not appear; process ended (EOF)

### Probe B: Help Modal
1. Launch with `mixed_auth.har`
2. Press `?`
3. Verify `Keybindings`
4. Press `?` again
5. Verify return to base UI

### Probe C: Export Modal
1. Launch with `mixed_auth.har`
2. Press `e`
3. Expected `Export Report` modal never appeared
4. Test aborted after timeout

### Probe D: Filter Modal
1. Launch with `mixed_auth.har`
2. Press `f`
3. Expected `Filter (empty to clear)` modal never appeared
4. Test aborted after timeout

### Probe E: Raw View Reachability
1. Launch with `mixed_auth.har`
2. Press `Tab` to move focus to Exchanges
3. Expected panel-specific hint/modal flow not observed
4. Raw modal (`Enter`) not reached

### Probe F: Analyze All
1. Launch with `mixed_auth.har`
2. Press `A`
3. Observe analysis output and `RISK SCORE` in Analysis panel

### Probe G: Header-Only Short-Circuit
1. Launch with `bearer_auth.har`
2. Press `a`
3. Verify `SHORT-CIRCUITED` and LOW-risk rendering

### Probe H: Bad Input
1. Launch with invalid path: `--input data/sample_har/does_not_exist.har`
2. Observe immediate stderr + exit instead of in-app error screen

## Raw/Debug Output

### Structured probe results
- `docs/reports/_tui_feature_probes.json`

### Runtime logs
- `docs/reports/_tui_probe_quit_confirm.log`
- `docs/reports/_tui_probe_help_modal.log`
- `docs/reports/_tui_probe_export_path_input.log`
- `docs/reports/_tui_probe_filter_text_input.log`
- `docs/reports/_tui_probe_raw_view_modal.log`
- `docs/reports/_tui_probe_analyze_all.log`
- `docs/reports/_tui_probe_header_short_circuit.log`

### ANSI-stripped logs for readability
- `docs/reports/_tui_probe_quit_confirm.clean.txt`
- `docs/reports/_tui_probe_help_modal.clean.txt`
- `docs/reports/_tui_probe_export_path_input.clean.txt`
- `docs/reports/_tui_probe_filter_text_input.clean.txt`
- `docs/reports/_tui_probe_raw_view_modal.clean.txt`
- `docs/reports/_tui_probe_analyze_all.clean.txt`
- `docs/reports/_tui_probe_header_short_circuit.clean.txt`
- `docs/reports/_tui_runtime_scenario_bad_input.clean.txt`

## Post-Fix Revalidation Delta (2026-03-14)

After implementing targeted fixes in keybinding scope, export modal behavior, quit handling, and invalid-path startup flow, a refined probe pass was executed.

### Refined Probe Summary
- Result: `3/6` direct regex checks passed.
- Evidence: `docs/reports/_tui_fix_probe_refined.json`

### Item-by-Item Status
- `f` filter modal: **FIXED** in runtime (`ok=true` in refined probe).
- Invalid path error state: **FIXED** in runtime (`ok=true`, in-app error state reached).
- `Tab` to Exchanges: **FIXED** for focus transition (`ok=true`).
- `q` quit confirm: **Rendered in runtime**, but probe regex still timed out.
  - The timeout buffer in `docs/reports/_tui_fix_probe_refined.json` contains `Quit CSRF ShieldAI?[y/n]`, which indicates modal rendering occurred.
  - Additional debug trace confirms modal presence: `docs/reports/_debug_q.clean.txt`.
- `e` export modal: **Rendered in runtime**, but probe regex still timed out.
  - The timeout buffer includes full export box drawing in `docs/reports/_tui_fix_probe_refined.json`.
  - Additional debug trace confirms modal presence: `docs/reports/_debug_e.clean.txt`.
- Raw modal (`Tab` -> `Enter`): **Still OPEN** in automated probe (`ok=false`), requiring a dedicated follow-up probe/manual validation pass.

### Interpretation
- Earlier hard-fail conclusions for quit/export are now downgraded from confirmed functional regressions to **probe-matching artifacts** (spacing/ANSI formatting mismatch), because runtime buffers show the modal content being drawn.
- Remaining high-confidence open issue is the raw viewer reachability check in automated flow.

## Final QA Verdict
- Proposal compliance is partial.
- Core analysis and header-only short-circuit rendering are working.
- Post-fix status:
  - Verified fixed: filter modal (`f`), invalid input in-app error state, `Tab` focus transition.
  - Rendered but regex-fragile in automation: quit modal (`q`), export modal (`e`).
  - Still open for direct follow-up validation: raw viewer reachability (`Tab` -> `Enter`).
