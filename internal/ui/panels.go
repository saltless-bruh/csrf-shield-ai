package ui

import (
	"fmt"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// renderSessions populates Panel 1 with session flow data.
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
		fmt.Fprintln(v, "  No sessions found. Check your HAR file.")
		return
	}

	for i, f := range flows {
		cursor := "  "
		if i == selectedIdx {
			cursor = "> "
		}

		// Truncate session ID to 7 chars.
		sid := f.SessionID
		if len(sid) > 7 {
			sid = sid[:7]
		}

		// Risk indicator.
		risk := "--"
		if analysis, ok := analyses[f.SessionID]; ok {
			risk = models.RiskIndicator(analysis.Summary.RiskLevel)
		}

		auth := models.AuthBadge(f.AuthMechanism)

		fmt.Fprintf(v, "%s%-7s  %-20s  %s [%d]  %s\n",
			cursor, sid, truncate(f.Host, 20), auth, f.ExchangeCount, risk)
	}
}

// renderExchanges populates Panel 2 (stub — full impl needs flow exchanges from IPC).
func (a *App) renderExchanges(g *gocui.Gui) {
	v, err := g.View(PanelExchanges)
	if err != nil {
		return
	}
	v.Clear()

	flow := a.selectedFlow()
	if flow == nil {
		fmt.Fprintln(v, "  No session selected.")
		return
	}

	// Show exchange data from cached analysis if available.
	analysis := a.selectedAnalysis()
	if analysis == nil || len(analysis.Results) == 0 {
		fmt.Fprintf(v, "  %d exchanges in session %s\n", flow.ExchangeCount, flow.SessionID[:min(7, len(flow.SessionID))])
		fmt.Fprintln(v, "  Press <a> to analyze.")
		return
	}

	a.mu.Lock()
	exchIdx := a.exchIdx
	a.mu.Unlock()

	for i, r := range analysis.Results {
		cursor := "  "
		if i == exchIdx && a.activePanel == PanelIDExchanges {
			cursor = "> "
		}

		risk := models.RiskIndicator(r.RiskLevel)
		endpoint := truncate(r.Endpoint, 30)

		fmt.Fprintf(v, "%s%-6s %-30s  --- %s  %s\n",
			cursor, r.HTTPMethod, endpoint, r.RiskLevel[:3], risk)
	}
}

// renderAnalysis populates Panel 3 (Mode A or Mode B).
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
	// Risk Score Header (pinned).
	fmt.Fprintf(v, "  RISK SCORE: %d / 100        %s %s\n",
		analysis.Summary.RiskScore,
		models.RiskIndicator(analysis.Summary.RiskLevel),
		analysis.Summary.RiskLevel)
	fmt.Fprintf(v, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
		analysis.Summary.MLProbabilityMax*100,
		analysis.Summary.StaticScoreMax*100)
	fmt.Fprintln(v, "")

	// Findings.
	totalFindings := 0
	for _, r := range analysis.Results {
		totalFindings += len(r.Findings)
	}
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

	// Recommendations.
	fmt.Fprintln(v, " --- Recommendations -----------------------------")
	fmt.Fprintln(v, "")
	seen2 := make(map[string]bool)
	idx := 1
	for _, r := range analysis.Results {
		for _, rec := range r.Recommendations {
			if seen2[rec] {
				continue
			}
			seen2[rec] = true
			fmt.Fprintf(v, "  %d. %s\n", idx, truncate(rec, 70))
			idx++
		}
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

	// Feature vector.
	fmt.Fprintf(v, " --- ML Feature Vector (%d) ----------------------\n", len(r.FeatureVector))
	fmt.Fprintln(v, "")
	for k, val := range r.FeatureVector {
		fmt.Fprintf(v, "  %-26s : %v\n", k, val)
	}
	fmt.Fprintln(v, "")

	// Recommendations.
	fmt.Fprintln(v, " --- Recommendations -----------------------------")
	fmt.Fprintln(v, "")
	for i, rec := range r.Recommendations {
		fmt.Fprintf(v, "  %d. %s\n", i+1, truncate(rec, 70))
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
		keys = " <a> analyze  <A> analyze all  <f> filter  <x> remove  <e> export  <q> quit  <?> help"
	case PanelIDExchanges:
		keys = " <Enter> view raw  <c> copy cURL  <f> filter  <e> export  <q> quit  <?> help"
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

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max-3] + "..."
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
