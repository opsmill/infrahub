from __future__ import annotations

import asyncio
import re
import shlex
import socket
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import redis
import redis.asyncio as async_redis
from pydantic import SecretStr
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub.components import ComponentType
from infrahub.config import BrokerDriver, BrokerSettings
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.services.adapters.message_bus.redis import RedisMessageBus
from infrahub.workers.dependencies import build_message_bus
from tests.helpers.constants import INFRAHUB_USE_TEST_CONTAINERS, REDIS_IMAGE

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Generator

    from fast_depends import Provider

pytestmark = pytest.mark.skipif(
    not INFRAHUB_USE_TEST_CONTAINERS, reason="Starts its own Redis Sentinel topology with testcontainers"
)

LOOPBACK = "127.0.0.1"
SERVICE_NAME = "mymaster"
SENTINEL_QUORUM = 1
SENTINEL_DOWN_AFTER_MS = 1_000
SENTINEL_FAILOVER_TIMEOUT_MS = 10_000
TOPOLOGY_READY_TIMEOUT_SECONDS = 30.0
FAILOVER_TIMEOUT_SECONDS = 30.0
REPLICATION_WAIT_MS = 5_000
RPC_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.2


@dataclass
class SentinelTopology:
    """A Redis master, one replica and one Sentinel, all reachable on the loopback address."""

    master_port: int
    replica_port: int
    sentinel_port: int
    master: DockerContainer

    @property
    def url(self) -> str:
        return f"redis+sentinel://{LOOPBACK}:{self.sentinel_port}/{SERVICE_NAME}"


