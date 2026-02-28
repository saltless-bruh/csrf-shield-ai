package ui

import (
	"encoding/json"
	"fmt"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// setupKeybindings configures all global and context-specific keybindings.
// Ref: CLI_TUI_PROPOSAL.md §6
func (a *App) setupKeybindings(g *gocui.Gui) error {
	bindings := []struct {
		view string
		key  interface{}
		mod  gocui.Modifier
		fn   func(*gocui.Gui, *gocui.View) error
	}{
		{"", 'q', gocui.ModNone, a.handleQuit},
		{"", gocui.KeyTab, gocui.ModNone, a.handleTab},
		{"", '?', gocui.ModNone, a.handleHelp},
		{"", 'e', gocui.ModNone, a.handleExport},
		{"", gocui.KeyEsc, gocui.ModNone, a.handleEsc},
		{"", 'r', gocui.ModNone, a.handleRestart},
		{"", 'j', gocui.ModNone, a.handleDown},
		{"", 'k', gocui.ModNone, a.handleUp},
		{"", 'h', gocui.ModNone, a.handlePrevPanel},
		{"", 'l', gocui.ModNone, a.handleTab},
		{"", gocui.KeyArrowDown, gocui.ModNone, a.handleDown},
		{"", gocui.KeyArrowUp, gocui.ModNone, a.handleUp},
		{"", 'a', gocui.ModNone, a.handleAnalyze},
		{"", 'A', gocui.ModNone, a.handleAnalyzeAll},
		{"", 'x', gocui.ModNone, a.handleRemove},
	}

	for _, b := range bindings {
		if err := g.SetKeybinding(b.view, b.key, b.mod, b.fn); err != nil {
			return err
		}
	}
	return nil
}

// --- Handler implementations ---

func (a *App) handleQuit(g *gocui.Gui, v *gocui.View) error {
	return gocui.ErrQuit
}

func (a *App) handleTab(g *gocui.Gui, v *gocui.View) error {
	a.activePanel = (a.activePanel + 1) % 3
	return nil
}

func (a *App) handlePrevPanel(g *gocui.Gui, v *gocui.View) error {
	a.activePanel = (a.activePanel + 2) % 3
	return nil
}

func (a *App) handleEsc(g *gocui.Gui, v *gocui.View) error {
	// Close help modal if open.
	if err := g.DeleteView("help"); err == nil {
		return nil
	}

	// Cancel analyze_all if running.
	if a.state == models.StateAnalyzing {
		go func() {
			_, _ = a.client.Call("cancel", map[string]interface{}{})
			a.mu.Lock()
			a.state = models.StateBrowsing
			a.engineStatus = "Idle"
			a.mu.Unlock()
			a.showToast("Analysis cancelled")
		}()
	}
	return nil
}

func (a *App) handleRestart(g *gocui.Gui, v *gocui.View) error {
	if a.state != models.StateError {
		return nil
	}
	a.setError("Restart not yet implemented. Please quit and re-launch.")
	return nil
}

func (a *App) handleDown(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	switch a.activePanel {
	case PanelIDSessions:
		if a.selectedIdx < len(a.flows)-1 {
			a.selectedIdx++
			a.exchIdx = 0
		}
	case PanelIDExchanges:
		if a.selectedIdx < len(a.flows) {
			if analysis, ok := a.analyses[a.flows[a.selectedIdx].SessionID]; ok {
				if a.exchIdx < len(analysis.Results)-1 {
					a.exchIdx++
				}
			}
		}
	}
	return nil
}

func (a *App) handleUp(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	switch a.activePanel {
	case PanelIDSessions:
		if a.selectedIdx > 0 {
			a.selectedIdx--
			a.exchIdx = 0
		}
	case PanelIDExchanges:
		if a.exchIdx > 0 {
			a.exchIdx--
		}
	}
	return nil
}

func (a *App) handleAnalyze(g *gocui.Gui, v *gocui.View) error {
	flow := a.selectedFlow()
	if flow == nil || a.state == models.StateAnalyzing {
		return nil
	}

	a.mu.Lock()
	a.state = models.StateAnalyzing
	a.engineStatus = "Analyzing..."
	a.mu.Unlock()

	go func() {
		resp, err := a.client.Call("analyze_flow", map[string]interface{}{
			"session_id": flow.SessionID,
		})

		a.mu.Lock()
		a.state = models.StateBrowsing
		a.engineStatus = "Idle"
		a.mu.Unlock()

		if err != nil {
			a.showToast(fmt.Sprintf("Error: %v", err))
			return
		}
		if resp.Error != nil {
			a.showToast(fmt.Sprintf("Error: %s", resp.Error.Message))
			return
		}

		analysis := parseAnalysis(resp.Result)
		a.mu.Lock()
		a.analyses[flow.SessionID] = analysis
		a.mu.Unlock()

		a.showToast(fmt.Sprintf("Analysis complete: %d/100 %s",
			analysis.Summary.RiskScore, analysis.Summary.RiskLevel))

		g.Update(func(g *gocui.Gui) error { return nil })
	}()

	return nil
}

func (a *App) handleAnalyzeAll(g *gocui.Gui, v *gocui.View) error {
	if a.state == models.StateAnalyzing {
		return nil
	}

	a.mu.Lock()
	a.state = models.StateAnalyzing
	a.engineStatus = "Analyzing all..."
	a.mu.Unlock()

	go func() {
		resp, err := a.client.Call("analyze_all", map[string]interface{}{})

		a.mu.Lock()
		a.state = models.StateBrowsing
		a.engineStatus = "Idle"
		a.mu.Unlock()

		if err != nil {
			a.showToast(fmt.Sprintf("Error: %v", err))
			return
		}

		// Fetch results for all flows.
		for _, flow := range a.flows {
			r, err := a.client.Call("get_results", map[string]interface{}{
				"session_id": flow.SessionID,
			})
			if err == nil && r.Error == nil {
				analysis := parseAnalysis(r.Result)
				a.mu.Lock()
				a.analyses[flow.SessionID] = analysis
				a.mu.Unlock()
			}
		}

		status := "ok"
		if resp != nil && resp.Result != nil {
			if s, ok := resp.Result["status"].(string); ok {
				status = s
			}
		}

		if status == "cancelled" {
			a.showToast("Analysis cancelled")
		} else {
			a.showToast("All sessions analyzed")
		}

		g.Update(func(g *gocui.Gui) error { return nil })
	}()

	return nil
}

func (a *App) handleRemove(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if len(a.flows) == 0 || a.selectedIdx >= len(a.flows) {
		return nil
	}

	removed := a.flows[a.selectedIdx]
	a.flows = append(a.flows[:a.selectedIdx], a.flows[a.selectedIdx+1:]...)
	delete(a.analyses, removed.SessionID)

	if a.selectedIdx >= len(a.flows) && a.selectedIdx > 0 {
		a.selectedIdx--
	}

	sid := removed.SessionID
	if len(sid) > 7 {
		sid = sid[:7]
	}
	go a.showToast(fmt.Sprintf("Session %s removed", sid))
	return nil
}

func (a *App) handleHelp(g *gocui.Gui, v *gocui.View) error {
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
	fmt.Fprintln(helpV, "  e                   Export report")
	fmt.Fprintln(helpV, "  ?                   This help menu")
	fmt.Fprintln(helpV, "  q                   Quit")
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
	fmt.Fprintln(helpV, "                        [ Esc to close ]")

	if _, err := g.SetCurrentView("help"); err != nil {
		return err
	}
	return nil
}

func (a *App) handleExport(g *gocui.Gui, v *gocui.View) error {
	flow := a.selectedFlow()
	if flow == nil {
		a.showToast("No session selected")
		return nil
	}

	sid := flow.SessionID
	if len(sid) > 7 {
		sid = sid[:7]
	}

	go func() {
		path := fmt.Sprintf("%s_report.json", sid)
		resp, err := a.client.Call("export_report", map[string]interface{}{
			"format":     "json",
			"scope":      "selected",
			"session_id": flow.SessionID,
			"path":       path,
		})
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
			if sb, ok := resp.Result["size_bytes"].(float64); ok {
				sizeBytes = int(sb)
			}
		}
		a.showToast(fmt.Sprintf("Exported to %s (%.1f KB)", path, float64(sizeBytes)/1024))
		g.Update(func(g *gocui.Gui) error { return nil })
	}()

	return nil
}

// parseAnalysis extracts SessionAnalysis from IPC result map.
func parseAnalysis(result map[string]interface{}) *models.SessionAnalysis {
	data, err := json.Marshal(result)
	if err != nil {
		return nil
	}
	var analysis models.SessionAnalysis
	if err := json.Unmarshal(data, &analysis); err != nil {
		return nil
	}
	return &analysis
}
