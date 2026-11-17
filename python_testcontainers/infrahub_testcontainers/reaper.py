from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    import socket
    from collections.abc import Callable

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
RYUK_ACKNOWLEDGEMENT = b"ACK\n"


class ComposeProjectReaper:
    """Registers compose projects with Ryuk, the testcontainers cleanup container.

    The registrations share one connection that stays open for the life of the process. Once every
    connection to Ryuk has been closed for its reconnection timeout, Ryuk removes the containers,
    networks and volumes of the registered projects, so the stacks are removed even when the process
    is killed before its own teardown runs.
    """

    def __init__(self, connect: Callable[[], socket.socket], acknowledgement_timeout: float) -> None:
        self._connect = connect
        self._acknowledgement_timeout = acknowledgement_timeout
        self._connection: socket.socket | None = None
        self._lock = threading.Lock()

    def register(self, project_name: str) -> None:
        """Register a compose project and wait until Ryuk acknowledges it.

        Raises:
            ConnectionError: Ryuk closed the connection or replied with something other than an acknowledgement.
            TimeoutError: Ryuk did not reply within the acknowledgement timeout.
        """
        message = urlencode({"label": f"{COMPOSE_PROJECT_LABEL}={project_name}"}).encode() + b"\n"
        with self._lock:
            if self._connection is None:
                self._connection = self._connect()
            try:
                self._send_filter(connection=self._connection, message=message)
            except OSError:
                # A late acknowledgement on this connection would be read as the reply to the next filter.
                self._connection.close()
                self._connection = None
                raise

    def _send_filter(self, connection: socket.socket, message: bytes) -> None:
        connection.settimeout(self._acknowledgement_timeout)
        connection.sendall(message)
        reply = b""
        while len(reply) < len(RYUK_ACKNOWLEDGEMENT):
            chunk = connection.recv(len(RYUK_ACKNOWLEDGEMENT) - len(reply))
            if not chunk:
                raise ConnectionError("Ryuk closed the connection before acknowledging the cleanup filter")
            reply += chunk
        if reply != RYUK_ACKNOWLEDGEMENT:
            raise ConnectionError(f"Ryuk replied {reply!r} instead of acknowledging the cleanup filter")
