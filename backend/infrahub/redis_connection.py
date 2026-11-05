from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, urlencode

from prefect_redis.connection import redis_from_url
from redis.asyncio.retry import Retry
from redis.asyncio.sentinel import SentinelConnectionPool
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

if TYPE_CHECKING:
    import redis.asyncio as redis
    from redis.asyncio.connection import AbstractConnection, ConnectionPool

    from infrahub.config import CacheSettings

# redis-py's own client retry policy, which it applies only to a pool it builds itself and never to one built from a URL.
REDIS_COMMAND_RETRIES: int = 10
REDIS_RETRY_BACKOFF_BASE: float = 0.01
REDIS_RETRY_BACKOFF_CAP: float = 1.0

# The interval prefect-redis uses, so that an idle connection to a server that went away is found before a command uses it.
REDIS_HEALTH_CHECK_INTERVAL: int = 20

TLS_URL_SCHEMES = frozenset({"rediss", "rediss+sentinel"})

# The three forms in which a TLS connection accepts the CA certificates to verify against.
CA_URL_OPTIONS = frozenset({"ssl_ca_certs", "ssl_ca_path", "ssl_ca_data"})


def _is_tls_url(url: str) -> bool:
    """Whether the URL's scheme selects TLS.

    The scheme is cut off by hand rather than read with ``urlsplit``, which raises
    ``ValueError: Invalid IPv6 URL`` on a Sentinel URL whose bracketed member is not the first one,
    as in ``rediss+sentinel://sentinel-a:26379,[2001:db8::1]:26379/mymaster``.
    """
    scheme, separator, _ = url.partition("://")
    return bool(separator) and scheme.lower() in TLS_URL_SCHEMES


def _has_at_sign_after_host(url: str) -> bool:
    """Whether an ``@`` follows the host, as it does when a ``/``, ``?`` or ``#`` in the credentials is not encoded."""
    _, _, remainder = url.partition("://")
    authority_end = min((index for index in map(remainder.find, "/?#") if index != -1), default=len(remainder))
    return "@" in remainder[authority_end:]


def add_default_ca_bundle(url: str, ca_file: str | None) -> str:
    """Return ``url`` verifying against ``ca_file`` when it selects TLS and names no CA certificates itself.

    On a ``rediss+sentinel://`` URL the ``ssl_*`` options also reach the Sentinel daemon connections,
    so the one CA covers the whole topology.
    """
    base, _, query = url.partition("?")
    if ca_file is None or not _is_tls_url(url) or CA_URL_OPTIONS & parse_qs(query, keep_blank_values=True).keys():
        return url
    option = urlencode({"ssl_ca_certs": ca_file})
    return f"{base}?{query}&{option}" if query else f"{base}?{option}"


def build_cache_connection_string(cache: CacheSettings) -> str:
    """Return the Redis connection URL that the cache settings describe.

    A configured ``cache.url`` is returned as written, verifying against ``cache.tls_ca_file`` unless it
    names CA certificates itself; otherwise the scalar settings are assembled into a single-node URL.
    """
    url = cache.url
    if url is not None:
        return add_default_ca_bundle(url.get_secret_value(), cache.tls_ca_file)

    scheme = "rediss" if cache.tls_enabled else "redis"

    userinfo = ""
    if cache.username and cache.password:
        userinfo = f"{quote(cache.username, safe='')}:{quote(cache.password, safe='')}@"
    elif cache.password:
        userinfo = f":{quote(cache.password, safe='')}@"

    query: dict[str, str] = {}
    if cache.tls_enabled:
        if cache.tls_insecure:
            query["ssl_cert_reqs"] = "none"
            query["ssl_check_hostname"] = "False"
        if cache.tls_ca_file:
            query["ssl_ca_certs"] = cache.tls_ca_file

    qs = f"?{urlencode(query)}" if query else ""
    # A bare IPv6 address is a valid host setting but has to be bracketed to be read back from a URL.
    host = f"[{cache.address}]" if ":" in cache.address and not cache.address.startswith("[") else cache.address
    return f"{scheme}://{userinfo}{host}:{cache.service_port}/{cache.database}{qs}"


