package ui

import (
	"fmt"

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

// renderSessions populates Panel 1 with session flow data.
// T-502: Virtual scrolling for large session lists.
// T-503: Empty state when no sessions.
func (a *App) renderSessions(g *gocui.Gui) {
	v, err := g.View(PanelSessions)
	if err != nil {
		return
	}
	v.Clear()

	a.mu.Lock()
	flows := a.flows
	selectedIdx := a.selectedIdx
	analyses := a.analyses
	a.mu.Unlock()

	if len(flows) == 0 {
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No sessions found. Check your HAR file.")
		return
	}

	height := viewHeight(v)
	a.sessionScroll = adjustScroll(selectedIdx, a.sessionScroll, height, len(flows))

	end := a.sessionScroll + height
	if end > len(flows) {
		end = len(flows)
	}

	for i := a.sessionScroll; i < end; i++ {
		f := flows[i]
		cursor := "  "
		if i == selectedIdx {
			cursor = "> "
		}

		sid := f.SessionID
		if len(sid) > 7 {
			sid = sid[:7]
		}

		risk := "--"
		if analysis, ok := analyses[f.SessionID]; ok {
			risk = models.RiskIndicator(analysis.Summary.RiskLevel)
		}

		auth := models.AuthBadge(f.AuthMechanism)

		fmt.Fprintf(v, "%s%-7s  %-20s  %s [%d]  %s\n",
			cursor, sid, truncate(f.Host, 20), auth, f.ExchangeCount, risk)
	}

	// Scroll indicator if list overflows.
	if len(flows) > height {
		v.Title = fmt.Sprintf(" Sessions [%d/%d] ", selectedIdx+1, len(flows))
	} else {
		v.Title = " Sessions "
	}
}

// renderExchanges populates Panel 2.
// T-502: Virtual scrolling for large exchange lists.
// T-503: Empty state when no exchanges or not analyzed.
func (a *App) renderExchanges(g *gocui.Gui) {
	v, err := g.View(PanelExchanges)
	if err != nil {
		return
	}
	v.Clear()

	flow := a.selectedFlow()
	if flow == nil {
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No session selected.")
		return
	}

	analysis := a.selectedAnalysis()
	if analysis == nil || len(analysis.Results) == 0 {
		sid := flow.SessionID
		if len(sid) > 7 {
			sid = sid[:7]
		}
		fmt.Fprintln(v, "")
		fmt.Fprintf(v, "  %d exchanges in session %s\n", flow.ExchangeCount, sid)
		fmt.Fprintln(v, "  Press <a> to analyze.")
		return
	}

	a.mu.Lock()
	exchIdx := a.exchIdx
	a.mu.Unlock()

	total := len(analysis.Results)
	height := viewHeight(v)
	a.exchScroll = adjustScroll(exchIdx, a.exchScroll, height, total)

	end := a.exchScroll + height
	if end > total {
		end = total
	}

	for i := a.exchScroll; i < end; i++ {
		r := analysis.Results[i]
		cursor := "  "
		if i == exchIdx && a.activePanel == PanelIDExchanges {
			cursor = "> "
		}

		risk := models.RiskIndicator(r.RiskLevel)
		endpoint := truncate(r.Endpoint, 30)

		fmt.Fprintf(v, "%s%-6s %-30s  --- %s  %s\n",
			cursor, r.HTTPMethod, endpoint, r.RiskLevel[:min(3, len(r.RiskLevel))], risk)
	}

	// Scroll indicator if list overflows.
	if total > height {
		v.Title = fmt.Sprintf(" Exchanges [%d/%d] ", exchIdx+1, total)
	} else {
		v.Title = " Exchanges "
	}
}

// renderAnalysis populates Panel 3 (Mode A or Mode B).
// T-503: Empty/not-analyzed and short-circuited states.
func (a *App) renderAnalysis(g *gocui.Gui) {
	v, err := g.View(PanelAnalysis)
	if err != nil {
		return
	}
	v.Clear()

	analysis := a.selectedAnalysis()
	if analysis == nil {
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "         Not analyzed yet.")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "    Select a session and press <a> to")
		fmt.Fprintln(v, "    run CSRF analysis.")
		return
	}

	if analysis.Status == "not_analyzed" {
		fmt.Fprintln(v, "  Press <a> to analyze.")
		return
	}

	// Mode A (session summary) vs Mode B (per-exchange detail).
	if a.activePanel == PanelIDExchanges && len(analysis.Results) > 0 {
		a.renderModeB(v, analysis)
	} else {
		a.renderModeA(v, analysis)
	}
}

