// Package ui implements the TUI application using gocui.
//
// Ref: CLI_TUI_PROPOSAL.md §4
package ui

import (
	"fmt"
	"log"
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
	PanelSessions  = "sessions"
	PanelExchanges = "exchanges"
	PanelAnalysis  = "analysis"
	PanelStatus    = "statusbar"
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
	flows         []models.FlowSummary
	analyses      map[string]*models.SessionAnalysis
	selectedIdx   int
	exchIdx       int
	activePanel   ActivePanel
	sessionScroll int // T-502: virtual scroll offset for sessions
	exchScroll    int // T-502: virtual scroll offset for exchanges

	// IPC.
	client  *ipc.Client
	health  *ipc.HealthMonitor
	harPath string

	// Toast.
	toastMsg  string
	toastTime time.Time

	// Engine status.
	engineStatus string

	// Error message.
	errorMsg string

	mu sync.Mutex
}

// NewApp creates a new TUI application.
func NewApp(harPath string, projectRoot string, pythonPath string) *App {
	app := &App{
		state:        models.StateLoading,
		analyses:     make(map[string]*models.SessionAnalysis),
		harPath:      harPath,
		engineStatus: "Idle",
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

	// Panel 3: Analysis Engine (right column, full height)
	if v, err := g.SetView(PanelAnalysis, leftWidth, 0, leftWidth+rightWidth, statusY, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Title = " Analysis Engine "
		v.Wrap = true
	}

	// Status bar (bottom, full width)
	if v, err := g.SetView(PanelStatus, 0, statusY+1, maxX-1, maxY-1, 0); err != nil {
		if err != gocui.ErrUnknownView {
			return err
		}
		v.Frame = false
	}

	// Update active panel borders.
	a.updatePanelBorders(g)

	// Render content.
	a.renderSessions(g)
	a.renderExchanges(g)
	a.renderAnalysis(g)
	a.renderStatusBar(g)

	// Set initial focus.
	panelName := PanelSessions
	switch a.activePanel {
	case PanelIDExchanges:
		panelName = PanelExchanges
	case PanelIDAnalysis:
		panelName = PanelAnalysis
	}
	if _, err := g.SetCurrentView(panelName); err != nil {
		log.Printf("SetCurrentView(%s): %v", panelName, err)
	}

	return nil
}

func (a *App) layoutLoading(g *gocui.Gui, maxX, maxY int) error {
	v, err := g.SetView("loading", maxX/4, maxY/3, maxX*3/4, maxY*2/3, 0)
	if err != nil && err != gocui.ErrUnknownView {
		return err
	}
	v.Clear()
	fmt.Fprintf(v, "\n")
	fmt.Fprintf(v, "           CSRF Shield AI v1.0\n\n")
	fmt.Fprintf(v, "    Loading: %s\n", a.harPath)
	fmt.Fprintf(v, "    Spawning analysis backend...\n\n")
	fmt.Fprintf(v, "    Press <q> to abort.")
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
	panels := []string{PanelSessions, PanelExchanges, PanelAnalysis}
	activeIdx := int(a.activePanel)

	for i, name := range panels {
		v, err := g.View(name)
		if err != nil {
			continue
		}
		if i == activeIdx {
			v.SelBgColor = gocui.ColorBlue
			v.SelFgColor = gocui.ColorWhite | gocui.AttrBold
		} else {
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
	a.mu.Lock()
	a.flows = parseFlows(resp.Result)
	a.state = models.StateBrowsing
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
	a.mu.Unlock()

	if a.gui != nil {
		a.gui.Update(func(g *gocui.Gui) error { return nil })
	}
}

func (a *App) handleCrash(err error) {
	a.setError(fmt.Sprintf("Backend process exited: %v", err))
}

func (a *App) showToast(msg string) {
	a.mu.Lock()
	a.toastMsg = msg
	a.toastTime = time.Now()
	a.mu.Unlock()

	// Auto-dismiss after 3s.
	go func() {
		time.Sleep(3 * time.Second)
		a.mu.Lock()
		if time.Since(a.toastTime) >= 3*time.Second {
			a.toastMsg = ""
		}
		a.mu.Unlock()
		if a.gui != nil {
			a.gui.Update(func(g *gocui.Gui) error { return nil })
		}
	}()
}

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
