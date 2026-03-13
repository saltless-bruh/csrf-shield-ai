package ui

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/clipboard"
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
		{"", gocui.KeyBacktab, gocui.ModNone, a.handlePrevPanel},
		{"", '?', gocui.ModNone, a.handleHelp},
		{"", 'e', gocui.ModNone, a.handleExport},
		{"", gocui.KeyEsc, gocui.ModNone, a.handleEsc},
		{"", gocui.KeyEnter, gocui.ModNone, a.handleEnter},
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
		{"", 'c', gocui.ModNone, a.handleCopyCURL},
		{"quitmodal", 'y', gocui.ModNone, a.handleConfirmQuit},
		{"quitmodal", 'Y', gocui.ModNone, a.handleConfirmQuit},
		{"quitmodal", 'n', gocui.ModNone, a.handleCancelQuit},
		{"quitmodal", 'N', gocui.ModNone, a.handleCancelQuit},
		{"exportmodal", gocui.KeyEnter, gocui.ModNone, a.handleConfirmExport},
		{"exportmodal", gocui.KeyTab, gocui.ModNone, a.handleExportTab},
		{"exportmodal", gocui.KeySpace, gocui.ModNone, a.handleExportSpace},
		{"exportmodal", gocui.KeyBackspace, gocui.ModNone, a.handleExportBackspace},
		{"exportmodal", gocui.KeyBackspace2, gocui.ModNone, a.handleExportBackspace},
		{"", 'f', gocui.ModNone, a.handleFilter},
		{"", '/', gocui.ModNone, a.handleFilter},
		{"filtermodal", gocui.KeyEnter, gocui.ModNone, a.handleFilterSubmit},
		// Raw modal column keybindings (M2).
		{"rawmodal_req", 'j', gocui.ModNone, a.handleRawScrollDown},
		{"rawmodal_req", 'k', gocui.ModNone, a.handleRawScrollUp},
		{"rawmodal_req", 'h', gocui.ModNone, a.handleRawFocusLeft}, // boundary no-op (already leftmost)
		{"rawmodal_req", 'l', gocui.ModNone, a.handleRawFocusRight},
		{"rawmodal_req", gocui.KeyEsc, gocui.ModNone, a.handleRawClose},
		{"rawmodal_req", 'q', gocui.ModNone, a.handleRawClose},
		{"rawmodal_resp", 'j', gocui.ModNone, a.handleRawScrollDown},
		{"rawmodal_resp", 'k', gocui.ModNone, a.handleRawScrollUp},
		{"rawmodal_resp", 'h', gocui.ModNone, a.handleRawFocusLeft},
		{"rawmodal_resp", 'l', gocui.ModNone, a.handleRawFocusRight}, // boundary no-op (already rightmost)
		{"rawmodal_resp", gocui.KeyEsc, gocui.ModNone, a.handleRawClose},
		{"rawmodal_resp", 'q', gocui.ModNone, a.handleRawClose},
		// Finding detail modal — view-specific scroll and close.
		{"findingmodal", 'j', gocui.ModNone, a.handleFindingScrollDown},
		{"findingmodal", 'k', gocui.ModNone, a.handleFindingScrollUp},
		{"findingmodal", gocui.KeyEsc, gocui.ModNone, a.handleFindingClose},
		{"findingmodal", 'q', gocui.ModNone, a.handleFindingClose},
	}

	for _, b := range bindings {
		if err := g.SetKeybinding(b.view, b.key, b.mod, b.fn); err != nil {
			return err
		}
	}
	return nil
}

// --- Handler implementations ---

// handleQuit, handleConfirmQuit, handleCancelQuit are defined in confirm.go.

func (a *App) handleTab(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	a.mu.Lock()
	a.activePanel = (a.activePanel + 1) % 3
	a.analysisScroll = 0
	a.mu.Unlock()
	return nil
}

func (a *App) handlePrevPanel(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	a.mu.Lock()
	a.activePanel = (a.activePanel + 2) % 3
	a.analysisScroll = 0
	a.mu.Unlock()
	return nil
}