// renderModeA shows session-level summary.
func (a *App) renderModeA(v *gocui.View, analysis *models.SessionAnalysis) {
	v.Title = " Analysis Engine "

	// Risk Score Header (pinned).
	fmt.Fprintf(v, "  RISK SCORE: %d / 100        %s %s\n",
		analysis.Summary.RiskScore,
		models.RiskIndicator(analysis.Summary.RiskLevel),
		analysis.Summary.RiskLevel)
	fmt.Fprintf(v, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
		analysis.Summary.MLProbabilityMax*100,
		analysis.Summary.StaticScoreMax*100)
	fmt.Fprintln(v, "")

	// Check for short-circuit.
	if len(analysis.Results) == 1 && analysis.Results[0].Endpoint == "short-circuited" {
		fmt.Fprintln(v, "  >> SHORT-CIRCUITED (Header-Only Auth)")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  This session uses header-based auth")
		fmt.Fprintln(v, "  exclusively. CSRF is not applicable.")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, " --- ML Feature Vector -------------------------")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  (Skipped — pipeline short-circuited)")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, " --- Recommendations ---------------------------")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No action needed — CSRF N/A.")
		return
	}

	// Findings.
	totalFindings := 0
	for _, r := range analysis.Results {
		totalFindings += len(r.Findings)
	}

	if totalFindings == 0 {
		fmt.Fprintln(v, " --- Static Findings (0) -------------------------")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No findings. All checks passed.")
		fmt.Fprintln(v, "")
	} else {
		fmt.Fprintf(v, " --- Static Findings (%d) -------------------------\n", totalFindings)
		fmt.Fprintln(v, "")

		seen := make(map[string]bool)
		for _, r := range analysis.Results {
			for _, f := range r.Findings {
				if seen[f.RuleID] {
					continue
				}
				seen[f.RuleID] = true
				sev := severityBadge(f.Severity)
				fmt.Fprintf(v, "  %s [%s] %s\n", sev, f.RuleID, f.RuleName)
				if f.Evidence != "" {
					fmt.Fprintf(v, "       > %s\n", truncate(f.Evidence, 60))
				}
				fmt.Fprintln(v, "")
			}
		}
	}

	// Recommendations.
	fmt.Fprintln(v, " --- Recommendations -----------------------------")
	fmt.Fprintln(v, "")
	seen2 := make(map[string]bool)
	idx := 1
	hasRecs := false
	for _, r := range analysis.Results {
		for _, rec := range r.Recommendations {
			if seen2[rec] {
				continue
			}
			seen2[rec] = true
			fmt.Fprintf(v, "  %d. %s\n", idx, truncate(rec, 70))
			idx++
			hasRecs = true
		}
	}
	if !hasRecs {
		fmt.Fprintln(v, "  No recommendations.")
	}
}

// renderModeB shows per-exchange detail.
func (a *App) renderModeB(v *gocui.View, analysis *models.SessionAnalysis) {
	a.mu.Lock()
	exchIdx := a.exchIdx
	a.mu.Unlock()

	if exchIdx >= len(analysis.Results) {
		exchIdx = 0
	}
	r := analysis.Results[exchIdx]

	v.Title = fmt.Sprintf(" Analysis: %s %s ", r.HTTPMethod, r.Endpoint)

	// Risk Score Header (pinned).
	fmt.Fprintf(v, "  RISK SCORE: %d / 100        %s %s\n",
		r.RiskScore,
		models.RiskIndicator(r.RiskLevel),
		r.RiskLevel)
	fmt.Fprintf(v, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
		r.MLProbability*100,
		r.StaticScore*100)
	fmt.Fprintln(v, "")

	// Findings.
	if len(r.Findings) == 0 {
		fmt.Fprintln(v, " --- Static Findings (0) -------------------------")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No findings for this exchange.")
		fmt.Fprintln(v, "")
	} else {
		fmt.Fprintf(v, " --- Static Findings (%d) -------------------------\n", len(r.Findings))
		fmt.Fprintln(v, "")
		for _, f := range r.Findings {
			sev := severityBadge(f.Severity)
			fmt.Fprintf(v, "  %s [%s] %s\n", sev, f.RuleID, f.RuleName)
			if f.Evidence != "" {
				fmt.Fprintf(v, "       > %s\n", truncate(f.Evidence, 60))
			}
			fmt.Fprintln(v, "")
		}
	}

	// Feature vector.
	if len(r.FeatureVector) == 0 {
		fmt.Fprintln(v, " --- ML Feature Vector -------------------------")
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  (Not available)")
		fmt.Fprintln(v, "")
	} else {
		fmt.Fprintf(v, " --- ML Feature Vector (%d) ----------------------\n", len(r.FeatureVector))
		fmt.Fprintln(v, "")
		for k, val := range r.FeatureVector {
			fmt.Fprintf(v, "  %-26s : %v\n", k, val)
		}
		fmt.Fprintln(v, "")
	}

	// Recommendations.
	fmt.Fprintln(v, " --- Recommendations -----------------------------")
	fmt.Fprintln(v, "")
	if len(r.Recommendations) == 0 {
		fmt.Fprintln(v, "  No recommendations.")
	} else {
		for i, rec := range r.Recommendations {
			fmt.Fprintf(v, "  %d. %s\n", i+1, truncate(rec, 70))
		}
	}
}

// renderStatusBar updates the bottom status bar.
func (a *App) renderStatusBar(g *gocui.Gui) {
	v, err := g.View(PanelStatus)
	if err != nil {
		return
	}
	v.Clear()

	// Context-specific keys.
	var keys string
	switch a.activePanel {
	case PanelIDSessions:
		keys = " <a> analyze  <A> analyze all  <x> remove  <e> export  <q> quit  <?> help"
	case PanelIDExchanges:
		keys = " <Enter> view raw  <c> copy cURL  <e> export  <q> quit  <?> help"
	case PanelIDAnalysis:
		keys = " <Enter> finding detail  <e> export  <q> quit  <?> help"
	}

	// Right side: toast or engine status.
	a.mu.Lock()
	rightSide := fmt.Sprintf("[ML: %s]", a.engineStatus)
	if a.toastMsg != "" {
		rightSide = fmt.Sprintf("[%s]", a.toastMsg)
	}
	a.mu.Unlock()

	maxX, _ := g.Size()
	padding := maxX - len(keys) - len(rightSide) - 1
	if padding < 1 {
		padding = 1
	}

	fmt.Fprintf(v, "%s%*s%s", keys, padding, "", rightSide)
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	if maxLen <= 3 {
		return s[:maxLen]
	}
	return s[:maxLen-3] + "..."
}

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

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
