package ui

import (
	"fmt"
	"strings"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/models"
)

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
	filter := strings.ToLower(a.sessionFilter)
	analyzingSID := a.analyzingSessionID
	spinFrame := a.spinnerFrame
	a.mu.Unlock()

	// Build filtered index list.
	var visible []int
	for i, f := range flows {
		if filter != "" {
			if !strings.Contains(strings.ToLower(f.SessionID), filter) &&
				!strings.Contains(strings.ToLower(f.Host), filter) {
				continue
			}
		}
		visible = append(visible, i)
	}

	if len(visible) == 0 {
		fmt.Fprintln(v, "")
		if filter != "" {
			fmt.Fprintf(v, "  No sessions matching \"%s\".\n", a.sessionFilter)
		} else {
			fmt.Fprintln(v, "  No sessions found. Check your HAR file.")
		}
		return
	}

	height := viewHeight(v)
	a.sessionScroll = adjustScroll(selectedIdx, a.sessionScroll, height, len(visible))

	end := a.sessionScroll + height
	if end > len(visible) {
		end = len(visible)
	}

	for vi := a.sessionScroll; vi < end; vi++ {
		realIdx := visible[vi]
		f := flows[realIdx]
		cursor := "  "
		if realIdx == selectedIdx {
			cursor = "> "
		}

		sid := f.SessionID
		if len(sid) > 7 {
			sid = sid[:7]
		}

		// Spinner for currently-analyzing session (T-843).
		risk := "--"
		if f.SessionID == analyzingSID && analyzingSID != "" {
			spinnerChars := []string{"-", "\\", "|", "/"}
			risk = "\033[1;33m[" + spinnerChars[spinFrame] + "]\033[0m"
		} else if analysis, ok := analyses[f.SessionID]; ok {
			color := models.RiskColor(analysis.Summary.RiskLevel)
			risk = color + models.RiskIndicator(analysis.Summary.RiskLevel) + "\033[0m"
		}

		auth := models.AuthBadge(f.AuthMechanism)

		fmt.Fprintf(v, "%s%-7s  %-20s  %s [%d]  %s\n",
			cursor, sid, truncate(f.Host, 20), auth, f.ExchangeCount, risk)
	}

	// Scroll indicator + filter label.
	w, _ := v.Size()
	selectedVisible := 1
	for i, realIdx := range visible {
		if realIdx == selectedIdx {
			selectedVisible = i + 1
			break
		}
	}
	if filter != "" {
		v.Title = titleWithCounter(
			fmt.Sprintf(" Sessions [Filter: %q] ", a.sessionFilter),
			fmt.Sprintf(" [%d/%d] ", selectedVisible, len(visible)),
			w,
		)
	} else if len(visible) > height {
		v.Title = titleWithCounter(" Sessions ", fmt.Sprintf(" [%d/%d] ", selectedVisible, len(visible)), w)
	} else {
		v.Title = " Sessions "
	}
}
