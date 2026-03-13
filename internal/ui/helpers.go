package ui

import (
	"strings"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// viewHeight returns the inner height of a gocui view (rows available for content).
func viewHeight(v *gocui.View) int {
	_, h := v.Size()
	return h
}

// adjustScroll ensures the selected index is visible within the scroll window.
// Returns the new scroll offset. Keeps the selection centered when possible.
func adjustScroll(selected, offset, height, total int) int {
	if total <= height {
		return 0
	}
	// Scroll down if selection is below visible area.
	if selected >= offset+height {
		offset = selected - height + 1
	}
	// Scroll up if selection is above visible area.
	if selected < offset {
		offset = selected
	}
	// Clamp.
	if offset > total-height {
		offset = total - height
	}
	if offset < 0 {
		offset = 0
	}
	return offset
}

// truncate shortens s to at most n runes, appending "..." if trimmed (requires n >= 4).
func truncate(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	if n < 4 {
		return string(runes[:n])
	}
	return string(runes[:n-3]) + "..."
}

// titleWithCounter composes a gocui panel title with a right-aligned position counter.
// The counter is placed flush-right within the panel border.
// Ref: CLI_TUI_PROPOSAL.md §9.2 — "[N/M] at the right edge of the panel border".
func titleWithCounter(left, right string, viewWidth int) string {
	pad := viewWidth - len(left) - len(right)
	if pad < 1 {
		pad = 1
	}
	return left + strings.Repeat(" ", pad) + right
}

// severityBadge returns a short label for a finding severity.
func severityBadge(sev string) string {
	switch sev {
	case models.SevCritical:
		return "[!!]"
	case models.SevHigh:
		return "[!]"
	case models.SevMedium:
		return "[~]"
	case models.SevLow:
		return "[*]"
	case models.SevInfo:
		return "[i]"
	default:
		return "[-]"
	}
}

// renderStatusBar writes the one-line status bar content.
// Shows per-panel keybinding hints on the left and engine status on the right.
// Ref: CLI_TUI_PROPOSAL.md §5.4
// NOTE: Moved to statusbar.go
