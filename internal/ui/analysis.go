package ui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// renderAnalysis populates Panel 3 (Mode A or Mode B).
// T-503: Empty/not-analyzed and short-circuited states.
func (a *App) renderAnalysis(g *gocui.Gui) {
	hdrV, err := g.View(PanelAnalysisHdr)
	if err != nil {
		return
	}
	bodyV, err := g.View(PanelAnalysis)
	if err != nil {
		return
	}
	hdrV.Clear()
	bodyV.Clear()
	_ = bodyV.SetOrigin(0, 0)

	analysis := a.selectedAnalysis()
	if analysis == nil {
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "         Not analyzed yet.")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "    Select a session and press <a> to")
		fmt.Fprintln(bodyV, "    run CSRF analysis.")
		return
	}

	if analysis.Status == "not_analyzed" {
		fmt.Fprintln(bodyV, "  Press <a> to analyze.")
		return
	}

	// Mode A (session summary) vs Mode B (per-exchange detail).
	if a.activePanel == PanelIDExchanges && len(analysis.Results) > 0 {
		a.renderModeB(hdrV, bodyV, analysis)
	} else {
		a.renderModeA(hdrV, bodyV, analysis)
	}

	// Apply j/k scroll offset for Panel 3 body only — header stays pinned (M1).
	a.mu.Lock()
	scroll := a.analysisScroll
	a.mu.Unlock()
	if scroll > 0 {
		_ = bodyV.SetOrigin(0, scroll)
	}
}

// renderModeA shows session-level summary.
func (a *App) renderModeA(hdrV, bodyV *gocui.View, analysis *models.SessionAnalysis) {
	hdrV.Title = " Analysis Engine "

	// Risk Score Header — written to hdrV so it stays pinned (M1).
	color := models.RiskColor(analysis.Summary.RiskLevel)
	fmt.Fprintf(hdrV, "  %sRISK SCORE: %d / 100        %s %s\033[0m\n",
		color,
		analysis.Summary.RiskScore,
		models.RiskIndicator(analysis.Summary.RiskLevel),
		analysis.Summary.RiskLevel)
	if analysis.Summary.MLProbabilityMax != nil {
		fmt.Fprintf(hdrV, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
			*analysis.Summary.MLProbabilityMax*100,
			analysis.Summary.StaticScoreMax*100)
	} else {
		fmt.Fprintf(hdrV, "  ML Confidence: Skipped  |  Static: %.0f%%\n",
			analysis.Summary.StaticScoreMax*100)
	}

	// Scrollable body content written to bodyV.

	// Check for short-circuit.
	if len(analysis.Results) == 1 && analysis.Results[0].Endpoint == "short-circuited" {
		fmt.Fprintln(bodyV, "  >> SHORT-CIRCUITED (Header-Only Auth)")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "  This session uses header-based auth")
		fmt.Fprintln(bodyV, "  exclusively. CSRF is not applicable.")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, " --- ML Feature Vector -------------------------")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "  (Skipped — pipeline short-circuited)")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, " --- Recommendations ---------------------------")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "  No action needed — CSRF N/A.")
		return
	}

	// Findings.
	totalFindings := 0
	for _, r := range analysis.Results {
		totalFindings += len(r.Findings)
	}

	if totalFindings == 0 {
		fmt.Fprintln(bodyV, " --- Static Findings (0) -------------------------")
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "  No findings. All checks passed.")
		fmt.Fprintln(bodyV, "")
	} else {
		fmt.Fprintf(bodyV, " --- Static Findings (%d) -------------------------\n", totalFindings)
		fmt.Fprintln(bodyV, "")

		seen := make(map[string]bool)
		for _, r := range analysis.Results {
			for _, f := range r.Findings {
				if seen[f.RuleID] {
					continue
				}
				seen[f.RuleID] = true
				sev := severityBadge(f.Severity)
				fmt.Fprintf(bodyV, "  %s [%s] %s\n", sev, f.RuleID, f.RuleName)
				if f.Evidence != "" {
					fmt.Fprintf(bodyV, "       > %s\n", truncate(f.Evidence, 60))
				}
				fmt.Fprintln(bodyV, "")
			}
		}
	}

	// Recommendations.
	fmt.Fprintln(bodyV, " --- Recommendations -----------------------------")
	fmt.Fprintln(bodyV, "")
	seen2 := make(map[string]bool)
	idx := 1
	hasRecs := false
	for _, r := range analysis.Results {
		for _, rec := range r.Recommendations {
			if seen2[rec] {
				continue
			}
			seen2[rec] = true
			fmt.Fprintf(bodyV, "  %d. %s\n", idx, truncate(rec, 70))
			idx++
			hasRecs = true
		}
	}
	if !hasRecs {
		fmt.Fprintln(bodyV, "  No recommendations.")
	}
}

