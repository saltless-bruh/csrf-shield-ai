// Package ui implements the TUI application using gocui.
//
// Ref: CLI_TUI_PROPOSAL.md §4
package ui

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/awesome-gocui/gocui"

	"github.com/csrf-shield-ai/tui/internal/ipc"
	"github.com/csrf-shield-ai/tui/internal/models"
)

const (
	minTermWidth  = 100
	minTermHeight = 24
)

// Panel names for gocui views.
const (
	PanelSessions    = "sessions"
	PanelExchanges   = "exchanges"
	PanelAnalysis    = "analysis"
	PanelAnalysisHdr = "analysis_hdr" // pinned header strip for Panel 3 (M1)
	PanelStatus      = "statusbar"
)

// ActivePanel tracks which panel has focus.
type ActivePanel int

const (
	PanelIDSessions ActivePanel = iota
	PanelIDExchanges
	PanelIDAnalysis
)

// App is the main TUI application.
type App struct {
	gui   *gocui.Gui
	state models.AppState

	// Data from backend.
	flows          []models.FlowSummary
	analyses       map[string]*models.SessionAnalysis
	flowExchanges  map[string][]models.HttpExchange
	selectedIdx    int
	exchIdx        int
	activePanel    ActivePanel
	sessionFilter  string // T-505 filter string for Panel 1 (sessions)
	exchangeFilter string // T-505 filter string for Panel 2 (exchanges)
	sessionScroll  int    // T-502: virtual scroll offset for sessions
	exchScroll     int    // T-502: virtual scroll offset for exchanges
	analysisScroll int    // T-[M3]: virtual scroll offset for Panel 3

	// IPC.
	client  *ipc.Client
	health  *ipc.HealthMonitor
	harPath string

	// Export form state.
	exportFocusIdx   int    // 0:Format, 1:Scope, 2:Path
	exportFormat     string // "json" or "html"
	exportScope      string // "selected" or "all"
	exportPath       string
	exportPathEdited bool

	// Toast.
	toastMsg  string
	toastTime time.Time

	// Engine status.
	engineStatus string

	// Analysis spinner.
	analyzingSessionID string       // session currently being analyzed
	spinnerFrame       int          // cycles for spinner animation
	loadingTicker      *time.Ticker // loading screen animation ticker

	// Scroll offset for finding detail modal.
	findingScroll int

	// Error message.
	errorMsg string

	mu sync.Mutex
}

// isAnyModalOpen returns true when any popup modal is currently visible.
// Used by global keybinding handlers to ensure modals capture all input.
// Ref: CLI_TUI_PROPOSAL.md §7 — "all global keybindings are inactive" when modal open.
func (a *App) isAnyModalOpen(g *gocui.Gui) bool {
	for _, name := range []string{"help", "findingmodal", "exportmodal", "filtermodal", "quitmodal", "rawmodal_req", "rawmodal_resp"} {
		if _, err := g.View(name); err == nil {
			return true
		}
	}
	return false
}

// NewApp creates a new TUI application.
func NewApp(harPath string, projectRoot string, pythonPath string) *App {
	app := &App{
		state:         models.StateLoading,
		analyses:      make(map[string]*models.SessionAnalysis),
		flowExchanges: make(map[string][]models.HttpExchange),
		harPath:       harPath,
		engineStatus:  "Idle",
	}

	app.client = ipc.NewClient(projectRoot, pythonPath)
	app.client.SetProgressHandler(app.handleProgress)
	app.client.SetCrashHandler(app.handleCrash)

	app.health = ipc.NewHealthMonitor(app.client, func(err error) {
		app.setError(fmt.Sprintf("Backend not responding: %v", err))
	})

	return app
}

// Run starts the TUI main loop.
func (a *App) Run() error {
	// Start backend.
	if err := a.client.Start(); err != nil {
		return fmt.Errorf("failed to start backend: %w", err)
	}
	defer a.client.Stop()

	// Load HAR file.
	go a.loadHAR()

	// Create gocui.
	g, err := gocui.NewGui(gocui.OutputNormal, true)
	if err != nil {
		return fmt.Errorf("failed to create GUI: %w", err)
	}
	defer g.Close()

	a.gui = g
	g.SetManagerFunc(a.layout)
	g.Cursor = false
	g.Mouse = false

	if err := a.setupKeybindings(g); err != nil {
		return fmt.Errorf("keybindings: %w", err)
	}

	// Start health monitor.
	a.health.Start()
	defer a.health.Stop()

	// Main loop.
	if err := g.MainLoop(); err != nil && err != gocui.ErrQuit {
		return err
	}
	return nil
}

