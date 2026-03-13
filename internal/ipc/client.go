package ipc

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"sync/atomic"
)

// Client manages the lifecycle of the Python IPC backend process.
type Client struct {
	cmd        *exec.Cmd
	stream     *Stream
	nextID     atomic.Int64
	stderr     io.ReadCloser
	mu         sync.Mutex
	callbacks  map[int]chan *RawMessage
	done       chan struct{}
	onProgress func(Progress)
	onCrash    func(error)

	// stderr observability
	stderrMu      sync.Mutex
	stderrLines   []string // last 50 lines, for ERROR state display
	stderrLogFile *os.File // ~/.csrf-shield/backend.log
}

// NewClient creates a new IPC client. pythonPath should be the
// path to the python interpreter within the project's venv.
func NewClient(projectRoot string, pythonPath string) *Client {
	if pythonPath == "" {
		pythonPath = "python3"
	}
	serverScript := filepath.Join(projectRoot, "src", "ipc_server.py")

	c := &Client{
		callbacks: make(map[int]chan *RawMessage),
		done:      make(chan struct{}),
	}

	c.cmd = exec.Command(pythonPath, "-u", serverScript)
	c.cmd.Dir = projectRoot
	c.cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1")

	return c
}

// SetProgressHandler sets the callback for progress events.
func (c *Client) SetProgressHandler(fn func(Progress)) {
	c.onProgress = fn
}

// SetCrashHandler sets the callback for backend crashes.
func (c *Client) SetCrashHandler(fn func(error)) {
	c.onCrash = fn
}

// Start spawns the Python backend process and begins reading.
func (c *Client) Start() error {
	stdin, err := c.cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("stdin pipe: %w", err)
	}

	stdout, err := c.cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}

	c.stderr, err = c.cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("stderr pipe: %w", err)
	}

	if err := c.cmd.Start(); err != nil {
		return fmt.Errorf("start python: %w", err)
	}

	c.stream = NewStream(stdout, stdin)

	// Open ~/.csrf-shield/backend.log for stderr capture (create dir if needed).
	if home, err := os.UserHomeDir(); err == nil {
		logDir := filepath.Join(home, ".csrf-shield")
		if mkErr := os.MkdirAll(logDir, 0700); mkErr == nil {
			logPath := filepath.Join(logDir, "backend.log")
			if info, statErr := os.Stat(logPath); statErr == nil && info.Size() > 1<<20 {
				_ = os.Truncate(logPath, 0)
			}
			if f, openErr := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0600); openErr == nil {
				c.stderrLogFile = f
			}
		}
	}

	// Background reader goroutine.
	go c.readLoop()

	// Background stderr logger.
	go c.logStderr()

	return nil
}

// Call sends a request and waits for the response.
func (c *Client) Call(method string, params map[string]interface{}) (*RawMessage, error) {
	id := int(c.nextID.Add(1))
	ch := make(chan *RawMessage, 1)

	c.mu.Lock()
	c.callbacks[id] = ch
	c.mu.Unlock()

	defer func() {
		c.mu.Lock()
		delete(c.callbacks, id)
		c.mu.Unlock()
	}()

	req := Request{
		ID:     id,
		Method: method,
		Params: params,
	}

	if err := c.stream.Send(req); err != nil {
		return nil, fmt.Errorf("send %s: %w", method, err)
	}

	select {
	case msg := <-ch:
		return msg, nil
	case <-c.done:
		return nil, fmt.Errorf("backend closed")
	}
}

// Stop terminates the Python backend process.
func (c *Client) Stop() {
	close(c.done)
	if c.cmd.Process != nil {
		_ = c.cmd.Process.Kill()
	}
	_ = c.cmd.Wait()
	c.stderrMu.Lock()
	if c.stderrLogFile != nil {
		_ = c.stderrLogFile.Close()
		c.stderrLogFile = nil
	}
	c.stderrMu.Unlock()
}

func (c *Client) readLoop() {
	defer func() {
		if c.onCrash != nil {
			// Check if process exited abnormally.
			if err := c.cmd.Wait(); err != nil {
				c.onCrash(err)
			}
		}
	}()

	for {
		msg, err := c.stream.Receive()
		if err != nil {
			select {
			case <-c.done:
				return
			default:
				if err == io.EOF {
					if c.onCrash != nil {
						c.onCrash(fmt.Errorf("backend process closed"))
					}
					return
				}
				log.Printf("IPC read error: %v", err)
				continue
			}
		}

		// Route progress events.
		if msg.Progress != nil {
			if c.onProgress != nil {
				c.onProgress(*msg.Progress)
			}
			continue
		}

		// Route response to waiting caller.
		c.mu.Lock()
		ch, ok := c.callbacks[msg.ID]
		c.mu.Unlock()
		if ok {
			ch <- msg
		}
	}
}

func (c *Client) logStderr() {
	if c.stderr == nil {
		return
	}
	scanner := bufio.NewScanner(c.stderr)
	for scanner.Scan() {
		line := scanner.Text()
		log.Printf("[python stderr] %s", line)

		c.stderrMu.Lock()
		c.stderrLines = append(c.stderrLines, line)
		if len(c.stderrLines) > 50 {
			c.stderrLines = c.stderrLines[len(c.stderrLines)-50:]
		}
		if c.stderrLogFile != nil {
			_, _ = fmt.Fprintln(c.stderrLogFile, line)
		}
		c.stderrMu.Unlock()
	}
}

// LastStderrLines returns a copy of the last 50 lines of backend stderr.
// Safe to call from any goroutine.
func (c *Client) LastStderrLines() []string {
	c.stderrMu.Lock()
	defer c.stderrMu.Unlock()
	return append([]string{}, c.stderrLines...)
}
