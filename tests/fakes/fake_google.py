"""Fake Google OAuth endpoints for the proxy tests.

The proxy container resolves www.googleapis.com and accounts.google.com to this
container (Docker network aliases) and trusts the test CA, so the proxy and the
introspection endpoint run unmodified against it.

Port 443 (TLS) serves the Google endpoints the proxy uses:
  GET  /.well-known/openid-configuration   OIDC discovery
  GET  /oauth2/v3/certs                    JWKS (the test signing key)
  POST /oauth2/v3/tokeninfo                access token validation

Port 8080 (plain HTTP) is the control API used by the tests:
  POST /_reset    forget tokens, zero the call counters, and leave the outage mode
  POST /_tokens   {"token": "...", "info": {...}} makes tokeninfo accept a token
  POST /_mode     {"tokeninfo": "ok" | "unavailable"}
  GET  /_calls    how many times each Google endpoint was called
  GET  /_health

Standard library only, so it runs on a stock python image.
"""

import json
import os
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ISSUER = "https://accounts.google.com"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
    "response_types_supported": ["code", "token", "id_token"],
    "subject_types_supported": ["public"],
    "id_token_signing_alg_values_supported": ["RS256"],
}

with open(os.environ["JWKS_FILE"], "rb") as f:
    JWKS = f.read()


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.tokens = {}
            self.calls = {"discovery": 0, "jwks": 0, "tokeninfo": 0}
            self.tokeninfo_mode = "ok"

    def count(self, endpoint):
        with self.lock:
            self.calls[endpoint] += 1


state = State()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_json(self, status, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))


class GoogleHandler(Handler):
    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route()

    def route(self):
        url = urlsplit(self.path)
        if url.path == "/.well-known/openid-configuration":
            state.count("discovery")
            self.send_json(200, DISCOVERY)
        elif url.path == "/oauth2/v3/certs":
            state.count("jwks")
            self.send_json(200, JWKS)
        elif url.path == "/oauth2/v3/tokeninfo":
            params = parse_qs(url.query)
            if self.command == "POST":
                params.update(parse_qs(self.read_body().decode()))
            self.tokeninfo(params.get("access_token", [""])[0])
        else:
            self.send_json(404, {"error": "not_found"})

    def tokeninfo(self, token):
        state.count("tokeninfo")
        with state.lock:
            mode = state.tokeninfo_mode
            info = state.tokens.get(token)
        if mode == "unavailable":
            self.send_json(503, {"error": "backendError"})
        elif info is None:
            # What Google returns for unknown, malformed, or expired tokens.
            self.send_json(400, {"error": "invalid_token", "error_description": "Invalid Value"})
        else:
            self.send_json(200, info)


class ControlHandler(Handler):
    def do_GET(self):
        if self.path == "/_calls":
            with state.lock:
                self.send_json(200, dict(state.calls))
        elif self.path == "/_health":
            self.send_json(200, {"ok": True})
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        body = json.loads(self.read_body() or b"{}")
        if self.path == "/_reset":
            state.reset()
        elif self.path == "/_tokens":
            with state.lock:
                state.tokens[body["token"]] = body["info"]
        elif self.path == "/_mode":
            with state.lock:
                state.tokeninfo_mode = body["tokeninfo"]
        else:
            self.send_json(404, {"error": "not_found"})
            return
        self.send_json(200, {"ok": True})


def main():
    google = ThreadingHTTPServer(("0.0.0.0", 443), GoogleHandler)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(os.environ["TLS_CERT"], os.environ["TLS_KEY"])
    google.socket = context.wrap_socket(google.socket, server_side=True)
    control = ThreadingHTTPServer(("0.0.0.0", 8080), ControlHandler)

    threading.Thread(target=control.serve_forever, daemon=True).start()
    google.serve_forever()


if __name__ == "__main__":
    main()
