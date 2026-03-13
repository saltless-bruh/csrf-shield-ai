package ui

import (
	"fmt"
	"strings"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// showFindingDetailModal displays finding details in a structured modal.
// Ref: CLI_TUI_PROPOSAL.md §7.4
func (a *App) showFindingDetailModal(g *gocui.Gui) error {
	analysis := a.selectedAnalysis()
	if analysis == nil || len(analysis.Results) == 0 {
		a.showToast("No analysis results — analyze session first")
		return nil
	}

	// Resolve the currently selected exchange and find its analysis result.
	flow := a.selectedFlow()
	if flow == nil {
		return nil
	}
	a.mu.Lock()
	exchIdx := a.exchIdx
	exchanges, hasExchanges := a.flowExchanges[flow.SessionID]
	a.mu.Unlock()

	var result *models.ExchangeResult
	if hasExchanges && exchIdx < len(exchanges) {
		ex := exchanges[exchIdx]
		for i, r := range analysis.Results {
			if r.HTTPMethod == ex.RequestMethod && strings.HasSuffix(ex.RequestURL, r.Endpoint) {
				result = &analysis.Results[i]
				break
			}
		}
	}
	// Fall back to first result if no match (e.g. Panel 3 focused without Panel 2 nav).
	if result == nil && len(analysis.Results) > 0 {
		result = &analysis.Results[0]
	}
	if result == nil {
		return nil
	}

	if len(result.Findings) == 0 {
		a.showToast("No findings for this exchange")
		return nil
	}

	maxX, maxY := g.Size()
	modal, err := g.SetView("findingmodal", maxX/6, 1, maxX*5/6, maxY-2, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	// Reset scroll every time the modal is (re-)opened.
	a.mu.Lock()
	a.findingScroll = 0
	a.mu.Unlock()
	modal.Title = " Finding Detail "
	modal.Wrap = true
	modal.Clear()

	const sep = "  ──────────────────────────────────────────────────────"
	const sepBig = "  ═══════════════════════════════════════════════════════"

	// Resolve exchange reference string for Evidence block.
	exchangeRef := ""
	if hasExchanges && exchIdx < len(exchanges) {
		ex := exchanges[exchIdx]
		exchangeRef = fmt.Sprintf("Exchange: %s %s (%d)", ex.RequestMethod, ex.RequestURL, ex.ResponseStatus)
	}

	for i, f := range result.Findings {
		if i > 0 {
			fmt.Fprintln(modal, sepBig)
		}
		// Header: severity badge + rule ID + rule name.
		fmt.Fprintf(modal, "\n  %s %s | %s\n", severityBadge(f.Severity), f.RuleID, f.RuleName)
		fmt.Fprintf(modal, "  Severity: %-10s  Module: Static Analysis\n", f.Severity)
		fmt.Fprintln(modal, sep)
		// Description block.
		fmt.Fprintln(modal, "  Description:")
		fmt.Fprintf(modal, "    %s\n", f.Description)
		fmt.Fprintln(modal, sep)
		// Evidence block.
		fmt.Fprintln(modal, "  Evidence:")
		if exchangeRef != "" {
			fmt.Fprintf(modal, "    %s\n", exchangeRef)
		}
		fmt.Fprintf(modal, "    %s\n", f.Evidence)
		fmt.Fprintln(modal, sep)
		// Recommendations block.
		fmt.Fprintln(modal, "  Recommendations:")
		for j, rec := range result.Recommendations {
			fmt.Fprintf(modal, "    %d. %s\n", j+1, rec)
		}
	}
	fmt.Fprintf(modal, "\n  j/k scroll  •  Esc or q to close\n")

	// Apply scroll position.
	a.mu.Lock()
	scroll := a.findingScroll
	a.mu.Unlock()
	_ = modal.SetOrigin(0, scroll)

	if _, err := g.SetCurrentView("findingmodal"); err != nil {
		return err
	}
	return nil
}

// handleFindingScrollDown scrolls the finding detail modal down.
func (a *App) handleFindingScrollDown(g *gocui.Gui, v *gocui.View) error {
	ox, oy := v.Origin()
	_ = v.SetOrigin(ox, oy+1)
	a.mu.Lock()
	a.findingScroll = oy + 1
	a.mu.Unlock()
	return nil
}

// handleFindingScrollUp scrolls the finding detail modal up.
func (a *App) handleFindingScrollUp(g *gocui.Gui, v *gocui.View) error {
	ox, oy := v.Origin()
	if oy > 0 {
		_ = v.SetOrigin(ox, oy-1)
		a.mu.Lock()
		a.findingScroll = oy - 1
		a.mu.Unlock()
	}
	return nil
}

// handleFindingClose closes the finding detail modal and returns focus.
func (a *App) handleFindingClose(g *gocui.Gui, v *gocui.View) error {
	_ = g.DeleteView("findingmodal")
	a.mu.Lock()
	a.findingScroll = 0
	a.mu.Unlock()
	panelName := PanelSessions
	switch a.activePanel {
	case PanelIDExchanges:
		panelName = PanelExchanges
	case PanelIDAnalysis:
		panelName = PanelAnalysis
	}
	_, err := g.SetCurrentView(panelName)
	return err
}
