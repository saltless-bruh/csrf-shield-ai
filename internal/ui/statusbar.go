package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"
)

// renderStatusBar writes the one-line status bar content.
// Shows per-panel keybinding hints on the left and engine status on the right.
// Ref: CLI_TUI_PROPOSAL.md §5.4
func (a *App) renderStatusBar(g *gocui.Gui) {
	v, err := g.View(PanelStatus)
	if err != nil {
		return
	}
	v.Clear()

	a.mu.Lock()
	status := a.engineStatus
	toast := a.toastMsg
	panel := a.activePanel
	a.mu.Unlock()

	engineLabel := "[ML: " + status + "]"

	if toast != "" {
		fmt.Fprintf(v, "  %-70s  %s", toast, engineLabel)
		return
	}

	var hints string
	switch panel {
	case PanelIDSessions:
		hints = "<a> analyze  <A> analyze all  <f> filter  <x> remove  <e> export  <q> quit  <?> help"
	case PanelIDExchanges:
		hints = "<Enter> view raw  <c> copy cURL  <f> filter  <e> export  <q> quit  <?> help"
	case PanelIDAnalysis:
		hints = "<Enter> finding detail  <j/k> scroll  <e> export  <q> quit  <?> help"
	}
	fmt.Fprintf(v, "  %-70s  %s", hints, engineLabel)
}
