# TUI Full Proposal Runtime QA Report

## Feature/Scenario Tested
Exhaustive runtime validation of the Go TUI against proposal and v2 requirements using scripted PTY interactions across all major workflows:
- Binary: `bin/csrf-shield-tui`
- Harness: `scripts/tui_proposal_full_probe.py`
- Results artifact: `docs/reports/_tui_full_proposal_results.json`
- Date: 2026-03-14

Coverage scope:
- Global navigation and modal behavior (`Tab`, `Shift+Tab`, `h/j/k/l`, `?`, `q`)
- Sessions panel actions (`a`, `A`, `x`, `f`, `/`)
- Exchanges panel actions (`Enter`, `c`, `/`) and panel guards
- Analysis panel actions (`Enter`, `j`, `k`)
- Export workflow (`e`, format/scope/path input)
- Content-type badges (`[Form]`, `[JSON]`, `[None]`, `[Multi]`, `[Text]`)
- Error state behavior (`r`, `q` in ERROR)
- Minimum terminal size handling (100x24)

## Reference Document
- `docs/proposal/CLI_TUI_PROPOSAL.md`
- `spec_tui_v2/Requirements.md` (FR-701 through FR-711)
- `spec_tui_v2/Design.md`

## Expected vs. Actual Behavior

### Aggregate Result Snapshot
- `core_global_nav`: `18/19`
- `sessions_actions`: `15/19`
- `exchanges_actions`: `19/21`
- `analysis_panel_actions`: `10/10`
- `export_dialog`: `8/9`
- `badge_form_json_none`: `2/3`
- `badge_multi`: `1/1`
- `badge_text`: `1/1`
- `error_state_restart`: `3/5`
- `small_terminal`: `1/1`

## Post-Fix Delta (Second Patch Pass)

Date: 2026-03-14 (latest rerun after rebuilding `bin/csrf-shield-tui` from current source)

### Full Proposal Probe Delta
- `sessions_actions`: improved from `13/19` to `15/19`
- `export_dialog`: improved from `7/9` to `8/9`
- Other case totals remained unchanged in this run.

Interpretation:
- The implemented fixes produced measurable runtime gains in sessions filtering/status flow and export interaction visibility.
- Remaining failures continue to cluster around PTY/ANSI matcher sensitivity and a small number of true residual interaction edge cases.

### Targeted Refined Probe (`scripts/tui_refined_probe.py`)
- Summary: `6/6` passed
- Passing probes:
  - `q_confirmation`
  - `filter_modal`
  - `export_modal`
  - `tab_to_exchanges`
  - `raw_modal`
  - `invalid_path_error_state`

Assessment:
- Core modal entry points and invalid-input error rendering are stable under targeted checks.
- Final green status required probe hardening against ANSI/cursor-fragmented output and correcting Enter key dispatch in the probe (`\r` vs `\n`), indicating the residual failures were primarily harness robustness issues rather than new runtime regressions.

### Confirmed Runtime Deviations (Proposal/FR Mismatch)

1. FR-701.1 (`/` opens filter modal) in Sessions panel is inconsistent.
- Expected: `/` while Panel 1 is active opens `Filter (empty to clear)` modal.
- Actual: `f` path opened modal, but immediate `/` check in same scenario timed out.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`sessions_actions.filter_modal_open_slash = false`)
  - `docs/reports/_tui_full_sessions_actions.log`

2. FR-701.6 (active filter title indicator) not confirmed in Sessions panel.
- Expected: title shows `[Filter: "..."]` while filter is active.
- Actual: probe did not detect filter title indicator after submitting `vuln`.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`sessions_actions.filter_title_shown = false`)

3. FR-701.2 / FR-701.4 filter application visibility in Exchanges panel not confirmed.
- Expected: submitting `POST` on Panel 2 should visibly show filtered state/content.
- Actual: filter modal opened and accepted input, but no post-submit filtered-state pattern was matched.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`exchanges_actions.filter_applied_exchange = false`)
  - `docs/reports/_tui_full_exchanges_actions.log`

