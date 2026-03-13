package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"
)

// handleQuit handles the 'q' key — closes any open modal first, then shows
// the quit confirmation dialog.
// Ref: CLI_TUI_PROPOSAL.md §6
func (a *App) handleQuit(g *gocui.Gui, v *gocui.View) error {
	// If any modal is open, close it instead of quitting (§7).
	panelName := PanelSessions
	switch a.activePanel {
	case PanelIDExchanges:
		panelName = PanelExchanges
	case PanelIDAnalysis:
		panelName = PanelAnalysis
	}
	// Close raw modal pair together (M2).
	reqOk := g.DeleteView("rawmodal_req") == nil
	respOk := g.DeleteView("rawmodal_resp") == nil
	if reqOk || respOk {
		g.SetCurrentView(panelName)
		return nil
	}
	for _, modal := range []string{"help", "findingmodal", "exportmodal", "filtermodal"} {
		if err := g.DeleteView(modal); err == nil {
			g.SetCurrentView(panelName)
			return nil
		}
	}

	// No modal open — show quit confirmation.
	maxX, maxY := g.Size()
	modal, err := g.SetView("quitmodal", maxX/2-15, maxY/2-2, maxX/2+15, maxY/2+2, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	modal.Title = " Quit "
	modal.Clear()
	fmt.Fprintf(modal, "\n  Quit CSRF Shield AI? [y/n]")

	if _, err := g.SetCurrentView("quitmodal"); err != nil {
		return err
	}
	return nil
}

// handleConfirmQuit exits the application.
func (a *App) handleConfirmQuit(g *gocui.Gui, v *gocui.View) error {
	return gocui.ErrQuit
}

// handleCancelQuit closes the quit confirmation dialog and returns focus.
func (a *App) handleCancelQuit(g *gocui.Gui, v *gocui.View) error {
	_ = g.DeleteView("quitmodal")
	// Return focus to active panel.
	panelName := PanelSessions
	switch a.activePanel {
	case PanelIDExchanges:
		panelName = PanelExchanges
	case PanelIDAnalysis:
		panelName = PanelAnalysis
	}
	g.SetCurrentView(panelName)
	return nil
}