// layout is the gocui manager function that creates/resizes views.
func (a *App) layout(g *gocui.Gui) error {
	maxX, maxY := g.Size()

	// Check minimum terminal size.
	if maxX < minTermWidth || maxY < minTermHeight {
		v, err := g.SetView("toosmall", 0, 0, maxX-1, maxY-1, 0)
		if err != nil && err != gocui.ErrUnknownView {
			return err
		}
		v.Clear()
		fmt.Fprintf(v, "\n\n  Terminal too small (%dx%d). Need at least %dx%d. Please resize.",
			maxX, maxY, minTermWidth, minTermHeight)
		return nil
	}
	_ = g.DeleteView("toosmall")

	// Handle error state.
	if a.state == models.StateError {
		return a.layoutError(g, maxX, maxY)
	}

	// Handle loading state.
	if a.state == models.StateLoading {
		return a.layoutLoading(g, maxX, maxY)
	}

	// Normal 3-panel layout (§4, §9.4).
	leftWidth := maxX / 2
	rightWidth := maxX - leftWidth - 1
	topHeight := (maxY - 1) / 2
	statusY := maxY - 2

	// Panel 1: Sessions (top left)
	if v, err := g.SetView(PanelSessions, 0, 0, leftWidth-1, topHeight-1, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Title = " Sessions "
		v.Highlight = true
		v.SelBgColor = gocui.ColorBlue
		v.SelFgColor = gocui.ColorWhite
	}

	// Panel 2: Exchanges (bottom left)
	if v, err := g.SetView(PanelExchanges, 0, topHeight, leftWidth-1, statusY, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Title = " Exchanges "
	}

	// Panel 3 header: pinned strip — risk score + ML/static (3 content lines).
	if hdrV, err := g.SetView(PanelAnalysisHdr, leftWidth, 0, leftWidth+rightWidth, 4, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		hdrV.Title = " Analysis Engine "
		hdrV.Wrap = true
	}
	// Panel 3 body: scrollable findings/features/recommendations (shares top border with header).
	if v, err := g.SetView(PanelAnalysis, leftWidth, 4, leftWidth+rightWidth, statusY, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Wrap = true
	}

	// Status bar (bottom, full width)
	if v, err := g.SetView(PanelStatus, -1, statusY, maxX, maxY, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Frame = false
		v.BgColor = gocui.ColorBlue
		v.FgColor = gocui.ColorWhite
	}

	// Update active panel borders.
	a.updatePanelBorders(g)

	// Render content.
	a.renderSessions(g)
	a.renderExchanges(g)
	a.renderAnalysis(g)
	a.renderStatusBar(g)

	// Keep modal focus stable when any modal is open.
	if a.isAnyModalOpen(g) {
		for _, modalName := range []string{"exportmodal", "filtermodal", "quitmodal", "findingmodal", "help", "rawmodal_resp", "rawmodal_req"} {
			if _, err := g.View(modalName); err == nil {
				if current := g.CurrentView(); current == nil || current.Name() != modalName {
					if _, err := g.SetCurrentView(modalName); err != nil {
						log.Printf("SetCurrentView(%s): %v", modalName, err)
					}
				}
				break
			}
		}
	} else {
		panelName := PanelSessions
		switch a.activePanel {
		case PanelIDExchanges:
			panelName = PanelExchanges
		case PanelIDAnalysis:
			panelName = PanelAnalysis
		}
		if current := g.CurrentView(); current == nil || current.Name() != panelName {
			if _, err := g.SetCurrentView(panelName); err != nil {
				log.Printf("SetCurrentView(%s): %v", panelName, err)
			}
		}
	}

	return nil
}

