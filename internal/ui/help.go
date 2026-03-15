package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"
)

// handleHelp opens the keybindings help modal.
// Ref: CLI_TUI_PROPOSAL.md §7.1
func (a *App) handleHelp(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	maxX, maxY := g.Size()
	helpV, err := g.SetView("help", maxX/6, 1, maxX*5/6, maxY-2, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	helpV.Title = " Keybindings "
	helpV.Clear()

	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "  --- Global ------------------------------------------------")
	fmt.Fprintln(helpV, "  Tab / Shift+Tab     Cycle panel focus")
	fmt.Fprintln(helpV, "  h / j / k / l       Vim-style navigation")
	fmt.Fprintln(helpV, "  f or /              Filter sessions/exchanges")
	fmt.Fprintln(helpV, "  e                   Export report")
	fmt.Fprintln(helpV, "  ?                   This help menu")
	fmt.Fprintln(helpV, "  q                   Quit (or close modal)")
	fmt.Fprintln(helpV, "  Esc                 Close modal / cancel batch")
	fmt.Fprintln(helpV, "  r                   Restart backend (ERROR only)")
	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "  --- Sessions Panel ----------------------------------------")
	fmt.Fprintln(helpV, "  a                   Analyze selected session")
	fmt.Fprintln(helpV, "  A (Shift+A)         Analyze all sessions")
	fmt.Fprintln(helpV, "  x                   Remove session from workspace")
	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "  --- Exchanges Panel ---------------------------------------")
	fmt.Fprintln(helpV, "  Enter               View raw HTTP request/response")
	fmt.Fprintln(helpV, "  c                   Copy as cURL to clipboard")
	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "  --- Analysis Panel ----------------------------------------")
	fmt.Fprintln(helpV, "  Enter               View finding detail")
	fmt.Fprintln(helpV, "  j / k               Scroll analysis content")
	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "  Note: All keys except Esc/Enter are suspended during")
	fmt.Fprintln(helpV, "  text input (filter, export path).")
	fmt.Fprintln(helpV, "")
	fmt.Fprintln(helpV, "                        [ Esc to close ]")

	if _, err := g.SetCurrentView("help"); err != nil {
		return err
	}
	g.SetViewOnTop("help")
	return nil
}
