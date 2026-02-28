// Package main is the entry point for the CSRF Shield AI TUI.
//
// Usage:
//
//	csrf-shield tui --input traffic.har
//
// Ref: CLI_TUI_PROPOSAL.md §10, spec/Tasks.md T-435
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/csrf-shield-ai/tui/internal/ui"
)

func main() {
	inputFile := flag.String("input", "", "Path to HAR file (required)")
	flag.Parse()

	if *inputFile == "" {
		fmt.Fprintf(os.Stderr, "Usage: csrf-shield tui --input <file.har>\n\n")
		fmt.Fprintf(os.Stderr, "  --input string  Path to HAR file (required)\n")
		os.Exit(1)
	}

	// Validate input file exists.
	if _, err := os.Stat(*inputFile); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Error: file not found: %s\n", *inputFile)
		os.Exit(1)
	}

	// Resolve absolute path.
	absInput, err := filepath.Abs(*inputFile)
	if err != nil {
		log.Fatalf("Failed to resolve path: %v", err)
	}

	// Determine project root (go up from cmd/tui/).
	exe, err := os.Executable()
	if err != nil {
		exe, _ = os.Getwd()
	}
	projectRoot := filepath.Dir(filepath.Dir(filepath.Dir(exe)))

	// Try to find project root from working directory as fallback.
	if _, err := os.Stat(filepath.Join(projectRoot, "src", "ipc_server.py")); os.IsNotExist(err) {
		cwd, _ := os.Getwd()
		projectRoot = cwd
		// Walk up until we find src/ipc_server.py.
		for i := 0; i < 5; i++ {
			if _, err := os.Stat(filepath.Join(projectRoot, "src", "ipc_server.py")); err == nil {
				break
			}
			projectRoot = filepath.Dir(projectRoot)
		}
	}

	// Determine Python path.
	pythonPath := filepath.Join(projectRoot, ".venv", "bin", "python3")
	if _, err := os.Stat(pythonPath); os.IsNotExist(err) {
		pythonPath = "python3"
	}

	log.SetFlags(log.Ltime | log.Lshortfile)

	app := ui.NewApp(absInput, projectRoot, pythonPath)
	if err := app.Run(); err != nil {
		log.Fatalf("TUI error: %v", err)
	}
}
