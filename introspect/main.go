// Implementation of RFC 7662 introspection endpoint
//
// mod_oauth2 verifies tokens against this endpoint (see oauth2.conf). Google access
// tokens are opaque and Google has no RFC 7662 endpoint, so we translate Google's
// tokeninfo response into an RFC 7662 response.
//
// httpd runs this binary as a CGI program (see site.conf), so there is no separate
// process to supervise. Standard library only.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/cgi"
	"net/url"
	"strconv"
	"time"
)

const tokeninfoURL = "https://www.googleapis.com/oauth2/v3/tokeninfo"

// Must stay below liboauth2's own 15s timeout for the introspection call.
const tokeninfoTimeout = 10 * time.Second

var inactive = map[string]any{"active": false}

type activeResponse struct {
	Active    bool   `json:"active"`
	Scope     any    `json:"scope"`
	Sub       any    `json:"sub"`
	Username  any    `json:"username"`
	Email     any    `json:"email"`
	Exp       any    `json:"exp"`
	TokenType string `json:"token_type"`
	Aud       any    `json:"aud"`
}

type introspector struct {
	tokeninfoURL string
	client       *http.Client
}

// tokeninfo returns Google's tokeninfo for the token, or nil if it is not valid.
func (i *introspector) tokeninfo(accessToken string) map[string]any {
	resp, err := i.client.PostForm(i.tokeninfoURL, url.Values{
		"access_token":    {accessToken},
		"token_type_hint": {"access_token"},
	})
	if err != nil {
		// Network failure or timeout. The token is in the body, not the logged URL.
		log.Printf("introspect: tokeninfo request failed: %v", err)
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		// Google answers invalid or expired tokens with a 4xx; that's routine.
		return nil
	}
	var info map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		log.Printf("introspect: tokeninfo response not JSON: %v", err)
		return nil
	}
	return info
}

// number converts a numeric string to a JSON number. tokeninfo returns exp as a string,
// but RFC 7662 makes it a number, and liboauth2 only checks exp when it is one.
// Anything else is returned unchanged.
func number(v any) any {
	s, ok := v.(string)
	if !ok {
		return v
	}
	n, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return v
	}
	return n
}

func (i *introspector) introspect(accessToken string) any {
	if accessToken == "" {
		return inactive
	}
	info := i.tokeninfo(accessToken)
	if info == nil {
		return inactive
	}
	return activeResponse{
		Active:    true,
		Scope:     info["scope"],
		Sub:       info["sub"],
		Username:  info["email"],
		Email:     info["email"],
		Exp:       number(info["exp"]),
		TokenType: "bearer",
		Aud:       info["aud"],
	}
}

func (i *introspector) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("only POST supported"))
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(i.introspect(r.PostFormValue("token")))
}

func newIntrospector(tokeninfoURL string, timeout time.Duration) *introspector {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	// Under CGI, client request headers arrive as HTTP_* environment variables, so
	// never take proxy settings from the environment (httpoxy).
	transport.Proxy = nil
	return &introspector{
		tokeninfoURL: tokeninfoURL,
		client:       &http.Client{Timeout: timeout, Transport: transport},
	}
}

func main() {
	// httpd timestamps CGI stderr lines itself.
	log.SetFlags(0)
	if err := cgi.Serve(newIntrospector(tokeninfoURL, tokeninfoTimeout)); err != nil {
		log.Fatalf("introspect: %v", err)
	}
}
