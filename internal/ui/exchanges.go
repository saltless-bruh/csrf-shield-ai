package ui

import (
	"fmt"
	"strings"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// renderExchanges populates Panel 2.
// T-502: Virtual scrolling for large exchange lists.
// T-503: Empty state when no exchanges or not analyzed.
// T-735: Filter by method/URL.
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

	a.mu.Lock()
	exchanges, hasExchanges := a.flowExchanges[flow.SessionID]
	exchIdx := a.exchIdx
	filter := strings.ToLower(a.exchangeFilter)
	a.mu.Unlock()

	if !hasExchanges {
		a.fetchFlowExchangesAsync(flow.SessionID)
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  Loading exchanges...")
		return
	}

	if len(exchanges) == 0 {
		fmt.Fprintln(v, "")
		fmt.Fprintln(v, "  No exchanges found.")
		return
	}

	analysis := a.selectedAnalysis() // Optional, used for highlighting risk

	// Build filtered index list.
	var visible []int
	for i, ex := range exchanges {
		if filter != "" {
			if !strings.Contains(strings.ToLower(ex.RequestMethod), filter) &&
				!strings.Contains(strings.ToLower(ex.RequestURL), filter) {
				continue
			}
		}
		visible = append(visible, i)
	}

	if len(visible) == 0 {
		fmt.Fprintln(v, "")
		fmt.Fprintf(v, "  No exchanges matching \"%s\".\n", a.exchangeFilter)
		return
	}

	height := viewHeight(v)
	a.exchScroll = adjustScroll(exchIdx, a.exchScroll, height, len(visible))

	end := a.exchScroll + height
	if end > len(visible) {
		end = len(visible)
	}

	for vi := a.exchScroll; vi < end; vi++ {
		realIdx := visible[vi]
		ex := exchanges[realIdx]
		cursor := "  "
		if realIdx == exchIdx && a.activePanel == PanelIDExchanges {
			cursor = "> "
		}

		// Default badge and risk
		badge := models.BodyTypeBadge(ex.RequestContentType)
		risk := "--"

		// If it's a state-changing request, try to find analysis
		if analysis != nil {
			for _, r := range analysis.Results {
				if r.HTTPMethod == ex.RequestMethod && strings.HasSuffix(ex.RequestURL, r.Endpoint) {
					color := models.RiskColor(r.RiskLevel)
					risk = color + models.RiskIndicator(r.RiskLevel) + "\033[0m"
					break
				}
			}
		}

		endpoint := truncate(ex.RequestURL, 25)
		fmt.Fprintf(v, "%s%-6s %-25s %-7s --- %d %s\n",
			cursor, ex.RequestMethod, endpoint, badge, ex.ResponseStatus, risk)
	}

	// Scroll indicator + filter label.
	w, _ := v.Size()
	selectedVisible := 1
	for i, realIdx := range visible {
		if realIdx == exchIdx {
			selectedVisible = i + 1
			break
		}
	}
	if filter != "" {
		v.Title = titleWithCounter(
			fmt.Sprintf(" Exchanges [Filter: %q] ", a.exchangeFilter),
			fmt.Sprintf(" [%d/%d] ", selectedVisible, len(visible)),
			w,
		)
	} else if len(visible) > height {
		v.Title = titleWithCounter(" Exchanges ", fmt.Sprintf(" [%d/%d] ", selectedVisible, len(visible)), w)
	} else {
		v.Title = " Exchanges "
	}
}
