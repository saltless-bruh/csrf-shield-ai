package ipc

import (
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
	buf := make([]byte, 4096)
	for {
		n, err := c.stderr.Read(buf)
		if n > 0 {
			log.Printf("[python stderr] %s", string(buf[:n]))
		}
		if err != nil {
			return
		}
	}
}