func (a *App) layoutLoading(g *gocui.Gui, maxX, maxY int) error {
	v, err := g.SetView("loading", maxX/4, maxY/3, maxX*3/4, maxY*2/3, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	v.Clear()

	// Animated spinner for loading state (T-861).
	a.mu.Lock()
	frame := a.spinnerFrame
	a.mu.Unlock()
	spinnerChars := []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}
	spinner := spinnerChars[frame%len(spinnerChars)]

	// Progress bar animation.
	barWidth := 20
	filled := (frame * 3) % (barWidth + 1)
	bar := ""
	for i := 0; i < barWidth; i++ {
		if i < filled {
			bar += "█"
		} else {
			bar += "░"
		}
	}

	fmt.Fprintf(v, "\n")
	fmt.Fprintf(v, "           CSRF Shield AI v1.0\n\n")
	fmt.Fprintf(v, "    %s Loading: %s\n", spinner, a.harPath)
	fmt.Fprintf(v, "    Spawning analysis backend...\n\n")
	fmt.Fprintf(v, "    [%s]\n\n", bar)
	fmt.Fprintf(v, "    Press <q> to abort.")

	// Start loading spinner if not already running.
	if a.loadingTicker == nil {
		a.loadingTicker = time.NewTicker(200 * time.Millisecond)
		go func() {
			for range a.loadingTicker.C {
				a.mu.Lock()
				a.spinnerFrame = (a.spinnerFrame + 1) % 40
				a.mu.Unlock()
				g.Update(func(g *gocui.Gui) error { return nil })
			}
		}()
	}

	return nil
}

