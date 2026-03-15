package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"
)

// showRawExchangeModal displays raw HTTP request/response in a side-by-side modal.
// Ref: CLI_TUI_PROPOSAL.md §7.3 (M2 — side-by-side raw view)
func (a *App) showRawExchangeModal(g *gocui.Gui) error {
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

	maxX, maxY := g.Size()
	midX := (2 + maxX - 3) / 2

	// Left column: request (M2).
	reqV, err := g.SetView("rawmodal_req", 2, 1, midX, maxY-2, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	reqV.Title = " Request "
	reqV.Wrap = false
	reqV.Clear()
	_ = reqV.SetOrigin(0, 0)

	// Right column: response — shares left border with request column (M2).
	respV, err := g.SetView("rawmodal_resp", midX, 1, maxX-3, maxY-2, gocui.LEFT)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	respV.Title = fmt.Sprintf(" Response — %s %s ", matchEx.RequestMethod, truncate(matchEx.RequestURL, 30))
	respV.Wrap = false
	respV.Clear()
	_ = respV.SetOrigin(0, 0)

	// --- Render request ---
	fmt.Fprintf(reqV, "\033[1m%s %s HTTP/1.1\033[0m\n", matchEx.RequestMethod, matchEx.RequestURL)
	for k, v := range matchEx.RequestHeaders {
		fmt.Fprintf(reqV, "\033[1m%s:\033[0m %s\n", k, v)
	}
	if len(matchEx.RequestCookies) > 0 {
		cookies := ""
		for k, v := range matchEx.RequestCookies {
			if cookies != "" {
				cookies += "; "
			}
			cookies += k + "=" + v
		}
		fmt.Fprintf(reqV, "\033[1mCookie:\033[0m %s\n", cookies)
	}
	if matchEx.RequestBody != nil && *matchEx.RequestBody != "" {
		body := *matchEx.RequestBody
		if len(body) > 4096 {
			body = body[:4096] + "\n[truncated]"
		}
		fmt.Fprintf(reqV, "\n%s\n", body)
	}
	fmt.Fprintf(reqV, "\n[l: → Response  |  j/k: scroll  |  q: close]")

	// --- Render response ---
	fmt.Fprintf(respV, "\033[1mHTTP/1.1 %d\033[0m\n", matchEx.ResponseStatus)
	for k, v := range matchEx.ResponseHeaders {
		fmt.Fprintf(respV, "\033[1m%s:\033[0m %s\n", k, v)
	}
	if matchEx.ResponseBody != nil && *matchEx.ResponseBody != "" {
		body := *matchEx.ResponseBody
		if len(body) > 2048 {
			body = body[:2048] + "\n[truncated]"
		}
		fmt.Fprintf(respV, "\n%s\n", body)
	}
	fmt.Fprintf(respV, "\n[h: ← Request  |  j/k: scroll  |  q: close]")

	if _, err := g.SetCurrentView("rawmodal_req"); err != nil {
		return err
	}
	g.SetViewOnTop("rawmodal_resp")
	g.SetViewOnTop("rawmodal_req")
	return nil
}

// handleRawScrollDown scrolls the focused raw modal column down (M2).
func (a *App) handleRawScrollDown(g *gocui.Gui, v *gocui.View) error {
	ox, oy := v.Origin()
	_ = v.SetOrigin(ox, oy+1)
	return nil
}

// handleRawScrollUp scrolls the focused raw modal column up (M2).
func (a *App) handleRawScrollUp(g *gocui.Gui, v *gocui.View) error {
	ox, oy := v.Origin()
	if oy > 0 {
		_ = v.SetOrigin(ox, oy-1)
	}
	return nil
}

// handleRawFocusRight moves focus from Request to Response column (M2).
func (a *App) handleRawFocusRight(g *gocui.Gui, v *gocui.View) error {
	_, err := g.SetCurrentView("rawmodal_resp")
	return err
}

// handleRawFocusLeft moves focus from Response to Request column (M2).
func (a *App) handleRawFocusLeft(g *gocui.Gui, v *gocui.View) error {
	_, err := g.SetCurrentView("rawmodal_req")
	return err
}

// handleRawClose closes both raw modal columns and returns focus to the active panel (M2).
func (a *App) handleRawClose(g *gocui.Gui, v *gocui.View) error {
	_ = g.DeleteView("rawmodal_req")
	_ = g.DeleteView("rawmodal_resp")
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