func (a *App) handleEsc(g *gocui.Gui, v *gocui.View) error {
	// Close any open modal.
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
	for _, modal := range []string{"help", "findingmodal", "quitmodal", "exportmodal", "filtermodal"} {
		if err := g.DeleteView(modal); err == nil {
			// A modal was closed — return focus to the active panel.
			if modal == "findingmodal" {
				a.mu.Lock()
				a.findingScroll = 0
				a.mu.Unlock()
			}
			g.SetCurrentView(panelName)
			return nil
		}
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
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.state != models.StateError {
		return nil
	}

	// Transition to loading, re-spawn backend.
	a.mu.Lock()
	a.state = models.StateLoading
	a.errorMsg = ""
	a.engineStatus = "Idle"
	a.mu.Unlock()

	// Stop old backend and re-start.
	a.client.Stop()
	go func() {
		if err := a.client.Start(); err != nil {
			a.setError(fmt.Sprintf("Failed to restart backend: %v", err))
			return
		}
		a.health.Start()
		a.loadHAR()
	}()

	g.Update(func(g *gocui.Gui) error {
		_ = g.DeleteView("error")
		return nil
	})
	return nil
}

func (a *App) handleDown(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	a.mu.Lock()
	defer a.mu.Unlock()

	switch a.activePanel {
	case PanelIDSessions:
		if a.selectedIdx < len(a.flows)-1 {
			a.selectedIdx++
			a.exchIdx = 0
			a.analysisScroll = 0
		}
	case PanelIDExchanges:
		if a.selectedIdx >= 0 && a.selectedIdx < len(a.flows) {
			sid := a.flows[a.selectedIdx].SessionID
			if exch, ok := a.flowExchanges[sid]; ok && a.exchIdx < len(exch)-1 {
				a.exchIdx++
			}
		}
	case PanelIDAnalysis:
		a.analysisScroll++
		if a.analysisScroll > 500 {
			a.analysisScroll = 500
		}
	}
	return nil
}

func (a *App) handleFilter(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.activePanel == PanelIDAnalysis {
		return nil
	}
	maxX, maxY := g.Size()
	modal, err := g.SetView("filtermodal", maxX/2-25, maxY/2-1, maxX/2+25, maxY/2+1, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	modal.Title = " Filter (empty to clear) "
	modal.Editable = true
	modal.Editor = gocui.DefaultEditor
	modal.Clear()
	currentFilter := a.sessionFilter
	if a.activePanel == PanelIDExchanges {
		currentFilter = a.exchangeFilter
	}
	fmt.Fprint(modal, currentFilter)

	if _, err := g.SetCurrentView("filtermodal"); err != nil {
		return err
	}
	return nil
}

func (a *App) handleFilterSubmit(g *gocui.Gui, v *gocui.View) error {
	a.mu.Lock()
	lines := v.BufferLines()
	text := ""
	if len(lines) > 0 {
		text = strings.TrimSpace(lines[0])
	}
	if a.activePanel == PanelIDSessions {
		a.sessionFilter = text
		a.selectedIdx = 0
		a.exchIdx = 0 // exchange index follows session reset
	} else if a.activePanel == PanelIDExchanges {
		a.exchangeFilter = text
		a.exchIdx = 0
	}
	a.mu.Unlock()

	_ = g.DeleteView("filtermodal")
	// Return focus
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

func (a *App) handleUp(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	a.mu.Lock()
	defer a.mu.Unlock()

	switch a.activePanel {
	case PanelIDSessions:
		if a.selectedIdx > 0 {
			a.selectedIdx--
			a.exchIdx = 0
			a.analysisScroll = 0
		}
	case PanelIDExchanges:
		if a.exchIdx > 0 {
			a.exchIdx--
		}
	case PanelIDAnalysis:
		if a.analysisScroll > 0 {
			a.analysisScroll--
		}
	}
	return nil
}

func (a *App) handleAnalyze(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.activePanel != PanelIDSessions {
		return nil
	}
	flow := a.selectedFlow()
	if flow == nil || a.state == models.StateAnalyzing {
		return nil
	}

	a.mu.Lock()
	a.state = models.StateAnalyzing
	a.engineStatus = "Analyzing..."
	a.analyzingSessionID = flow.SessionID
	a.spinnerFrame = 0
	a.mu.Unlock()

	// Spinner ticker goroutine.
	spinnerDone := make(chan struct{})
	go func() {
		ticker := time.NewTicker(150 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				a.mu.Lock()
				a.spinnerFrame = (a.spinnerFrame + 1) % 4
				a.mu.Unlock()
				g.Update(func(g *gocui.Gui) error { return nil })
			case <-spinnerDone:
				return
			}
		}
	}()

	go func() {
		defer func() { close(spinnerDone) }()

		resp, err := a.client.Call("analyze_flow", map[string]interface{}{
			"session_id": flow.SessionID,
		})

		a.mu.Lock()
		a.state = models.StateBrowsing
		a.engineStatus = "Idle"
		a.analyzingSessionID = ""
		a.mu.Unlock()

		if err != nil {
			a.showToast(fmt.Sprintf("Error: %v", err))
			return
		}
		if resp.Error != nil {
			a.showToast(fmt.Sprintf("Error: %s", resp.Error.Message))
			return
		}

		resultMap, ok := resp.Result.(map[string]interface{})
		if !ok {
			a.showToast("Invalid analysis response format")
			return
		}

		analysis := parseAnalysis(resultMap)
		if analysis == nil {
			a.showToast("Analysis parse failed")
			return
		}
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
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.activePanel != PanelIDSessions {
		return nil
	}
	if a.state == models.StateAnalyzing {
		return nil
	}

	a.mu.Lock()
	a.state = models.StateAnalyzing
	a.engineStatus = "Analyzing all..."
	// Clear cached analyses so all sessions re-analyze from scratch.
	// Ref: CLI_TUI_PROPOSAL §6.2 — <A> always re-analyzes all sessions.
	for _, flow := range a.flows {
		delete(a.analyses, flow.SessionID)
	}
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

		// Fetch results for any sessions not already updated by progressive handler.
		for _, flow := range a.flows {
			a.mu.Lock()
			_, alreadyCached := a.analyses[flow.SessionID]
			a.mu.Unlock()
			if alreadyCached {
				continue
			}
			r, err := a.client.Call("get_results", map[string]interface{}{
				"session_id": flow.SessionID,
			})
			if err == nil && r.Error == nil {
				if rMap, ok := r.Result.(map[string]interface{}); ok {
					analysis := parseAnalysis(rMap)
					a.mu.Lock()
					a.analyses[flow.SessionID] = analysis
					a.mu.Unlock()
				}
			}
		}

		status := "ok"
		if resp != nil && resp.Result != nil {
			if rMap, ok := resp.Result.(map[string]interface{}); ok {
				if s, ok := rMap["status"].(string); ok {
					status = s
				}
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
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.activePanel != PanelIDSessions {
		return nil
	}
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

func (a *App) handleEnter(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	switch a.activePanel {
	case PanelIDExchanges:
		return a.showRawExchangeModal(g)
	case PanelIDAnalysis:
		return a.showFindingDetailModal(g)
	}
	return nil
}

// showRawExchangeModal, handleRawScrollDown, handleRawScrollUp,
// handleRawFocusRight, handleRawFocusLeft, handleRawClose are defined in rawview.go.

// showFindingDetailModal, handleFindingScrollDown, handleFindingScrollUp,
// handleFindingClose are defined in finding.go.

// handleCopyCURL generates a cURL command for the selected exchange
// and copies it to the system clipboard (or fallback to temp file).
// Uses the cached flowExchanges map — no analysis or IPC call required.
// Ref: CLI_TUI_PROPOSAL.md §6.2
func (a *App) handleCopyCURL(g *gocui.Gui, v *gocui.View) error {
	if a.isAnyModalOpen(g) {
		return nil
	}
	if a.activePanel != PanelIDExchanges {
		return nil
	}

	flow := a.selectedFlow()
	if flow == nil {
		return nil
	}

	a.mu.Lock()
	exchIdx := a.exchIdx
	exchanges, hasExchanges := a.flowExchanges[flow.SessionID]
	a.mu.Unlock()

	if !hasExchanges {
		a.fetchFlowExchangesAsync(flow.SessionID)
		a.showToast("Loading exchanges, please try again")
		return nil
	}
	if len(exchanges) == 0 || exchIdx >= len(exchanges) {
		a.showToast("No exchange at this position")
		return nil
	}
	matchEx := &exchanges[exchIdx]

	// Build exact cURL command
	curlCmd := fmt.Sprintf("curl -X %s '%s'", matchEx.RequestMethod, matchEx.RequestURL)

	for k, vStr := range matchEx.RequestHeaders {
		// Escape single quotes in headers
		vStrEscaped := strings.ReplaceAll(vStr, "'", "'\\''")
		curlCmd += fmt.Sprintf(" \\\n  -H '%s: %s'", k, vStrEscaped)
	}

	if matchEx.RequestBody != nil && *matchEx.RequestBody != "" {
		bodyEscaped := strings.ReplaceAll(*matchEx.RequestBody, "'", "'\\''")
		curlCmd += fmt.Sprintf(" \\\n  -d '%s'", bodyEscaped)
	}

	// Use the clipboard module for platform detection.
	msg := clipboard.Copy(curlCmd)
	a.showToast(msg)

	return nil
}

// handleHelp is defined in help.go.

// drawExportModal, handleExport, handleExportTab, handleExportSpace,
// handleExportBackspace, exportEditor, handleConfirmExport are defined in export.go.

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