func (a *App) layoutError(g *gocui.Gui, maxX, maxY int) error {
	v, err := g.SetView("error", maxX/4, maxY/3, maxX*3/4, maxY*2/3, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	v.Clear()
	fmt.Fprintf(v, "\n")
	fmt.Fprintf(v, "           CSRF Shield AI v1.0\n\n")
	fmt.Fprintf(v, "    [ERROR] %s\n\n", a.errorMsg)
	fmt.Fprintf(v, "    Press <r> to restart or <q> to quit.")
	return nil
}

func (a *App) updatePanelBorders(g *gocui.Gui) {
	type panelEntry struct {
		name    string
		ownerID ActivePanel
	}
	entries := []panelEntry{
		{PanelSessions, PanelIDSessions},
		{PanelExchanges, PanelIDExchanges},
		{PanelAnalysisHdr, PanelIDAnalysis}, // both analysis views highlighted together
		{PanelAnalysis, PanelIDAnalysis},
	}

	for _, e := range entries {
		v, err := g.View(e.name)
		if err != nil {
			continue
		}
		if e.ownerID == a.activePanel {
			v.FrameColor = gocui.ColorWhite | gocui.AttrBold
			v.TitleColor = gocui.ColorWhite | gocui.AttrBold
			v.SelBgColor = gocui.ColorBlue
			v.SelFgColor = gocui.ColorWhite | gocui.AttrBold
		} else {
			v.FrameColor = gocui.ColorDefault
			v.TitleColor = gocui.ColorDefault
			v.SelBgColor = gocui.ColorDefault
			v.SelFgColor = gocui.ColorDefault
		}
	}
}

// loadHAR loads the HAR file via IPC.
func (a *App) loadHAR() {
	resp, err := a.client.Call("load_har", map[string]interface{}{
		"path": a.harPath,
	})
	if err != nil {
		a.setError(fmt.Sprintf("Failed to load HAR: %v", err))
		return
	}
	if resp.Error != nil {
		a.setError(fmt.Sprintf("%s: %s", resp.Error.Code, resp.Error.Message))
		return
	}

	// Parse flows from result.
	resultMap, ok := resp.Result.(map[string]interface{})
	if !ok {
		a.setError("Invalid flow response format")
		return
	}

	a.mu.Lock()
	a.flows = parseFlows(resultMap)
	a.state = models.StateBrowsing
	if a.loadingTicker != nil {
		a.loadingTicker.Stop()
		a.loadingTicker = nil
	}
	a.spinnerFrame = 0
	a.mu.Unlock()

	if a.gui != nil {
		a.gui.Update(func(g *gocui.Gui) error {
			_ = g.DeleteView("loading")
			return nil
		})
	}
}

func (a *App) setError(msg string) {
	a.mu.Lock()
	a.state = models.StateError
	a.errorMsg = msg
	a.mu.Unlock()

	if a.gui != nil {
		a.gui.Update(func(g *gocui.Gui) error { return nil })
	}
}

func (a *App) handleProgress(p ipc.Progress) {
	a.mu.Lock()
	a.engineStatus = fmt.Sprintf("Analyzing %d/%d... %s %d%%",
		p.SessionIndex, p.SessionTotal, p.Step, p.Percent)
	a.analyzingSessionID = p.SessionID
	sessionDone := (p.Percent == 100 || p.Status == "complete") && p.SessionID != ""
	if sessionDone {
		a.analyzingSessionID = ""
	}
	a.mu.Unlock()

	// Progressively fetch and cache results as each session completes (m4).
	if sessionDone {
		sid := p.SessionID
		go func() {
			r, err := a.client.Call("get_results", map[string]interface{}{
				"session_id": sid,
			})
			if err != nil || r.Error != nil {
				return
			}
			if rMap, ok := r.Result.(map[string]interface{}); ok {
				if analysis := parseAnalysis(rMap); analysis != nil {
					a.mu.Lock()
					a.analyses[sid] = analysis
					a.mu.Unlock()
				}
			}
			if a.gui != nil {
				a.gui.Update(func(g *gocui.Gui) error { return nil })
			}
		}()
	}

	if a.gui != nil {
		a.gui.Update(func(g *gocui.Gui) error { return nil })
	}
}

func (a *App) handleCrash(err error) {
	lines := a.client.LastStderrLines()
	msg := fmt.Sprintf("Backend process exited: %v", err)
	if len(lines) > 0 {
		msg += "\n\nLast backend output:\n" + strings.Join(lines, "\n")
	}
	a.setError(msg)
}

// showToast is defined in toast.go.

// parseFlows extracts FlowSummary list from IPC result map.
func parseFlows(result map[string]interface{}) []models.FlowSummary {
	flowsRaw, ok := result["flows"].([]interface{})
	if !ok {
		return nil
	}

	flows := make([]models.FlowSummary, 0, len(flowsRaw))
	for _, raw := range flowsRaw {
		m, ok := raw.(map[string]interface{})
		if !ok {
			continue
		}
		f := models.FlowSummary{
			SessionID:     strVal(m, "session_id"),
			Host:          strVal(m, "host"),
			AuthMechanism: strVal(m, "auth_mechanism"),
			ExchangeCount: intVal(m, "exchange_count"),
		}
		flows = append(flows, f)
	}
	return flows
}

func strVal(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func intVal(m map[string]interface{}, key string) int {
	if v, ok := m[key].(float64); ok {
		return int(v)
	}
	return 0
}

func (a *App) selectedFlow() *models.FlowSummary {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.selectedIdx >= 0 && a.selectedIdx < len(a.flows) {
		return &a.flows[a.selectedIdx]
	}
	return nil
}

func (a *App) selectedAnalysis() *models.SessionAnalysis {
	flow := a.selectedFlow()
	if flow == nil {
		return nil
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.analyses[flow.SessionID]
}

// fetchFlowExchangesAsync fetches all raw exchanges for a given session asynchronously
// and caches them in a.flowExchanges, then triggers a UI update.
func (a *App) fetchFlowExchangesAsync(sessionID string) {
	a.mu.Lock()
	if _, exists := a.flowExchanges[sessionID]; exists {
		a.mu.Unlock()
		return // Already cached or being fetched
	}
	// Insert a placeholder to prevent multiple fetches.
	a.flowExchanges[sessionID] = []models.HttpExchange{}
	a.mu.Unlock()

	go func() {
		resp, err := a.client.Call("get_flow_exchanges", map[string]interface{}{
			"session_id": sessionID,
		})
		if err != nil || resp.Error != nil {
			return
		}

		var exchanges []models.HttpExchange
		rawBytes, err := json.Marshal(resp.Result)
		if err != nil {
			return
		}
		if err := json.Unmarshal(rawBytes, &exchanges); err != nil {
			return
		}

		a.mu.Lock()
		a.flowExchanges[sessionID] = exchanges
		a.mu.Unlock()

		if a.gui != nil {
			a.gui.Update(func(g *gocui.Gui) error { return nil })
		}
	}()
}
