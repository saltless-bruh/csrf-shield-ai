// Package models defines Go structs mirroring the Python dataclasses
// used in the CSRF Shield AI analysis pipeline.
//
// JSON struct tags match the exact IPC serialization values defined in
// CLI_TUI_PROPOSAL.md §3.2.
//
// Ref: spec/Tasks.md T-436
package models

import "strings"

// Severity levels — UPPERCASE values matching Python Severity enum.
const (
	SevCritical = "CRITICAL"
	SevHigh     = "HIGH"
	SevMedium   = "MEDIUM"
	SevLow      = "LOW"
	SevInfo     = "INFO"
)

// Risk levels — UPPERCASE values matching Python RiskLevel enum.
const (
	RiskCritical = "CRITICAL"
	RiskHigh     = "HIGH"
	RiskMedium   = "MEDIUM"
	RiskLow      = "LOW"
)

// Auth mechanisms — lowercase values matching Python AuthMechanism enum.
const (
	AuthCookie     = "cookie"
	AuthHeaderOnly = "header_only"
	AuthMixed      = "mixed"
	AuthNone       = "none"
)

// ExchangeRef is the compact exchange reference used in Finding serialization.
// See CLI_TUI_PROPOSAL.md §3.2 "Finding.exchange serialization".
type ExchangeRef struct {
	Method string `json:"method"`
	URL    string `json:"url"`
	Status int    `json:"status"`
}

// HttpExchange represents the full raw HTTP exchange.
type HttpExchange struct {
	RequestMethod      string            `json:"request_method"`
	RequestURL         string            `json:"request_url"`
	RequestHeaders     map[string]string `json:"request_headers"`
	RequestCookies     map[string]string `json:"request_cookies"`
	RequestBody        *string           `json:"request_body"`
	RequestContentType string            `json:"request_content_type"`
	ResponseStatus     int               `json:"response_status"`
	ResponseHeaders    map[string]string `json:"response_headers"`
	ResponseBody       *string           `json:"response_body"`
	Timestamp          *string           `json:"timestamp"`
}

// Finding represents a single static analysis finding.
type Finding struct {
	RuleID      string      `json:"rule_id"`
	RuleName    string      `json:"rule_name"`
	Severity    string      `json:"severity"`
	Description string      `json:"description"`
	Evidence    string      `json:"evidence"`
	Exchange    ExchangeRef `json:"exchange"`
}

// FlowSummary is a session flow summary from list_flows.
type FlowSummary struct {
	SessionID     string `json:"session_id"`
	Host          string `json:"host"`
	AuthMechanism string `json:"auth_mechanism"`
	ExchangeCount int    `json:"exchange_count"`
}

// AnalysisResultSummary is the session-level aggregate from analyze_flow.
type AnalysisResultSummary struct {
	RiskScore        int      `json:"risk_score"`
	RiskLevel        string   `json:"risk_level"`
	MLProbabilityMax *float64 `json:"ml_probability_max"`
	StaticScoreMax   float64  `json:"static_score_max"`
}

// ExchangeResult is the per-exchange analysis result.
type ExchangeResult struct {
	Endpoint        string                 `json:"endpoint"`
	HTTPMethod      string                 `json:"http_method"`
	RiskScore       int                    `json:"risk_score"`
	RiskLevel       string                 `json:"risk_level"`
	Findings        []Finding              `json:"findings"`
	MLProbability   *float64               `json:"ml_probability"`
	StaticScore     float64                `json:"static_score"`
	FeatureVector   map[string]interface{} `json:"feature_vector"`
	Recommendations []string               `json:"recommendations"`
}

// SessionAnalysis is the full analyze_flow response.
type SessionAnalysis struct {
	SessionID string                `json:"session_id"`
	Status    string                `json:"status,omitempty"`
	Summary   AnalysisResultSummary `json:"summary"`
	Results   []ExchangeResult      `json:"results"`
}

// AppState represents the TUI lifecycle state.
type AppState int

const (
	StateLaunch AppState = iota
	StateLoading
	StateBrowsing
	StateAnalyzing
	StateExporting
	StateExit
	StateError
)

// String returns the human-readable state name.
func (s AppState) String() string {
	switch s {
	case StateLaunch:
		return "LAUNCH"
	case StateLoading:
		return "LOADING"
	case StateBrowsing:
		return "BROWSING"
	case StateAnalyzing:
		return "ANALYZING"
	case StateExporting:
		return "EXPORTING"
	case StateExit:
		return "EXIT"
	case StateError:
		return "ERROR"
	default:
		return "UNKNOWN"
	}
}

// RiskColor returns the terminal color code for a risk level.
func RiskColor(level string) string {
	switch level {
	case RiskLow:
		return "\033[1;32m" // Bright Green
	case RiskMedium:
		return "\033[1;33m" // Bright Yellow
	case RiskHigh:
		return "\033[38;5;208m" // Dark Orange (256-color)
	case RiskCritical:
		return "\033[1;31m" // Bright Red
	default:
		return "\033[0m"
	}
}

// RiskIndicator returns the badge string for a risk level.
func RiskIndicator(level string) string {
	switch level {
	case RiskCritical:
		return "[!!]"
	case RiskHigh:
		return "[!]"
	case RiskMedium:
		return "[~]"
	case RiskLow:
		return "[*]"
	default:
		return "--"
	}
}

// AuthBadge returns the display badge for an auth mechanism.
func AuthBadge(auth string) string {
	switch auth {
	case AuthCookie:
		return "(C) Cookie"
	case AuthHeaderOnly:
		return "(H) Header"
	case AuthMixed:
		return "(M) Mixed"
	case AuthNone:
		return "(?) None"
	default:
		return "(?) Unknown"
	}
}

// BodyTypeBadge derives the body type badge from content type.
func BodyTypeBadge(contentType string) string {
	switch {
	case strings.Contains(contentType, "form-urlencoded"):
		return "[Form]"
	case strings.Contains(contentType, "multipart"):
		return "[Multi]"
	case strings.Contains(contentType, "json"):
		return "[JSON]"
	case strings.Contains(contentType, "text/plain"):
		return "[Text]"
	default:
		return "[None]"
	}
}
