package main

import (
	"crypto/hmac"
	"crypto/sha1"
	"encoding/hex"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"strings"
)

func marion(w http.ResponseWriter, r *http.Request) {
	// TODO: revert to marion.html once testing is done
	http.ServeFile(w, r, "./index.html")
}

// code from https://stackoverflow.com/questions/59521105/github-secret-token-verification
func IsValidSignature(r *http.Request, key string) bool {
	gotHash := strings.SplitN(r.Header.Get("X-Hub-Signature"), "=", 2)
	if gotHash[0] != "sha1" {
		return false
	}
	defer r.Body.Close()
	b, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Printf("Cannot read the request body: %s\n", err)
		return false
	}
	hash := hmac.New(sha1.New, []byte(key))
	if _, err := hash.Write(b); err != nil {
		log.Printf("Cannot compute the HMAC for request: %s\n", err)
		return false
	}
	return hex.EncodeToString(hash.Sum(nil)) == gotHash[1]
}

func exit(w http.ResponseWriter, r *http.Request) {
	if IsValidSignature(r, os.Getenv("GITHUB_WEBHOOK_SECRET")) {
		http.Error(w, "Exiting", http.StatusNotFound)
		os.Exit(http.StatusNotFound)
	}
}

func main() {
	// Serve static assets (photo, etc.) from ./resources/ under the /resources/ URL prefix.
	// This avoids exposing main.go and other source files at the root.
	http.Handle("/resources/", http.StripPrefix("/resources/", http.FileServer(http.Dir("./resources"))))
	http.HandleFunc("/marion", marion)
	http.HandleFunc("/exit", exit)
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/marion", http.StatusFound)
	})

	port := ":12345"
	log.Println("Starting web server on port", port)
	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