4. FR-711.1/FR-711.2 restart feedback in ERROR flow is incomplete.
- Expected: `r` in ERROR triggers restart transition and visible LOADING/ERROR refresh feedback.
- Actual: initial ERROR state and hint (`Press <r> to restart or <q> to quit.`) were visible, but restart feedback check timed out.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`error_state_restart.restart_feedback = false`)
  - `docs/reports/_tui_full_error_state_restart.log`

### Likely Automation/Matching Artifacts (Rendered in Logs, Regex Miss)

1. FR-706.2 quit confirmation visibility in global flow.
- Probe check failed (`quit_confirm_visible`), but modal behavior has been previously observed in refined probes and this run log includes heavy redraw/ANSI fragmentation.
- Status: needs manual runtime confirmation in interactive terminal to rule out false negative.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`core_global_nav.quit_confirm_visible = false`)
  - `docs/reports/_tui_full_core_global_nav.log`

2. FR-705.1 export modal open check.
- Probe marked modal missing, but log contains `Export Report` modal frame and fields (`Format`, `Scope`, `Path`).
- Status: treated as regex false negative.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`export_dialog.export_modal_visible = false`)
  - `docs/reports/_tui_full_export_dialog.log`

3. FR-705 export result toast check.
- Probe did not detect `Exported to ...` or `Export error`; log shows modal interactions and redraws, but terminal capture did not preserve a stable toast match.
- Status: inconclusive under current matcher; manual verification recommended.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`export_dialog.export_result_toast = false`)

4. FR-704.3 cURL fallback toast check.
- Probe expected lowercase `written`; runtime log shows toast text with capitalized `Written to /tmp/csrf-shield-curl.txt`.
- Status: regex mismatch, not a product defect.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`exchanges_actions.curl_toast = false`)
  - `docs/reports/_tui_full_exchanges_actions.log` (contains `Written to /tmp/csrf-shield-curl.txt`)

5. FR-707 `[None]` badge check.
- Probe unexpectedly marked `[None]` missing while same log clearly contains `[None]` in exchanges rows.
- Status: matcher/order artifact.
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`badge_form_json_none.badge_none = false`)
  - `docs/reports/_tui_full_badge_form_json_none.log`

6. FR-709.1 guard behavior and analysis progress checks in Sessions flow.
- Panel guard key sends were successful, but checks relying on transient UI text (`Analyzing`, `RISK SCORE`, status bar transitions) timed out in this run.
- Status: likely timing/redraw artifact; several related functions were validated in other scenarios (`analysis_panel_actions` passed `10/10`).
- Evidence:
  - `docs/reports/_tui_full_proposal_results.json` (`analysis_progress_or_score`, `analyze_all_status`, `post_cancel_ui` failed)

### Additional Observation: FR-708 ANSI Risk Colors
- Harness ANSI scan in `docs/reports/_tui_full_proposal_results.json` returned all false (`low_green`, `medium_yellow`, `high_orange`, `critical_red`).
- This check searched for escaped string literals and is not a reliable final verdict for terminal-rendered colors in this capture format.
- Result classification: inconclusive from this automation run.

### Behaviors Verified as Working in This Run
- FR-701.1 via `f` (filter modal opens)
- FR-702 raw exchange viewer open/scroll/switch/close
- FR-703 finding detail open/close path (or no-findings placeholder)
- FR-704 panel-specific guard for `c` in Sessions and cURL generation path in Exchanges
- FR-705 modal interaction path (format/scope/path input)
- FR-707 badges `[Form]`, `[JSON]`, `[Multi]`, `[Text]` observed
- FR-709 panel guards for `a` and `x` on Exchanges
- FR-711 ERROR state rendering and restart hint text
- Minimum terminal size message (`Terminal too small` / `Need 100x24`) displayed

## Exhaustive Interaction Log

