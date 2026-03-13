package ui

import (
	"time"

	"github.com/awesome-gocui/gocui"
)

// showToast displays a transient message in the status bar for 3 seconds.
// Ref: CLI_TUI_PROPOSAL.md §5.4
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
