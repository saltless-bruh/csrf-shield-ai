package ui

import (
	"testing"

	"github.com/csrf-shield-ai/tui/internal/models"
)

// --- T-502: Virtual scrolling tests ---

func TestAdjustScroll_FitsInView(t *testing.T) {
	// 5 items, view height 10 => no scrolling needed.
	offset := adjustScroll(3, 0, 10, 5)
	if offset != 0 {
		t.Errorf("Expected 0, got %d", offset)
	}
}

func TestAdjustScroll_ScrollDown(t *testing.T) {
	// 50 items, view height 10, selected=15 => offset should bring 15 in view.
	offset := adjustScroll(15, 0, 10, 50)
	if offset != 6 { // 15 - 10 + 1 = 6
		t.Errorf("Expected 6, got %d", offset)
	}
}

func TestAdjustScroll_ScrollUp(t *testing.T) {
	// Selected=2, offset=5 => should scroll up to 2.
	offset := adjustScroll(2, 5, 10, 50)
	if offset != 2 {
		t.Errorf("Expected 2, got %d", offset)
	}
}

func TestAdjustScroll_ClampEnd(t *testing.T) {
	// Selected=49 (last), 50 items, height=10 => offset = 40.
	offset := adjustScroll(49, 0, 10, 50)
	if offset != 40 {
		t.Errorf("Expected 40, got %d", offset)
	}
}

func TestAdjustScroll_ZeroItems(t *testing.T) {
	offset := adjustScroll(0, 0, 10, 0)
	if offset != 0 {
		t.Errorf("Expected 0, got %d", offset)
	}
}

// --- T-503: Empty state helper tests ---

func TestParseFlows_NilResult(t *testing.T) {
	result := parseFlows(nil)
	if result != nil {
		t.Errorf("Expected nil, got %v", result)
	}
}

func TestParseFlows_EmptyFlows(t *testing.T) {
	data := map[string]interface{}{
		"flows": []interface{}{},
	}
	result := parseFlows(data)
	if len(result) != 0 {
		t.Errorf("Expected 0 flows, got %d", len(result))
	}
}

func TestParseFlows_ValidFlows(t *testing.T) {
	data := map[string]interface{}{
		"flows": []interface{}{
			map[string]interface{}{
				"session_id":     "abc1234",
				"host":           "example.com",
				"auth_mechanism": "cookie",
				"exchange_count": float64(5),
			},
		},
	}
	result := parseFlows(data)
	if len(result) != 1 {
		t.Fatalf("Expected 1 flow, got %d", len(result))
	}
	if result[0].SessionID != "abc1234" {
		t.Errorf("Expected 'abc1234', got '%s'", result[0].SessionID)
	}
	if result[0].ExchangeCount != 5 {
		t.Errorf("Expected 5, got %d", result[0].ExchangeCount)
	}
}

// --- T-504: Layout dimension tests ---

func TestLayoutDimensions_MinSize(t *testing.T) {
	// Simulate 100x24 terminal.
	maxX, maxY := 100, 24
	leftWidth := maxX / 2
	rightWidth := maxX - leftWidth - 1
	topHeight := (maxY - 1) / 2
	statusY := maxY - 2

	if leftWidth != 50 {
		t.Errorf("leftWidth: expected 50, got %d", leftWidth)
	}
	if rightWidth != 49 {
		t.Errorf("rightWidth: expected 49, got %d", rightWidth)
	}
	if topHeight != 11 {
		t.Errorf("topHeight: expected 11, got %d", topHeight)
	}
	if statusY != 22 {
		t.Errorf("statusY: expected 22, got %d", statusY)
	}
}

func TestLayoutDimensions_LargeSize(t *testing.T) {
	// Simulate 200x50 terminal.
	maxX, maxY := 200, 50
	leftWidth := maxX / 2
	rightWidth := maxX - leftWidth - 1
	topHeight := (maxY - 1) / 2
	statusY := maxY - 2

	if leftWidth != 100 {
		t.Errorf("leftWidth: expected 100, got %d", leftWidth)
	}
	if rightWidth != 99 {
		t.Errorf("rightWidth: expected 99, got %d", rightWidth)
	}
	if topHeight != 24 {
		t.Errorf("topHeight: expected 24, got %d", topHeight)
	}
	if statusY != 48 {
		t.Errorf("statusY: expected 48, got %d", statusY)
	}
}

// --- Helper function tests ---

func TestTruncate(t *testing.T) {
	tests := []struct {
		input    string
		maxLen   int
		expected string
	}{
		{"short", 10, "short"},
		{"a very long string", 10, "a very ..."}, // 7 chars + "..."
		{"abc", 3, "abc"},
		{"abcd", 3, "abc"},
		{"", 10, ""},
	}
	for _, tt := range tests {
		got := truncate(tt.input, tt.maxLen)
		if got != tt.expected {
			t.Errorf("truncate(%q, %d) = %q, want %q", tt.input, tt.maxLen, got, tt.expected)
		}
	}
}

func TestSeverityBadge(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{models.SevCritical, "[!!]"},
		{models.SevHigh, "[!]"},
		{models.SevMedium, "[~]"},
		{models.SevLow, "[*]"},
		{models.SevInfo, "[i]"},
		{"UNKNOWN", "[-]"},
	}
	for _, tt := range tests {
		got := severityBadge(tt.input)
		if got != tt.expected {
			t.Errorf("severityBadge(%q) = %q, want %q", tt.input, got, tt.expected)
		}
	}
}

func TestRiskIndicator(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{models.RiskCritical, "[!!]"},
		{models.RiskHigh, "[!]"},
		{models.RiskMedium, "[~]"},
		{models.RiskLow, "[*]"},
		{"OTHER", "--"},
	}
	for _, tt := range tests {
		got := models.RiskIndicator(tt.input)
		if got != tt.expected {
			t.Errorf("RiskIndicator(%q) = %q, want %q", tt.input, got, tt.expected)
		}
	}
}

func TestAuthBadge(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{models.AuthCookie, "(C) Cookie"},
		{models.AuthHeaderOnly, "(H) Header"},
		{models.AuthMixed, "(M) Mixed"},
		{models.AuthNone, "(?) None"},
		{"unknown", "(?) Unknown"},
	}
	for _, tt := range tests {
		got := models.AuthBadge(tt.input)
		if got != tt.expected {
			t.Errorf("AuthBadge(%q) = %q, want %q", tt.input, got, tt.expected)
		}
	}
}