def _connection_defaults() -> dict[str, Any]:
    """Connection options that the URL's own query options override."""
    backoff = ExponentialWithJitterBackoff(base=REDIS_RETRY_BACKOFF_BASE, cap=REDIS_RETRY_BACKOFF_CAP)
    return {
        # Redis may already have run a command whose reply timed out, so only connection errors, which a failover raises,
        # are retried.
        "retry": Retry(backoff, retries=REDIS_COMMAND_RETRIES, supported_errors=(RedisConnectionError,)),
        "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
    }


def _redis_from_url(url: str, max_connections: int | None = None) -> redis.Redis:
    options = _connection_defaults()
    if max_connections is not None:
        # Each flow waiting on a lock polls it with its own command, and redis-py 8 otherwise caps a pool at 100.
        options["max_connections"] = max_connections
    client = redis_from_url(url, asynchronous=True, **options)
    pool = client.connection_pool
    if isinstance(pool, SentinelConnectionPool):
        # prefect-redis 0.3.0 passes only the socket_* and ssl_* options to the Sentinel daemon clients, so their pools
        # would keep redis-py 8's 100 connections and no health check, the only record of a connection's last reply.
        for daemon in pool.sentinel_manager.sentinels:
            daemon.connection_pool.max_connections = pool.max_connections
            daemon.connection_pool.connection_kwargs["health_check_interval"] = pool.connection_kwargs.get(
                "health_check_interval", 0
            )
    return client


def pool_size_from_url(url: str, max_connections: int) -> int:
    """Return the size of the pool built from ``url`` for a ``max_connections`` setting.

    A ``max_connections`` query option of the URL takes precedence, read the way redis-py reads it.
    """
    return _redis_from_url(url, max_connections=max_connections).connection_pool.max_connections


def validate_redis_url(url: str) -> None:
    """Check that a client and its connections can be built from ``url``, without opening a connection.

    Raises:
        ValueError: When the URL is malformed or names an option the connection does not accept. The
            message never echoes the credentials embedded in the URL.

    """
    if _has_at_sign_after_host(url):
        # The parsers would read part of the credentials as a host, port, path or option, and echo it.
        raise ValueError(
            "Redis URL has an '@' after its host. Percent-encode the characters /, ?, #, @, : and % in its "
            "username and password, for example / as %2F, and an @ in a query value as %40."
        )
    try:
        # Building a connection object, not only the client, is what rejects an unknown query option.
        _redis_from_url(url).connection_pool.make_connection()
    except (TypeError, RedisError) as exc:
        raise ValueError(f"Redis URL is not valid: {exc}") from exc


def build_redis_connection(settings: CacheSettings) -> redis.Redis:
    """Build a client that selects single-node or Sentinel mode from the URL the settings describe.

    Close it with ``prefect_redis.connection.aclose_redis_client``, which also releases a Sentinel
    client's daemon connections.
    """
    return _redis_from_url(build_cache_connection_string(settings), max_connections=settings.max_connections)


async def close_idle_connections(client: redis.Redis, idle_seconds: float) -> int:
    """Close the free connections of ``client`` whose last reply is older than ``idle_seconds``.

    A closed connection stays in its pool and reconnects when a command takes it again. On a Sentinel client,
    the pools to the Sentinel daemons are cleaned too.

    Returns:
        The number of connections closed.

    """
    pool = client.connection_pool
    pools: list[ConnectionPool] = [pool]
    if isinstance(pool, SentinelConnectionPool):
        pools.extend(daemon.connection_pool for daemon in pool.sentinel_manager.sentinels)

    closed = 0
    for each_pool in pools:
        closed += await _close_idle_pool_connections(pool=each_pool, idle_seconds=idle_seconds)
    return closed


async def _close_idle_pool_connections(pool: ConnectionPool, idle_seconds: float) -> int:
    now = asyncio.get_running_loop().time()
    closed = 0
    # redis-py 8.1.0 hands out and takes back free connections under this lock, so no command takes one while it closes.
    async with pool._lock:
        for connection in pool._available_connections:
            if connection.is_connected and _idle_for(connection, now=now) >= idle_seconds:
                await connection.disconnect()
                closed += 1
    return closed


def _idle_for(connection: AbstractConnection, now: float) -> float:
    """Return the seconds since the connection's last reply, or 0 when it is not known."""
    # redis-py 8.1.0 records a reply only as the time of the next health check, and only while the check is enabled.
    if not connection.health_check_interval or connection.next_health_check < 0:
        return 0
    return now - (connection.next_health_check - connection.health_check_interval)
