cat internal/ui/panels.go | \
  sed '/func (a \*App) renderModeB/,$d' > new_panels2.go
cat << 'INNER' >> new_panels2.go
// renderModeB shows per-exchange detail.
func (a *App) renderModeB(v *gocui.View, analysis *models.SessionAnalysis) {
        a.mu.Lock()
        exchIdx := a.exchIdx
        flow := a.selectedFlow()
        exchanges, hasExchanges := a.flowExchanges[flow.SessionID]
        a.mu.Unlock()

        if !hasExchanges || exchIdx >= len(exchanges) {
                fmt.Fprintln(v, "  No exchange selected.")
                return
        }
        
        ex := exchanges[exchIdx]
        
        // Find matching analysis result if we have one
        var result *models.ExchangeResult
        for i, r := range analysis.Results {
                if r.HTTPMethod == ex.RequestMethod && strings.HasSuffix(ex.RequestURL, r.Endpoint) {
                        result = &analysis.Results[i]
                        break
                }
        }
        
        if result == nil {
                v.Title = fmt.Sprintf(" Analysis: %s %s ", ex.RequestMethod, truncate(ex.RequestURL, 20))
                fmt.Fprintln(v, "")
                fmt.Fprintln(v, "  No CSRF analysis applicable for this request.")
                fmt.Fprintln(v, "  (Usually because it is a GET request or non-state-changing)")
                return
        }

        r := *result
        v.Title = fmt.Sprintf(" Analysis: %s %s ", r.HTTPMethod, r.Endpoint)

        // Risk Score Header (pinned) with color.
        color := models.RiskColor(r.RiskLevel)
        fmt.Fprintf(v, "  %sRISK SCORE: %d / 100        %s %s\033[0m\n",
                color,
                r.RiskScore,
                models.RiskIndicator(r.RiskLevel),
                r.RiskLevel)
        if r.MLProbability != nil {
                fmt.Fprintf(v, "  ML Confidence: %.0f%%  |  Static: %.0f%%\n",
                        *r.MLProbability*100,
                        r.StaticScore*100)
        } else {
                fmt.Fprintf(v, "  ML Confidence: Skipped  |  Static: %.0f%%\n",
                        r.StaticScore*100)
        }
        fmt.Fprintln(v, "")

        // Findings.
        fmt.Fprintln(v, " --- Findings ------------------------------------")
        fmt.Fprintln(v, "")
        if len(r.Findings) == 0 {
                fmt.Fprintln(v, "  No critical findings.")
        } else {
                for _, f := range r.Findings {
                        sev := severityBadge(f.Severity)
                        fmt.Fprintf(v, "  %s [%s] %s\n", sev, f.RuleID, f.RuleName)
                        if f.Evidence != "" {
                                fmt.Fprintf(v, "       > %s\n", truncate(f.Evidence, 60))
                        }
                        fmt.Fprintln(v, "")
                }
        }

        // ML Feature Vector.
        fmt.Fprintln(v, " --- ML Feature Vector -------------------------")
        fmt.Fprintln(v, "")
        keys := make([]string, 0, len(r.FeatureVector))
        for k := range r.FeatureVector {
                keys = append(keys, k)
        }
        sort.Strings(keys)
        for _, k := range keys {
                val := r.FeatureVector[k]
                fmt.Fprintf(v, "  %-25s : %v\n", k, val)
        }
        fmt.Fprintln(v, "")

        // Recommendations.
        fmt.Fprintln(v, " --- Recommendations ---------------------------")
        fmt.Fprintln(v, "")
        if len(r.Recommendations) == 0 {
                fmt.Fprintln(v, "  No specific recommendations.")
        } else {
                for i, rec := range r.Recommendations {
                        // T-505 line wrap to avoid overflowing 80 chars.
                        fmt.Fprintf(v, "  %d. %s\n", i+1, truncate(rec, 70))
                }
        }
}
INNER
mv new_panels2.go internal/ui/panels.go
