# TUI/CLI External HAR Validation Report (IRL Corpora)

## Feature/Scenario Tested
Validation of CSRF Shield AI behavior against third-party HAR datasets requested by user:
- Source A: `https://github.com/haralyzer/haralyzer/tree/master/tests/data`
- Source B: `https://github.com/readmeio/oas/tree/main/packages/har-examples`

Scope executed:
- Bulk non-interactive analysis compatibility run (`python -m src.main analyze`) across all external samples.
- Live TUI runtime witness check (`bin/csrf-shield-tui`) with real loaded external HAR content and quit flow.
- Failure classification for malformed/partial HAR structures.

## Reference Document
- `docs/proposal/CLI_TUI_PROPOSAL.md`
- `README.md` (runtime command expectations)
- Existing QA baselines under `docs/reports/REPORT_TUI_*.md`

## Expected vs. Actual Behavior

### Expected
1. Program accepts valid HAR 1.2 inputs from external creators.
2. CLI analysis should complete with report artifacts for valid files.
3. TUI should launch, render panels, and allow quit confirmation flow.
4. Invalid/malformed HAR should fail safely with explicit error.

### Actual
1. External corpus ingestion succeeded from both requested repositories.
- `haralyzer`: 14 direct `.har` files discovered.
- `oas`: no direct `.har` files in repo tree; examples provided as TypeScript fixtures (`*.har.ts`).
- Fixtures were converted to concrete `.har` JSON payloads via `npx tsx` import/serialize pipeline, yielding 20 testable HAR files.

2. CLI matrix results:
- Total files tested: 34
- Successful analyses with parseable JSON report output: 31
- Failed/incomplete: 3
- By source:
  - `haralyzer`: 11/14 success
  - `oas_converted`: 20/20 success

3. TUI witness (real runtime) succeeded on external HAR:
- Confirmed startup/loading screen, populated `Sessions` panel, and quit confirmation modal (`Quit CSRF Shield AI? [y/n]`) on a live external sample (`haralyzer` corpus).
- Evidence captured with terminal size >= `100x24` to satisfy proposal minimum and avoid false negatives.

4. Failures found in external matrix:
- `haralyzer/tests/data/single_entry.har`: hard failure (exit code 1), explicit parser error: `Missing required 'log' key in HAR data`.
- `haralyzer/tests/data/missing_page.har`: command exits 0 and says analysis complete, but no output report file generated.
- `haralyzer/tests/data/missing_pageref.har`: command exits 0 and says analysis complete, but no output report file generated.

## Exhaustive Interaction Log

### A. Source acquisition and corpus preparation
1. Cloned external repositories into `/tmp/csrf_irl_har/`.
2. Enumerated direct HAR files:
- `/tmp/csrf_irl_har/haralyzer/tests/data/*.har` -> 14 files.
3. Inspected OAS path and confirmed fixtures are TypeScript files (`*.har.ts`), not raw HAR files.
4. Converted OAS fixtures to HAR JSON files:
- Input: `/tmp/csrf_irl_har/oas/packages/har-examples/src/*.har.ts`
- Output: `/tmp/csrf_irl_har/oas_converted/*.har`
- Converted count: 20

### B. CLI compatibility matrix execution
1. Activated project venv.
2. For each of 34 external HAR files, executed:
- `python -m src.main analyze --input <file> --output <unique-path> --format json`
3. Collected per-case:
- process exit code
- stderr/stdout tails
- report existence and parseability
4. Stored aggregate artifact:
- `docs/reports/_tui_irl_har_cli_matrix_2026-03-15.json`

### C. Live TUI witness on external data
1. Spawned real TUI with external HAR in PTY dimension `40x140` (meets minimum width/height constraint).
2. Observed runtime render states in capture:
- `CSRF Shield AI v1.0`
- loading panel
- `Sessions` pane with external host/session rows
3. Triggered quit flow with `q` then `y`.
4. Captured witness log:
- `docs/reports/_tmp_dim_test.log`

## Raw/Debug Output

Primary artifacts:
- `docs/reports/_tui_irl_har_cli_matrix_2026-03-15.json`
- `docs/reports/_tmp_dim_test.log`

Representative success evidence (external corpora):
- `haralyzer/chrome.har`: exit 0, report emitted, parsed.
- `oas_converted/application-json.har`: exit 0, report emitted, parsed.

Representative failure evidence:
- `haralyzer/single_entry.har`: exit 1, `Missing required 'log' key in HAR data`.
- `haralyzer/missing_page.har`: exit 0, no report artifact emitted.
- `haralyzer/missing_pageref.har`: exit 0, no report artifact emitted.

## Findings Summary
- Total issues found: 3
- Severity breakdown:
  - Major: 2 (`missing_page.har`, `missing_pageref.har` success-status with missing output artifact)
  - Expected invalid-input failure: 1 (`single_entry.har` malformed structure)

## Verdict
CSRF Shield AI functions correctly against the vast majority of third-party HAR samples from both requested sources, including all converted OAS HAR examples and most `haralyzer` samples. The primary gap is inconsistent CLI success semantics for two malformed/partial HAR files where analysis reports success but does not materialize an output file.

---

## Fixes Implemented (2026-03-15 Retest)

### Code changes
1. Updated report generation behavior for empty-flow parses in `src/pipeline.py`.
- Previous behavior: when `0` flows were reconstructed, `_generate_reports()` returned early and emitted no report artifact.
- New behavior: when `output_dir` is provided and `0` flows are present, pipeline now emits deterministic JSON/HTML reports with:
  - empty findings list
  - low-risk baseline score (`0`)
  - valid report schema

2. Added regression tests to prevent recurrence:
- `tests/test_cli.py`: `test_analyze_empty_flow_har_still_writes_report`
- `tests/test_integration.py`: `test_empty_flow_har_still_generates_reports`

### Validation executed after fix
1. Targeted tests:
- `python -m pytest tests/test_cli.py tests/test_integration.py -q`
- Result: `26 passed`

2. External failing-case replay:
- `haralyzer/tests/data/missing_page.har` now writes output report.
- `haralyzer/tests/data/missing_pageref.har` now writes output report.

3. Full external corpus retest (34 files):
- Artifact: `docs/reports/_tui_irl_har_cli_matrix_retest_2026-03-15.json`
- Summary:
  - Total: `34`
  - Passed: `33`
  - Failed: `1`
  - `haralyzer`: `13/14` passed
  - `oas_converted`: `20/20` passed

### Remaining failure
- `haralyzer/tests/data/single_entry.har`
  - Exit code: `1`
  - Reason: `Missing required 'log' key in HAR data`
  - Status: expected invalid input hard-fail (correct behavior)