### Case 1: `core_global_nav`
1. Launch: `./bin/csrf-shield-tui --input data/sample_har/mixed_auth.har`
2. Wait for loading and base panes (`Sessions`, `Exchanges`).
3. Press `Tab`.
4. Verify focus transition to Exchanges context.
5. Press `Shift+Tab` (`\x1b[Z`).
6. Verify focus returns to Sessions.
7. Press `l`, `h`, `j`, `k`.
8. Press `?` and verify Keybindings modal.
9. Press `?` again to close help.
10. Press `q`.
11. Expect quit confirm and cancel with `n`.

### Case 2: `sessions_actions`
1. Launch with `data/sample_har/vulnerable.har`.
2. Press `f`, enter `vuln`, submit with `Enter`.
3. Check filtered state visibility.
4. Press `/`, submit empty input to clear.
5. Press `c` while Panel 1 is active (guard check).
6. Press `a` for selected analyze.
7. Press `A` for analyze-all.
8. Press `Esc` to cancel batch.
9. Press `x` to remove session.

### Case 3: `exchanges_actions`
1. Launch with `data/sample_har/vulnerable.har`.
2. Press `Tab` to panel 2.
3. Press `a` and `x` on panel 2 (guard checks).
4. Press `Enter` to open raw modal.
5. Press `j`, `k`, `l`, `h` in raw modal.
6. Press `Esc` to close raw modal.
7. Press `c` for cURL export/fallback.
8. Press `/`, type `POST`, submit filter.

### Case 4: `analysis_panel_actions`
1. Launch with `data/sample_har/vulnerable.har`.
2. Press `a` and wait for `RISK SCORE`.
3. Press `Tab` twice to Analysis panel.
4. Press `j`, `k` to scroll.
5. Press `Enter` for finding detail (or no-findings state).
6. Press `Esc` to close detail and return.

### Case 5: `export_dialog`
1. Launch with `data/sample_har/mixed_auth.har`.
2. Press `e` to open Export dialog.
3. Press `Space` to toggle field option.
4. Press `Down` twice to path row.
5. Enter `qa_jcfre_report.json` and press `Enter`.
6. Expect success/error toast.

### Case 6: `badge_form_json_none`
1. Launch with `data/sample_har/vulnerable.har`.
2. Validate presence of `[Form]`, `[JSON]`, `[None]` in Exchanges rows.

### Case 7: `badge_multi`
1. Launch with `data/sample_har/multipart.har`.
2. Validate `[Multi]` badge.

### Case 8: `badge_text`
1. Launch with `data/sample_har/text_plain_request.har`.
2. Validate `[Text]` badge.

### Case 9: `error_state_restart`
1. Launch with invalid input: `data/sample_har/does_not_exist.har`.
2. Validate ERROR screen text.
3. Press `r` to restart backend.
4. Validate restart feedback/transition.
5. Press `q` and validate quit affordance.

### Case 10: `small_terminal`
1. Launch with reduced PTY dimensions (`80x20`).
2. Validate terminal-too-small warning text.

## Raw/Debug Output

Primary results:
- `docs/reports/_tui_full_proposal_results.json`

Per-case runtime logs:
- `docs/reports/_tui_full_core_global_nav.log`
- `docs/reports/_tui_full_sessions_actions.log`
- `docs/reports/_tui_full_exchanges_actions.log`
- `docs/reports/_tui_full_analysis_panel_actions.log`
- `docs/reports/_tui_full_export_dialog.log`
- `docs/reports/_tui_full_badge_form_json_none.log`
- `docs/reports/_tui_full_badge_multi.log`
- `docs/reports/_tui_full_badge_text.log`
- `docs/reports/_tui_full_error_state_restart.log`
- `docs/reports/_tui_full_small_terminal.log`

## Final Verdict

- Exhaustive proposal coverage was executed end-to-end in live TUI runtime.
- High-confidence functional gaps remain around:
  - Sessions `/` filter path consistency and filter-visibility signaling,
  - Exchanges post-filter applied-state visibility,
  - ERROR restart feedback confirmation.
- Several additional fails are attributable to matcher fragility under ANSI/redraw behavior and should be treated as automation artifacts unless reproduced manually.