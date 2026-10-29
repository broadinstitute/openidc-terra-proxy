"""Backend service for the proxy tests: answers every request with what it received.

The response is JSON: {"method", "path", "headers": [[name, value], ...], "body"}.
Headers are a list of pairs, not a dict, so tests can see duplicated headers.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Echo(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def echo(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        data = json.dumps({
            "method": self.command,
            "path": self.path,
            "headers": [[name, value] for name, value in self.headers.items()],
            "body": body.decode("utf-8", "replace"),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = echo


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Echo).serve_forever()
