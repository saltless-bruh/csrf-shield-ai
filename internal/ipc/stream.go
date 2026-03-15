package ipc

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"sync"
)

const (
	// maxIPCMessageSize caps a single NDJSON message size exchanged with the
	// Python backend. Large HAR-derived payloads can exceed 1MB.
	maxIPCMessageSize = 16 * 1024 * 1024 // 16MB
)

// Stream provides buffered NDJSON read/write over io pipes.
type Stream struct {
	writer  io.Writer
	scanner *bufio.Scanner
	mu      sync.Mutex // protects writer
}

// NewStream creates a new NDJSON stream.
func NewStream(reader io.Reader, writer io.Writer) *Stream {
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 1024*1024), maxIPCMessageSize)
	return &Stream{
		writer:  writer,
		scanner: scanner,
	}
}

// Send writes a JSON request line to the stream.
func (s *Stream) Send(req Request) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	data, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}
	data = append(data, '\n')
	_, err = s.writer.Write(data)
	return err
}

// Receive reads and parses the next JSON line from the stream.
// Returns nil, io.EOF when the stream is closed.
func (s *Stream) Receive() (*RawMessage, error) {
	if !s.scanner.Scan() {
		if err := s.scanner.Err(); err != nil {
			return nil, fmt.Errorf("scan: %w", err)
		}
		return nil, io.EOF
	}

	var msg RawMessage
	if err := json.Unmarshal(s.scanner.Bytes(), &msg); err != nil {
		return nil, fmt.Errorf("unmarshal: %w", err)
	}
	return &msg, nil
}