// renderModeB shows per-exchange detail.
func (a *App) renderModeB(hdrV, bodyV *gocui.View, analysis *models.SessionAnalysis) {
	a.mu.Lock()
	exchIdx := a.exchIdx
	var sessionID string
	if a.selectedIdx >= 0 && a.selectedIdx < len(a.flows) {
		sessionID = a.flows[a.selectedIdx].SessionID
	}
	exchanges, hasExchanges := a.flowExchanges[sessionID]
	a.mu.Unlock()

	if sessionID == "" || !hasExchanges || exchIdx >= len(exchanges) {
		fmt.Fprintln(bodyV, "  No exchange selected.")
		return
	}

	ex := exchanges[exchIdx]

	// Find matching analysis result if we have one.
	var result *models.ExchangeResult
	for i, r := range analysis.Results {
		if r.HTTPMethod == ex.RequestMethod && strings.HasSuffix(ex.RequestURL, r.Endpoint) {
			result = &analysis.Results[i]
			break
		}
	}

	if result == nil {
		hdrV.Title = fmt.Sprintf(" Analysis: %s %s ", ex.RequestMethod, truncate(ex.RequestURL, 20))
		fmt.Fprintln(bodyV, "")
		fmt.Fprintln(bodyV, "  No CSRF analysis applicable for this request.")
		fmt.Fprintln(bodyV, "  (Usually because it is a GET request or non-state-changing)")
		return
	}

	r := *result
	hdrV.Title = fmt.Sprintf(" Analysis: %s %s ", r.HTTPMethod, r.Endpoint)

	// Risk Score Header — written to hdrV so it stays pinned (M1).
	color := models.RiskColor(r.RiskLevel)
	fmt.Fprintf(hdrV, "  %sRISK SCORE: %d / 100        %s %s\033[0m\n",
		color,
		r.RiskScore,
		models.RiskIndicator(r.RiskLevel),
		r.RiskLevel)
	if r.MLProbability != nil {
		fmt.Fprintf(hdrV, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
			*r.MLProbability*100,
			r.StaticScore*100)
	} else {
		fmt.Fprintf(hdrV, "  ML Confidence: Skipped  |  Static: %.0f%%\n",
			r.StaticScore*100)
	}

	// Scrollable body content written to bodyV.

	// Findings.
	fmt.Fprintln(bodyV, " --- Findings ------------------------------------")
	fmt.Fprintln(bodyV, "")
	if len(r.Findings) == 0 {
		fmt.Fprintln(bodyV, "  No critical findings.")
	} else {
		for _, f := range r.Findings {
			sev := severityBadge(f.Severity)
			fmt.Fprintf(bodyV, "  %s [%s] %s\n", sev, f.RuleID, f.RuleName)
			if f.Evidence != "" {
				fmt.Fprintf(bodyV, "       > %s\n", truncate(f.Evidence, 60))
			}
			fmt.Fprintln(bodyV, "")
		}
	}

	// ML Feature Vector with proposal-defined key order (§5.3, n2).
	fmt.Fprintln(bodyV, " --- ML Feature Vector -------------------------")
	fmt.Fprintln(bodyV, "")
	orderedKeys := []string{
		"has_csrf_token_in_form",
		"has_csrf_token_in_header",
		"has_samesite_cookie",
		"has_origin_check",
		"has_referer_check",
		"http_method",
		"is_state_changing",
		"content_type",
		"requires_auth",
		"token_entropy",
		"token_changes_per_request",
		"response_sets_cookie",
		"auth_mechanism",
		"endpoint_sensitivity",
	}
	printed := make(map[string]bool)
	for _, k := range orderedKeys {
		if val, ok := r.FeatureVector[k]; ok {
			fmt.Fprintf(bodyV, "  %-25s : %v\n", k, val)
			printed[k] = true
		}
	}
	// Any extra keys not in the proposal table, sorted alphabetically.
	extraKeys := make([]string, 0)
	for k := range r.FeatureVector {
		if !printed[k] {
			extraKeys = append(extraKeys, k)
		}
	}
	sort.Strings(extraKeys)
	for _, k := range extraKeys {
		fmt.Fprintf(bodyV, "  %-25s : %v\n", k, r.FeatureVector[k])
	}
	fmt.Fprintln(bodyV, "")

	// Recommendations.
	fmt.Fprintln(bodyV, " --- Recommendations ---------------------------")
	fmt.Fprintln(bodyV, "")
	if len(r.Recommendations) == 0 {
		fmt.Fprintln(bodyV, "  No specific recommendations.")
	} else {
		for i, rec := range r.Recommendations {
			// T-505 line wrap to avoid overflowing 80 chars.
			fmt.Fprintf(bodyV, "  %d. %s\n", i+1, truncate(rec, 70))
		}
	}
}
