package ipc

import (
	"fmt"
	"log"
	"time"
)

const (
	pingInterval = 5 * time.Second
	pingTimeout  = 10 * time.Second
)

// HealthMonitor runs periodic ping checks against the backend.
type HealthMonitor struct {
	client  *Client
	onError func(error)
	stop    chan struct{}
}

// NewHealthMonitor creates a health monitor for the IPC client.
func NewHealthMonitor(client *Client, onError func(error)) *HealthMonitor {
	return &HealthMonitor{
		client:  client,
		onError: onError,
		stop:    make(chan struct{}),
	}
}

// Start begins the periodic health check loop.
func (h *HealthMonitor) Start() {
	go h.loop()
}

// Stop terminates the health check loop.
func (h *HealthMonitor) Stop() {
	close(h.stop)
}

func (h *HealthMonitor) loop() {
	ticker := time.NewTicker(pingInterval)
	defer ticker.Stop()

	for {
		select {
		case <-h.stop:
			return
		case <-ticker.C:
			if err := h.ping(); err != nil {
				log.Printf("Health check failed: %v", err)
				if h.onError != nil {
					h.onError(err)
				}
			}
		}
	}
}

func (h *HealthMonitor) ping() error {
	done := make(chan error, 1)

	go func() {
		resp, err := h.client.Call("ping", map[string]interface{}{})
		if err != nil {
			done <- fmt.Errorf("ping failed: %w", err)
			return
		}
		if resp.Error != nil {
			done <- fmt.Errorf("ping error: %s", resp.Error.Message)
			return
		}
		done <- nil
	}()

	select {
	case err := <-done:
		return err
	case <-time.After(pingTimeout):
		return fmt.Errorf("ping timeout after %v", pingTimeout)
	case <-h.stop:
		return nil
	}
}
