"""Reproduce the "idle connection killer" failure mode with the Neo4j Python driver.

Topology:
    this script --(bolt)--> IdleKillerProxy (127.0.0.1:7688) --(tcp)--> Neo4j (127.0.0.1:7687)

The proxy forwards traffic transparently, but once a connection has been idle for
IDLE_KILL_SECONDS it "blackholes" it: it silently stops forwarding and never sends
FIN/RST back to the client. This is exactly what stateful firewalls, NAT gateways
and load balancers do when their idle timeout expires and they evict the flow from
their state table: the client still believes the TCP connection is established.

What you should observe:

    Phase 1  pool warm-up          -> 2 healthy pooled bolt connections
    Phase 2  idle period           -> the proxy silently drops both flows
    Phase 3  3 concurrent queries  -> 2 queries grab the stale connections and HANG
                                      (in production until TCP retransmission gives
                                      up, often 15+ minutes), the 3rd query cannot
                                      get a connection from the exhausted pool and
                                      raises ConnectionAcquisitionTimeoutError
    Phase 4  mitigation            -> same idle period, but with
                                      max_connection_lifetime set BELOW the killer's
                                      idle timeout the driver discards the aged
                                      connection and dials a fresh one: the query
                                      succeeds with no failed request

Infrahub exposes the corresponding driver options as database settings:

  * INFRAHUB_DB_MAX_CONNECTION_LIFETIME -- the reliable fix for silent drops: set it
    below the idle timeout of every middlebox between Infrahub and the database.
  * INFRAHUB_DB_LIVENESS_CHECK_TIMEOUT -- pings idle pooled connections before reuse.
    It replaces connections that died LOUDLY (e.g. a database restart) with no failed
    request, but it does NOT prevent the silent case: the ping itself goes down the
    dead socket and consumes the acquisition deadline, failing every waiting request
    once with ConnectionAcquisitionTimeoutError before the pool recovers.

Prerequisites: a local Neo4j, e.g.
    docker run --rm -p 7687:7687 -e NEO4J_AUTH=neo4j/secretpassword neo4j:2026.05.0-community

Run:
    NEO4J_PASSWORD=secretpassword uv run python utilities/neo4j_idle_killer_repro.py
"""

from __future__ import annotations

import contextlib
import os
import socket
import threading
import time

from neo4j import Driver, GraphDatabase

NEO4J_HOST = os.environ.get("NEO4J_HOST", "127.0.0.1")
NEO4J_PORT = int(os.environ.get("NEO4J_PORT", "7687"))
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "secretpassword")

PROXY_HOST = "127.0.0.1"
PROXY_PORT = int(os.environ.get("PROXY_PORT", "7688"))

IDLE_KILL_SECONDS = 8
"""Idle timeout of the simulated firewall/NAT/load balancer."""
IDLE_SLEEP_SECONDS = 12
"""How long the app stays idle (> IDLE_KILL_SECONDS)."""
POOL_SIZE = 2
"""Tiny pool so exhaustion is easy to trigger."""
ACQUISITION_TIMEOUT = 5
"""Driver connection_acquisition_timeout (driver default: 60)."""

PROXY_URI = f"bolt://{PROXY_HOST}:{PROXY_PORT}"
AUTH = (NEO4J_USER, NEO4J_PASSWORD)


