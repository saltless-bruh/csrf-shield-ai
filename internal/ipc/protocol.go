// Package ipc implements the NDJSON IPC client for communicating
// with the Python analysis backend.
//
// Ref: CLI_TUI_PROPOSAL.md §3.2
package ipc

// Request is a JSON-RPC-like request sent to the Python backend.
type Request struct {
	ID     int                    `json:"id"`
	Method string                 `json:"method"`
	Params map[string]interface{} `json:"params"`
}

// Response is a successful response from the Python backend.
type Response struct {
	ID     int         `json:"id"`
	Result interface{} `json:"result,omitempty"`
}

// ErrorDetail is the error payload in an error response.
type ErrorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// ErrorResponse is an error response from the Python backend.
type ErrorResponse struct {
	ID    int         `json:"id"`
	Error ErrorDetail `json:"error"`
}

// ProgressEvent is a progress notification during analysis.
type ProgressEvent struct {
	ID       int      `json:"id"`
	Progress Progress `json:"progress"`
}

// Progress holds the progress details.
type Progress struct {
	Status       string `json:"status"`
	SessionID    string `json:"session_id"`
	SessionIndex int    `json:"session_index"`
	SessionTotal int    `json:"session_total"`
	Step         string `json:"step"`
	StepCurrent  int    `json:"step_current"`
	StepTotal    int    `json:"step_total"`
	Percent      int    `json:"percent"`
}

// RawMessage is used for initial parsing to determine message type.
type RawMessage struct {
	ID       int          `json:"id"`
	Result   interface{}  `json:"result,omitempty"`
	Error    *ErrorDetail `json:"error,omitempty"`
	Progress *Progress    `json:"progress,omitempty"`
}
