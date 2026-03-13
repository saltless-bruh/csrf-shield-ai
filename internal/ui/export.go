package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"
)

// drawExportModal renders the export modal content.
// Ref: CLI_TUI_PROPOSAL.md §7.3
func (a *App) drawExportModal(v *gocui.View) {
	v.Clear()

	// Format Toggle
	formatStr := "  Format:   "
	if a.exportFormat == "json" {
		formatStr += "(*) JSON    ( ) HTML\n"
	} else {
		formatStr += "( ) JSON    (*) HTML\n"
	}
	if a.exportFocusIdx == 0 {
		formatStr = "\033[30;47m" + formatStr[:len(formatStr)-1] + "\033[0m\n" // Invert color for focus
	}

	// Scope Toggle
	scopeStr := "  Scope:    "
	if a.exportScope == "selected" {
		scopeStr += "(*) Selected session    ( ) All sessions\n"
	} else {
		scopeStr += "( ) Selected session    (*) All sessions\n"
	}
	if a.exportFocusIdx == 1 {
		scopeStr = "\033[30;47m" + scopeStr[:len(scopeStr)-1] + "\033[0m\n" // Invert color for focus
	}

	// Path Input
	pathStr := fmt.Sprintf("  Path:     %s\n", a.exportPath)
	if a.exportFocusIdx == 2 {
		pathStr = "\033[30;47m" + pathStr[:len(pathStr)-1] + "_\033[0m\n" // Invert color for focus + cursor
	}

	fmt.Fprintf(v, "\n%s%s\n%s\n", formatStr, scopeStr, pathStr)
	fmt.Fprintf(v, "           [ Enter to Export ]\n")
}

// handleExport opens the export report modal.
// Ref: CLI_TUI_PROPOSAL.md §7.3
func (a *App) handleExport(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	flow := a.selectedFlow()
	if flow == nil {
		a.showToast("No session selected")
		return nil
	}

	maxX, maxY := g.Size()
	modal, err := g.SetView("exportmodal", maxX/2-25, maxY/2-5, maxX/2+25, maxY/2+5, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	modal.Title = " Export Report "

	sid := flow.SessionID
	if len(sid) > 7 {
		sid = sid[:7]
	}

	a.mu.Lock()
	a.exportFocusIdx = 0
	a.exportFormat = "json"
	a.exportScope = "selected"
	a.exportPath = fmt.Sprintf("%s_report.json", sid)
	a.mu.Unlock()

	// Use custom editor to capture text input when Path is focused
	modal.Editable = true
	modal.Editor = gocui.EditorFunc(a.exportEditor)

	a.drawExportModal(modal)

	if _, err := g.SetCurrentView("exportmodal"); err != nil {
		return err
	}
	return nil
}

func (a *App) handleExportTab(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	a.exportFocusIdx = (a.exportFocusIdx + 1) % 3
	a.mu.Unlock()
	a.drawExportModal(v)
	return nil
}

func (a *App) handleExportSpace(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	if a.exportFocusIdx == 0 {
		if a.exportFormat == "json" {
			a.exportFormat = "html"
		} else {
			a.exportFormat = "json"
		}
	} else if a.exportFocusIdx == 1 {
		if a.exportScope == "selected" {
			a.exportScope = "all"
		} else {
			a.exportScope = "selected"
		}
	} else if a.exportFocusIdx == 2 {
		a.exportPath += " "
	}
	a.mu.Unlock()
	a.drawExportModal(v)
	return nil
}

func (a *App) handleExportBackspace(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	if a.exportFocusIdx == 2 && len(a.exportPath) > 0 {
		a.exportPath = a.exportPath[:len(a.exportPath)-1]
	}
	a.mu.Unlock()
	a.drawExportModal(v)
	return nil
}

func (a *App) exportEditor(v *gocui.View, key gocui.Key, ch rune, mod gocui.Modifier) {
	a.mu.Lock()
	if a.exportFocusIdx == 2 {
		if ch != 0 && mod == gocui.ModNone {
			a.exportPath += string(ch)
		}
	}
	a.mu.Unlock()
	a.drawExportModal(v)
}

// handleConfirmExport executes the export IPC call and notifies via toast.
// Ref: CLI_TUI_PROPOSAL.md §7.3
func (a *App) handleConfirmExport(g *gocui.Gui, v *gocui.View) error {
	flow := a.selectedFlow()
	if flow == nil {
		return nil
	}

	_ = g.DeleteView("exportmodal")
	// Return focus.
	panelName := PanelSessions
	switch a.activePanel {
	case PanelIDExchanges:
		panelName = PanelExchanges
	case PanelIDAnalysis:
		panelName = PanelAnalysis
	}
	g.SetCurrentView(panelName)

	a.mu.Lock()
	format := a.exportFormat
	scope := a.exportScope
	path := a.exportPath
	a.mu.Unlock()

	go func() {
		params := map[string]interface{}{
			"format": format,
			"scope":  scope,
			"path":   path,
		}
		if scope == "selected" {
			params["session_id"] = flow.SessionID
		}
		resp, err := a.client.Call("export_report", params)
		if err != nil {
			a.showToast(fmt.Sprintf("Export error: %v", err))
			return
		}
		if resp.Error != nil {
			a.showToast(fmt.Sprintf("Export error: %s", resp.Error.Message))
			return
		}

		sizeBytes := 0
		if resp.Result != nil {
			if rMap, ok := resp.Result.(map[string]interface{}); ok {
				if sb, ok := rMap["size_bytes"].(float64); ok {
					sizeBytes = int(sb)
				}
			}
		}
		a.showToast(fmt.Sprintf("Exported to %s (%.1f KB)", path, float64(sizeBytes)/1024))
		g.Update(func(g *gocui.Gui) error { return nil })
	}()

	return nil
}