def log(msg: str) -> None:
    """Print a timestamped, unbuffered progress line."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class _Flow:
    __slots__ = ("blackholed", "client", "id", "last_activity", "server")

    def __init__(self, fid: int, client: socket.socket, server: socket.socket) -> None:
        self.id = fid
        self.client = client
        self.server = server
        self.last_activity = time.monotonic()
        self.blackholed = False


class IdleKillerProxy(threading.Thread):
    """TCP proxy that silently stops forwarding flows idle longer than idle_kill_seconds.

    "Silently" is the key part: the client socket is left open (no FIN/RST), mimicking
    a firewall/NAT/load balancer that evicted the flow from its state table.
    """

    def __init__(
        self,
        listen_host: str = PROXY_HOST,
        listen_port: int = PROXY_PORT,
        upstream: tuple[str, int] = (NEO4J_HOST, NEO4J_PORT),
        idle_kill_seconds: float = IDLE_KILL_SECONDS,
    ) -> None:
        """Start listening and spawn the reaper that blackholes idle flows.

        Args:
            listen_host: Address the proxy listens on.
            listen_port: Port the proxy listens on.
            upstream: (host, port) of the real Neo4j server.
            idle_kill_seconds: Idle time after which a flow is silently dropped.

        """
        super().__init__(daemon=True)
        self.upstream = upstream
        self.idle_kill_seconds = idle_kill_seconds
        self.listener = socket.create_server((listen_host, listen_port))
        self.flows: list[_Flow] = []
        self.lock = threading.Lock()
        self._next_id = 0
        self._stopped = threading.Event()
        threading.Thread(target=self._reaper, daemon=True).start()

    def run(self) -> None:
        """Accept client connections and pump them to/from the upstream server."""
        while not self._stopped.is_set():
            try:
                client, _ = self.listener.accept()
            except OSError:
                break  # listener closed
            try:
                server = socket.create_connection(address=self.upstream, timeout=5)
            except OSError as exc:
                log(f"proxy: cannot reach upstream {self.upstream}: {exc}")
                client.close()
                continue
            # create_connection's timeout also applies to every later recv(): without
            # this reset the server->client pump raises TimeoutError after 5s idle and
            # propagates a *visible* close to the client, which defeats the whole point
            # of a silent blackhole.
            server.settimeout(None)
            with self.lock:
                self._next_id += 1
                flow = _Flow(fid=self._next_id, client=client, server=server)
                self.flows.append(flow)
            log(f"proxy: new flow #{flow.id} (client -> Neo4j)")
            threading.Thread(target=self._pump, args=(flow, client, server), daemon=True).start()
            threading.Thread(target=self._pump, args=(flow, server, client), daemon=True).start()

    def _pump(self, flow: _Flow, src: socket.socket, dst: socket.socket) -> None:
        while True:
            try:
                data = src.recv(65536)
            except OSError:
                break
            if not data:
                break
            if flow.blackholed:
                # Drain and discard: the client's send() keeps succeeding, but bytes
                # go nowhere and no reply will ever come back.
                continue
            flow.last_activity = time.monotonic()
            try:
                dst.sendall(data)
            except OSError:
                break
        if not flow.blackholed:
            # Normal proxy behaviour: propagate the close to the other side.
            for sock in (flow.client, flow.server):
                with contextlib.suppress(OSError):
                    sock.shutdown(socket.SHUT_RDWR)

    def _reaper(self) -> None:
        while not self._stopped.is_set():
            time.sleep(0.5)
            now = time.monotonic()
            with self.lock:
                for flow in self.flows:
                    if not flow.blackholed and now - flow.last_activity > self.idle_kill_seconds:
                        flow.blackholed = True
                        # Close only the SERVER side (Neo4j tidies up), but tell the
                        # client NOTHING -- no FIN, no RST.
                        with contextlib.suppress(OSError):
                            flow.server.shutdown(socket.SHUT_RDWR)
                            flow.server.close()
                        log(f"proxy: flow #{flow.id} idle > {self.idle_kill_seconds}s -> SILENTLY dropped")

    def release_hung_clients(self) -> None:
        """Kill blackholed client sockets so hung driver calls error out instead of blocking forever."""
        with self.lock:
            for flow in self.flows:
                if flow.blackholed:
                    with contextlib.suppress(OSError):
                        flow.client.shutdown(socket.SHUT_RDWR)
                        flow.client.close()

    def stop(self) -> None:
        """Stop accepting new flows and shut the listener down."""
        self._stopped.set()
        with contextlib.suppress(OSError):
            self.listener.close()


def warm_pool(driver: Driver, n: int) -> None:
    """Force the pool to hold n connections by keeping n transactions open simultaneously.

    Args:
        driver: Driver whose pool to warm.
        n: Number of pooled connections to establish.

    """
    sessions = [driver.session() for _ in range(n)]
    transactions = [session.begin_transaction() for session in sessions]
    for tx in transactions:
        tx.run("RETURN 1").consume()
    for tx in transactions:
        tx.commit()
    for session in sessions:
        session.close()


def timed_query(driver: Driver, label: str, results: dict[str, str]) -> None:
    """Run one RETURN 1 query and record its outcome and duration under label.

    Args:
        driver: Driver to query through.
        label: Key to record the outcome under.
        results: Shared dict the outcome is written into.

    """
    start = time.monotonic()
    try:
        with driver.session() as session:
            value = session.run("RETURN 1 AS x").single(strict=True)["x"]
        results[label] = f"OK (returned {value}) in {time.monotonic() - start:.1f}s"
    except Exception as exc:
        results[label] = f"{type(exc).__name__} after {time.monotonic() - start:.1f}s: {exc}"


def main() -> None:
    """Run the four reproduction phases against a local Neo4j."""
    proxy = IdleKillerProxy()
    proxy.start()
    log(f"proxy listening on {PROXY_URI}, forwarding to {NEO4J_HOST}:{NEO4J_PORT}, idle kill = {IDLE_KILL_SECONDS}s")

    driver = GraphDatabase.driver(
        PROXY_URI,
        auth=AUTH,
        max_connection_pool_size=POOL_SIZE,
        connection_acquisition_timeout=ACQUISITION_TIMEOUT,
        # Defaults left on purpose: max_connection_lifetime=3600, no liveness check
        # -> the driver happily reuses a silently-dead connection.
    )
    try:
        driver.verify_connectivity()
    except OSError as exc:
        log(f"cannot reach Neo4j through the proxy: {type(exc).__name__}: {exc}")
        log(
            "is Neo4j running? e.g. docker run --rm -p 7687:7687 "
            "-e NEO4J_AUTH=neo4j/secretpassword neo4j:2026.05.0-community"
        )
        proxy.stop()
        return

    log(f"--- Phase 1: warming a pool of {POOL_SIZE} connections ---")
    warm_pool(driver=driver, n=POOL_SIZE)
    log(f"pool now holds {POOL_SIZE} idle connections")

    log(f"--- Phase 2: app goes idle for {IDLE_SLEEP_SECONDS}s (> {IDLE_KILL_SECONDS}s idle timeout) ---")
    time.sleep(IDLE_SLEEP_SECONDS)

    log(f"--- Phase 3: {POOL_SIZE + 1} concurrent queries against {POOL_SIZE} stale connections ---")
    results: dict[str, str] = {}
    threads = [
        threading.Thread(target=timed_query, args=(driver, f"query-{i}", results), daemon=True)
        for i in range(1, POOL_SIZE + 2)
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + ACQUISITION_TIMEOUT + 3
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))

    for i in range(1, POOL_SIZE + 2):
        outcome = results.get(f"query-{i}", "STILL HANGING on a silently-dropped connection")
        log(f"query-{i}: {outcome}")

    log("releasing the hung client sockets (in production these hang until TCP gives up -- often 15+ minutes)")
    proxy.release_hung_clients()
    for thread in threads:
        thread.join(timeout=5)
    for i in range(1, POOL_SIZE + 2):
        log(f"query-{i} final: {results.get(f'query-{i}', 'still hanging')}")
    driver.close()

    log(f"--- Phase 4: mitigation: max_connection_lifetime={IDLE_KILL_SECONDS - 3}s < idle timeout ---")
    mitigated_driver = GraphDatabase.driver(
        PROXY_URI,
        auth=AUTH,
        max_connection_pool_size=POOL_SIZE,
        connection_acquisition_timeout=ACQUISITION_TIMEOUT,
        max_connection_lifetime=IDLE_KILL_SECONDS - 3,
    )
    warm_pool(driver=mitigated_driver, n=1)
    log(f"sleeping {IDLE_SLEEP_SECONDS}s again ...")
    time.sleep(IDLE_SLEEP_SECONDS)
    mitigated_results: dict[str, str] = {}
    timed_query(driver=mitigated_driver, label="mitigated-query", results=mitigated_results)
    log(
        f"mitigated-query: {mitigated_results['mitigated-query']} "
        "(driver discarded the aged connection and dialed a fresh one -- watch for the new proxy flow above)"
    )
    mitigated_driver.close()
    proxy.stop()
    log("done")


if __name__ == "__main__":
    main()
