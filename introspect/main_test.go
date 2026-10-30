package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

// fakeGoogle serves tokeninfo for validToken and rejects everything else.
const validToken = "ya29.valid&token=with special/chars"

func fakeGoogle(t *testing.T, calls *int) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		*calls++
		if r.PostFormValue("access_token") != validToken {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error_description":"Invalid Value"}`))
			return
		}
		w.Write([]byte(`{"aud":"client.apps.googleusercontent.com","sub":"1234","scope":"openid email","exp":"1700000000","email":"user@example.org","email_verified":"true"}`))
	}))
}

func post(t *testing.T, h http.Handler, form url.Values) map[string]any {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/introspect/", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json; charset=utf-8" {
		t.Fatalf("Content-Type = %q", ct)
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("body %q: %v", rec.Body.String(), err)
	}
	return got
}

func TestValidToken(t *testing.T) {
	var calls int
	google := fakeGoogle(t, &calls)
	defer google.Close()

	got := post(t, newIntrospector(google.URL, time.Second), url.Values{"token": {validToken}})
	want := map[string]any{
		"active":     true,
		"scope":      "openid email",
		"sub":        "1234",
		"username":   "user@example.org",
		"email":      "user@example.org",
		"exp":        float64(1700000000), // a JSON number, decoded as float64
		"token_type": "bearer",
		"aud":        "client.apps.googleusercontent.com",
	}
	if len(got) != len(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s = %#v, want %#v", k, got[k], v)
		}
	}
}

func TestInactive(t *testing.T) {
	var calls int
	google := fakeGoogle(t, &calls)
	defer google.Close()
	h := newIntrospector(google.URL, time.Second)

	for name, form := range map[string]url.Values{
		"invalid token": {"token": {"bogus"}},
		"empty token":   {"token": {""}},
		"no token":      {},
	} {
		if got := post(t, h, form); len(got) != 1 || got["active"] != false {
			t.Errorf("%s: got %v, want {active:false}", name, got)
		}
	}
	if calls != 1 {
		t.Errorf("Google called %d times, want 1 (only for the non-empty token)", calls)
	}
}

func TestGoogleUnavailable(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(500 * time.Millisecond)
	}))
	defer slow.Close()
	closed := httptest.NewServer(http.NotFoundHandler())
	closed.Close()

	for name, h := range map[string]*introspector{
		"timeout": newIntrospector(slow.URL, 50*time.Millisecond),
		"down":    newIntrospector(closed.URL, time.Second),
	} {
		if got := post(t, h, url.Values{"token": {validToken}}); got["active"] != false {
			t.Errorf("%s: got %v, want {active:false}", name, got)
		}
	}
}

func TestOnlyPost(t *testing.T) {
	rec := httptest.NewRecorder()
	newIntrospector("http://unused", time.Second).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/introspect/", nil))
	if rec.Code != http.StatusInternalServerError || rec.Body.String() != "only POST supported" {
		t.Errorf("got %d %q", rec.Code, rec.Body.String())
	}
}

func TestNumber(t *testing.T) {
	for _, tc := range []struct {
		in, want any
	}{
		{"1700000000", int64(1700000000)},
		{"soon", "soon"},
		{float64(1700000000), float64(1700000000)},
		{nil, nil},
	} {
		if got := number(tc.in); got != tc.want {
			t.Errorf("number(%#v) = %#v, want %#v", tc.in, got, tc.want)
		}
	}
}
