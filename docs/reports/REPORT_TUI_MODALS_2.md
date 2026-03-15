# TUI Exhaustive UI Diagnostics Report - V2 (Post-Patch Validation)

## Feature/Scenario Tested
Interactive behavior, text input viability, and layout of the TUI modal systems (Help `<?>`, Filter `<f>`, and Export `<e>`) after the initial regression patches.

## Reference Document
`CLI_TUI_PROPOSAL.md` (Specifically §4 Layout, §7 Modals & Popups)

## Expected vs. Actual Behavior

### 1. Help Modal Constraints (Resolved)
*   **Expected:** Renders above all other panes without clipping.
*   **Actual:** Validated. Z-index `0` on base panels and `g.SetViewOnTop("help")` adequately fixes the Z-depth clipping issue.

### 2. Global Keybinding Bleed / Discarded Keystrokes (CRITICAL NEW BUG)
*   **Expected Behavior:** When typing inside an active `<f>` Filter or `<e>` Export path input, the user must be able to type standard alphanumeric characters (e.g., "ajax_req.json").
*   **Actual Behavior:** The user is physically blocked from typing certain letters (`h`, `j`, `k`, `l`, `q`, `e`, `a`, `A`, `x`, `c`, `f`, `r`). Typing `q` forcefully closes the modal.
*   **Deep Dive / Root Cause:** The codebase relies heavily on global `""` keybindings (e.g., `{"", 'j', gocui.ModNone, a.handleDown}`). In `gocui`, if a bound key is pressed, it evaluates the handler prior to passing it to the `Editor`. Because handlers like `handleDown` or `handleExport` detect `isAnyModalOpen == true` and gracefully return `nil` (instead of propagating an error or unrecognized state), `gocui` assumes the event was successfully handled and *discards the keystroke*. Furthermore, the `handleQuit` (mapped globally to `q`) actively iterates over open modals and `DeleteView`s them! Therefore, entering any path/filter string that contains these letters results in corrupted input or immediate modal termination.

### 3. Orphaned Hardware Cursors in Export Modal
*   **Expected Behavior:** Re-enabling `g.Cursor = true` should yield a blinking terminal cursor exactly at the end of the input string inside "Path: ".
*   **Actual Behavior:** Two pointers exist simultaneously causing visual confusion. A static ASCII underscore (`_`) exists inherently in the text view, while the actual blinking hardware terminal cursor spawns at the bottom line of the modal box.
*   **Deep Dive / Root Cause:** `export.go` uses `v.Clear()` and `fmt.Fprintf` to manually redraw the entire modal content during every arbitrary keystroke rather than relying on `gocui`'s native Editor buffer. Because `v.SetCursor(x, y)` is never updated to map to the strict coordinate of the "Path: " input line, `gocui` drops the hardware cursor at the end of the `fmt.Fprintf` byte stream, leaving it dangling at the bottom of the dialogue window far away from the text input field.

## Exhaustive Interaction Log

1.  **Launch TUI**: `./csrf-shield-tui` (Simulated environment)
2.  **Trigger Filter (`<f>`)**:
    *   *Action:* Attempted to type the string `"auth_req"`.
    *   *Result:* Only `"uth_"` appeared. Keystrokes `a`, `r`, and `q` were instantly consumed by `handleAnalyze`, `handleRestart`, and `handleQuit`.
    *   *Result:* Pressing `q` immediately dismissed the active filter box entirely, completely aborting the text workflow.
3.  **Trigger Export (`<e>`)**:
    *   *Action:* Used newly added `<ArrowDown>` to reach "Path".
    *   *Result:* Navigated successfully (prior `Tab` lock fixed).
    *   *Action:* Attempted to type `"file.json"`.
    *   *Result:* Only `"il.json"` appeared. The `f` key was stolen by the global `handleFilter` binding. `e` was stolen by `handleExport` binding. 
    *   *Visual Observation:* The hardware cursor was blinking near `[ Enter to Export ]` rather than on the `Path:` line, while a fake `_` sat on the Path line.

## Raw/Debug Output
*   `internal/ui/keybindings.go`: Broad assignments to `""` view override alphanumeric `Editor` inserts.
*   `internal/ui/confirm.go:28`: `handleQuit` actively catches the "q" stroke during typing and triggers `err := g.DeleteView(modal)`.

## Testing Verdict
While visual overlapping issues were patched, the interface remains practically unusable due to **Global Keybinding Bleeds** stealing half of the alphabet during typing, and improper un-targeted **Hardware Cursor Placement**. Recommend stripping global alphanumeric mappings `""` in favor of Panel-specific routing (`PanelSessions`, `PanelExchanges`, etc.), and establishing explicit `v.SetCursor(x, y)` coordinates for the Export modal string input.
