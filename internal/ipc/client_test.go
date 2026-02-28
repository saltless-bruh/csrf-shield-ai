package ipc_test

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/csrf-shield-ai/tui/internal/ipc"
)

// findProjectRoot walks up from the test file to find the project root.
func findProjectRoot() string {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	for i := 0; i < 10; i++ {
		if _, err := os.Stat(filepath.Join(dir, "src", "ipc_server.py")); err == nil {
			return dir
		}
		dir = filepath.Dir(dir)
	}
	return ""
}

func findPython(root string) string {
	venv := filepath.Join(root, ".venv", "bin", "python3")
	if _, err := os.Stat(venv); err == nil {
		return venv
	}
	return "python3"
}

func TestIPCPingRoundTrip(t *testing.T) {
	root := findProjectRoot()
	if root == "" {
		t.Skip("Could not find project root")
	}

	client := ipc.NewClient(root, findPython(root))
	if err := client.Start(); err != nil {
		t.Fatalf("Failed to start backend: %v", err)
	}
	defer client.Stop()

	resp, err := client.Call("ping", map[string]interface{}{})
	if err != nil {
		t.Fatalf("Ping failed: %v", err)
	}
	if resp.Error != nil {
		t.Fatalf("Ping error: %s", resp.Error.Message)
	}

	status, ok := resp.Result["status"].(string)
	if !ok || status != "ok" {
		t.Errorf("Expected status 'ok', got %v", resp.Result["status"])
	}
	version, ok := resp.Result["version"].(string)
	if !ok || version != "1.0" {
		t.Errorf("Expected version '1.0', got %v", resp.Result["version"])
	}
}

func TestIPCLoadHarRoundTrip(t *testing.T) {
	root := findProjectRoot()
	if root == "" {
		t.Skip("Could not find project root")
	}

	harFile := filepath.Join(root, "data", "sample_har", "mixed_auth.har")
	if _, err := os.Stat(harFile); os.IsNotExist(err) {
		t.Skipf("Sample HAR not found: %s", harFile)
	}

	client := ipc.NewClient(root, findPython(root))
	if err := client.Start(); err != nil {
		t.Fatalf("Failed to start backend: %v", err)
	}
	defer client.Stop()

	resp, err := client.Call("load_har", map[string]interface{}{
		"path": harFile,
	})
	if err != nil {
		t.Fatalf("load_har failed: %v", err)
	}
	if resp.Error != nil {
		t.Fatalf("load_har error: %s", resp.Error.Message)
	}

	totalFlows, ok := resp.Result["total_flows"].(float64)
	if !ok || totalFlows < 1 {
		t.Errorf("Expected at least 1 flow, got %v", resp.Result["total_flows"])
	}
}

func TestIPCErrorResponse(t *testing.T) {
	root := findProjectRoot()
	if root == "" {
		t.Skip("Could not find project root")
	}

	client := ipc.NewClient(root, findPython(root))
	if err := client.Start(); err != nil {
		t.Fatalf("Failed to start backend: %v", err)
	}
	defer client.Stop()

	resp, err := client.Call("load_har", map[string]interface{}{
		"path": "/nonexistent/file.har",
	})
	if err != nil {
		t.Fatalf("Call failed unexpectedly: %v", err)
	}
	if resp.Error == nil {
		t.Fatal("Expected error response, got success")
	}
	if resp.Error.Code != "FILE_NOT_FOUND" {
		t.Errorf("Expected FILE_NOT_FOUND, got %s", resp.Error.Code)
	}
}
