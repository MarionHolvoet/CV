package main

import (
	"net/http"
	"os/exec"
	"testing"
	"time"
)

func TestServerHTTPHandlers(t *testing.T) {
	// Start the server as a subprocess
	cmd := exec.Command("go", "run", "main.go")
	if err := cmd.Start(); err != nil {
		t.Fatalf("Failed to start server: %v", err)
	}
	defer func() {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	}()
	// Wait for server to start
	time.Sleep(2 * time.Second)

	// Test /marion endpoint
	resp, err := http.Get("http://localhost:12345/marion")
	if err != nil {
		t.Fatalf("Failed to GET /marion: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected 200 OK for /marion, got %d", resp.StatusCode)
	}
	_ = resp.Body.Close()

	// Test /resources/photo.jpg (should be 200 or 404)
	resp, err = http.Get("http://localhost:12345/resources/photo.jpg")
	if err != nil {
		t.Fatalf("Failed to GET /resources/photo.jpg: %v", err)
	}
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
		t.Errorf("Expected 200 or 404 for /resources/photo.jpg, got %d", resp.StatusCode)
	}
	_ = resp.Body.Close()
}
