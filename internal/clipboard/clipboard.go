// Package clipboard provides platform-specific clipboard access.
//
// Strategy per CLI_TUI_PROPOSAL.md §6.2:
//
//	Linux X11:    xclip -selection clipboard
//	Linux Wayland: wl-copy
//	macOS:        pbcopy
//	WSL:          clip.exe
//	OSC 52:       terminal escape sequence (iTerm2, Alacritty, kitty, …)
//	Fallback:     write to /tmp/csrf-shield-curl.txt
package clipboard

import (
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
)

// Copy copies text to the system clipboard.
// Returns a description of what happened.
func Copy(text string) string {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("pbcopy")
	case "linux":
		if os.Getenv("WAYLAND_DISPLAY") != "" {
			cmd = exec.Command("wl-copy")
		} else if _, err := exec.LookPath("xclip"); err == nil {
			cmd = exec.Command("xclip", "-selection", "clipboard")
		} else {
			// OSC 52 works in modern terminals (kitty, Alacritty, iTerm2).
			return osc52Write(text)
		}
	default:
		// Try clip.exe for WSL.
		if _, err := exec.LookPath("clip.exe"); err == nil {
			cmd = exec.Command("clip.exe")
		} else {
			// OSC 52 works in modern terminals.
			return osc52Write(text)
		}
	}

	cmd.Stdin = stringReader(text)
	if err := cmd.Run(); err != nil {
		return writeToFile(text)
	}
	return "Copied to clipboard"
}

// osc52Write copies text via the OSC 52 terminal escape sequence.
// Supported by iTerm2, Alacritty, kitty, foot, and others.
// Falls back to a temp file if writing to stdout fails.
func osc52Write(text string) string {
	b64 := base64.StdEncoding.EncodeToString([]byte(text))
	_, err := fmt.Fprintf(os.Stdout, "\033]52;c;%s\007", b64)
	if err != nil {
		return writeToFile(text)
	}
	return "Copied via OSC 52 (check terminal clipboard)"
}

func writeToFile(text string) string {
	path := "/tmp/csrf-shield-curl.txt"
	if err := os.WriteFile(path, []byte(text), 0644); err != nil {
		return fmt.Sprintf("Failed to write: %v", err)
	}
	return fmt.Sprintf("Written to %s", path)
}

type stringReaderImpl struct {
	data []byte
	pos  int
}

func stringReader(s string) *stringReaderImpl {
	return &stringReaderImpl{data: []byte(s)}
}

func (r *stringReaderImpl) Read(p []byte) (int, error) {
	if r.pos >= len(r.data) {
		return 0, io.EOF
	}
	n := copy(p, r.data[r.pos:])
	r.pos += n
	return n, nil
}