def _free_ports(count: int) -> list[int]:
    sockets = [socket.socket() for _ in range(count)]
    try:
        for sock in sockets:
            sock.bind((LOOPBACK, 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def _start_redis(script: str, ready_log: str) -> DockerContainer:
    # Host networking makes the master address that Sentinel reports reachable from the test process.
    container = (
        DockerContainer(image=REDIS_IMAGE).with_command(f"sh -c {shlex.quote(script)}").with_kwargs(network_mode="host")
    )
    container.start()
    wait_for_logs(
        container, re.escape(ready_log), timeout=TOPOLOGY_READY_TIMEOUT_SECONDS, interval=POLL_INTERVAL_SECONDS
    )
    return container


def _wait_until(condition: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Condition not met within {timeout}s")
        time.sleep(POLL_INTERVAL_SECONDS)


def _replica_is_monitored(sentinel: redis.Redis, replica_port: int) -> bool:
    try:
        replicas = sentinel.sentinel_slaves(SERVICE_NAME)
    except redis.ConnectionError:
        return False
    return any(
        int(replica["port"]) == replica_port and replica["master-link-status"] == "ok"
        for replica in replicas
        if "s_down" not in replica["flags"] and "disconnected" not in replica["flags"]
    )


@pytest.fixture
def sentinel_topology() -> Generator[SentinelTopology, None, None]:
    master_port, replica_port, sentinel_port = _free_ports(3)
    sentinel_config = "\\n".join(
        [
            f"port {sentinel_port}",
            f"sentinel monitor {SERVICE_NAME} {LOOPBACK} {master_port} {SENTINEL_QUORUM}",
            f"sentinel down-after-milliseconds {SERVICE_NAME} {SENTINEL_DOWN_AFTER_MS}",
            f"sentinel failover-timeout {SERVICE_NAME} {SENTINEL_FAILOVER_TIMEOUT_MS}",
        ]
    )

    containers: list[DockerContainer] = []
    try:
        master = _start_redis(
            f"exec redis-server --port {master_port} --save '' --appendonly no",
            ready_log="Ready to accept connections",
        )
        containers.append(master)
        replica = _start_redis(
            f"exec redis-server --port {replica_port} --replicaof {LOOPBACK} {master_port} --save '' --appendonly no",
            ready_log="MASTER <-> REPLICA sync: Finished with success",
        )
        containers.append(replica)
        # Sentinel rewrites its configuration file, so it needs a writable one rather than command-line options.
        sentinel_node = _start_redis(
            f"printf '{sentinel_config}\\n' > /tmp/sentinel.conf && exec redis-server /tmp/sentinel.conf --sentinel",
            ready_log=f"+monitor master {SERVICE_NAME}",
        )
        containers.append(sentinel_node)
        with redis.Redis(host=LOOPBACK, port=sentinel_port, decode_responses=True) as sentinel:
            _wait_until(lambda: _replica_is_monitored(sentinel, replica_port), timeout=TOPOLOGY_READY_TIMEOUT_SECONDS)
        yield SentinelTopology(
            master_port=master_port, replica_port=replica_port, sentinel_port=sentinel_port, master=master
        )
    finally:
        for container in reversed(containers):
            container.stop()


async def _new_bus(settings: BrokerSettings, component_type: ComponentType, callback_stream: str) -> RedisMessageBus:
    bus = RedisMessageBus(component_type=component_type, settings=settings)
    # Both buses run in one process, so each gets the callback stream a separate worker process would have.
    bus.callback_stream = callback_stream
    await bus._initialize()
    return bus


@dataclass
class SentinelBuses:
    api_server: RedisMessageBus
    git_agent: RedisMessageBus


@pytest.fixture
async def sentinel_buses(
    sentinel_topology: SentinelTopology, dependency_provider: Provider
) -> AsyncGenerator[SentinelBuses, None]:
    namespace = f"sentinel-{uuid4().hex[:8]}"
    settings = BrokerSettings(driver=BrokerDriver.Redis, url=SecretStr(sentinel_topology.url), namespace=namespace)
    api_server = await _new_bus(settings, ComponentType.API_SERVER, callback_stream=f"{namespace}:callback:api")
    git_agent = await _new_bus(settings, ComponentType.GIT_AGENT, callback_stream=f"{namespace}:callback:git")
    try:
        # The echo handler replies through the bus of the worker that runs it.
        with dependency_provider.scope(build_message_bus, lambda: git_agent):
            yield SentinelBuses(api_server=api_server, git_agent=git_agent)
    finally:
        await git_agent.shutdown()
        await api_server.shutdown()


async def _echo(bus: RedisMessageBus, text: str) -> str:
    response = await bus.rpc(
        message=messages.SendEchoRequest(message=text),
        response_class=SendEchoRequestResponse,
        timeout=RPC_TIMEOUT_SECONDS,
    )
    return response.data.response


async def _master_port(topology: SentinelTopology) -> int:
    async with async_redis.Redis(host=LOOPBACK, port=topology.sentinel_port, decode_responses=True) as sentinel:
        address = await sentinel.sentinel_get_master_addr_by_name(SERVICE_NAME)
    if not isinstance(address, tuple):
        raise TypeError(f"Sentinel returned no address for the master {SERVICE_NAME}: {address!r}")
    _, port = address
    return int(port)


async def _role(port: int) -> str:
    async with async_redis.Redis(host=LOOPBACK, port=port, decode_responses=True) as node:
        role, *_ = await node.execute_command("ROLE")
    return role


async def _wait_for_replication(topology: SentinelTopology) -> None:
    """Wait until the replica holds every write the master acknowledged, so the promoted master has the streams."""
    async with async_redis.Redis(host=LOOPBACK, port=topology.master_port) as master:
        await master.execute_command("WAIT", 1, REPLICATION_WAIT_MS)


async def _wait_for_failover(condition: Callable[[], Awaitable[bool]]) -> None:
    deadline = time.monotonic() + FAILOVER_TIMEOUT_SECONDS
    while not await condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Sentinel did not complete the failover within {FAILOVER_TIMEOUT_SECONDS}s")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _request_failover(topology: SentinelTopology) -> None:
    """Ask Sentinel to promote the replica while the master stays up.

    Returns once Sentinel has also demoted the old master: until then the old master still accepts the
    writes of the clients connected to it, so a client only has to follow the failover from that point.
    """
    await _wait_for_replication(topology)
    async with async_redis.Redis(host=LOOPBACK, port=topology.sentinel_port) as sentinel:
        await sentinel.execute_command("SENTINEL", "FAILOVER", SERVICE_NAME)

    async def old_master_demoted() -> bool:
        return await _master_port(topology) == topology.replica_port and await _role(topology.master_port) == "slave"

    await _wait_for_failover(old_master_demoted)


async def _crash_master(topology: SentinelTopology) -> None:
    """Kill the master, so that Sentinel finds it down and promotes the replica."""
    await _wait_for_replication(topology)
    await asyncio.to_thread(topology.master.get_wrapped_container().kill)

    async def replica_promoted() -> bool:
        return await _master_port(topology) == topology.replica_port

    await _wait_for_failover(replica_promoted)


@dataclass
class FailoverCase:
    name: str
    fail_over: Callable[[SentinelTopology], Awaitable[None]]


FAILOVER_CASES = [
    FailoverCase(name="requested_failover", fail_over=_request_failover),
    FailoverCase(name="master_crash", fail_over=_crash_master),
]


async def test_rpc_reaches_a_worker_through_sentinel(
    sentinel_topology: SentinelTopology, sentinel_buses: SentinelBuses
) -> None:
    """The bus finds the master through Sentinel, and a worker answers an RPC sent by the API server."""
    assert await sentinel_buses.api_server.connection.connection_pool.get_master_address() == (
        LOOPBACK,
        sentinel_topology.master_port,
    )

    assert await _echo(sentinel_buses.api_server, "through sentinel") == "Reply to: through sentinel"


@pytest.mark.parametrize("case", FAILOVER_CASES, ids=lambda case: case.name)
async def test_rpc_reaches_a_worker_after_a_sentinel_failover(
    case: FailoverCase, sentinel_topology: SentinelTopology, sentinel_buses: SentinelBuses
) -> None:
    """After Sentinel promotes the replica, both buses follow the new master and RPCs are answered again."""
    assert await _echo(sentinel_buses.api_server, "before failover") == "Reply to: before failover"

    await case.fail_over(sentinel_topology)

    assert await _echo(sentinel_buses.api_server, "after failover") == "Reply to: after failover"
