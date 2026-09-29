"""Smart-HTTP Git server over `git http-backend`, or a server that answers 401 to everything.

Usage: python3 githttp.py <port> <project root> serve|deny

Infrahub refuses to create a repository it can't clone, so the unreachable fixtures are created
while this serves them, then the server is stopped (connection refused) or restarted with `deny`
(401, read as a credential error).
"""

import http.server
import os
import socket
import subprocess
import sys
from urllib.parse import urlsplit

PORT, ROOT, MODE = int(sys.argv[1]), sys.argv[2], sys.argv[3]


class Handler(http.server.BaseHTTPRequestHandler):
    def _deny(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="scn"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _backend(self) -> None:
        url = urlsplit(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        env = {
            **os.environ,
            "GIT_PROJECT_ROOT": ROOT,
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": url.path,
            "QUERY_STRING": url.query,
            "REQUEST_METHOD": self.command,
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(len(body)),
            "REMOTE_ADDR": self.client_address[0],
        }
        if self.headers.get("Git-Protocol"):
            env["GIT_PROTOCOL"] = self.headers["Git-Protocol"]
        out = subprocess.run(["git", "http-backend"], input=body, env=env, capture_output=True, check=False).stdout
        head, _, payload = out.partition(b"\r\n\r\n")
        status = 200
        headers = []
        for line in head.decode().split("\r\n"):
            key, _, value = line.partition(":")
            if key.lower() == "status":
                status = int(value.strip().split()[0])
            elif key:
                headers.append((key, value.strip()))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._deny() if MODE == "deny" else self._backend()

    do_POST = do_GET

    def log_message(self, *args: object) -> None:
        pass


class DualStackServer(http.server.ThreadingHTTPServer):
    # host.docker.internal resolves to an IPv6 address inside the containers.
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


DualStackServer(("::", PORT), Handler).serve_forever()
