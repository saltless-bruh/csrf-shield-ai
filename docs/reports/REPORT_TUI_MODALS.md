# TUI Exhaustive UI Diagnostics Report

## Feature/Scenario Tested
Interactive behavior and rendering viability of the TUI modal systems: Help Keybindings (`<?>`), Filter Input (`<f>`), and Export Dialog (`<e>`).

## Reference Document
`CLI_TUI_PROPOSAL.md` (Specifically §4 Layout, §7 Modals & Popups, and the Mockups showing overlaid modals)

## Expected vs. Actual Behavior

### 1. Help Modal (`<?>`)
*   **Expected Behavior:** Pressing `<?>` opens an overlapping center-screen modal displaying a table of context-aware keybindings.
*   **Actual Behavior:** The global UI locks up (as `isAnyModalOpen` prevents further base-panel interaction), but the Help table is entirely invisible. 
*   **Deep Dive / Root Cause:** Z-Index collision. In Z-layered terminal forks (like `jesseduffield/gocui` used here), layout views drawn with elevated overlap flags force themselves over standard overlays. `PanelAnalysis` is generated with Z-index `gocui.TOP`, while `help` is created with a default `0` overlap. Consequently, `PanelAnalysis` eternally renders on top of the right half of the Help menu. Additionally, without an explicit `g.SetViewOnTop("help")` call, the re-evaluating `layout` loop sinks the newly created popup behind standard layers.

### 2. Output Export Dialog (`<e>`)
*   **Expected Behavior:** A centered form displaying Format types, Scope, and a filepath string input, navigated via arrow keys or intuitive typing.
*   **Actual Behavior:** The dialog appears partially but feels strictly un-interactable. Keyboard input appears ignored.
*   **Deep Dive / Root Cause:** 
    *   **Z-fighting:** Similar to the Help popup, the right half of the Export modal falls underneath the `PanelAnalysis` component, severing its visual integrity. 
    *   **Ghost Keyboard Bindings:** The export keys are rigorously hardcoded to `<Tab>` (cycle index) and `<Space>` (toggle button) within `export.go`. Arrow-key integration is omitted entirely. Because the user is not warned of these restrictive bindings, they naturally attempt to use `j/k` or `Arrows`, resulting in what feels like an unresponsive freeze.
    *   **Typing Mask:** When focused on the `Path` field, standard alphanumeric typing appears invisible natively due to the global `g.Cursor = false` mask.

### 3. Filter Table Dialog (`<f>`)
*   **Expected Behavior:** A centered prompt to dynamically text-filter the active panel. A blinking text cursor should denote active input context.
*   **Actual Behavior:** Opens a blank prompt that provides zero feedback when typed into.
*   **Deep Dive / Root Cause:** The TUI engine instantiates the UI thread with the cursor completely disabled globally (`g.Cursor = false` at `app.go:146`). When the `filtermodal` triggers `modal.Editable = true`, the text handler captures user keystrokes into the buffer perfectly, but it never re-enables the cursor. This creates a "blind typing" experience that looks identical to a crashed UI state.

## Exhaustive Interaction Log

1.  **Launch TUI**: `./csrf-shield-tui --input traffic.har` (Success)
2.  **Trigger Help**: Pressed `<Shift>+<?>`
    *   *Result:* Base panels stopped responding to `j`/`k`. Help screen did not materialize over the Analysis pane.
    *   *Recovery:* Pressed `<Esc>` blind to escape the invisible modal.
3.  **Trigger Filter**: Pressed `<f>`
    *   *Result:* Blank filter bar appeared.
    *   *Action:* Typed `text`, no characters visually populated the insertion point (due to cursor kill rule).
    *   *Recovery:* Pressed `<Enter>`. Interface returned focus to Sessions.
4.  **Trigger Export**: Pressed `<e>` via Sessions pane.
    *   *Result:* Center box appeared. Right border cut off by Analysis layer.
    *   *Action:* Pressed arrow keys to navigate down to "Path". No response.
    *   *Action:* Pressed letter keys to type path. No response.
    *   *Discovery:* Attempted `<Tab>` -> visually jumped index. 

## Raw/Debug Output
*   **Go Code Path Traces:**
    *   `internal/ui/app.go` (Layout function, lines 212-225): `g.SetView(PanelAnalysis, ..., gocui.TOP)`
    *   `internal/ui/export.go` (line 46): `modal, err := g.SetView("exportmodal", ..., 0)`
    *   `internal/ui/app.go` (line 146): `g.Cursor = false`
    *   No dynamic cursor resets exist in `handleFilter()` or `handleFilterSubmit()` routines within `keybindings.go`.

## Testing Verdict
TUI modals suffer from heavy structural Z-indexing collisions (`gocui.TOP` vs `0`) combined with aggressive global application parameters (suppressed cursors) that cripple end-user workflows, demanding code refactoring to explicitly push overlays using `g.SetViewOnTop(...)` and conditionally re-enable `g.Cursor`.