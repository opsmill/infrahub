from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.config import CacheSettings

# The URL grammar, the parsing and the Sentinel wiring all live in prefect_redis.connection, which
# Infrahub already depends on for the Prefect result-storage block. Sharing that one implementation
# keeps the cache, the lock registry and the result-storage block on a single URL dialect:
#
#     redis://[user:pass@]host[:port][/db][?options]
#     rediss://...                                    (TLS)
#     redis+sentinel://[user:pass@]host[:port][,host2[:port2],...]/service_name[/db][?options]
#     rediss+sentinel://...                           (TLS for the data nodes and the daemons)
#
# Sentinel members default to port 26379. The sentinel_username and sentinel_password options
# authenticate to the Sentinel daemons; every other option is a standard redis-py connection option
# (socket_timeout, max_connections, health_check_interval, ssl_cert_reqs, ssl_check_hostname,
# ssl_ca_certs, ...) applied to the data-node connections, and on a TLS scheme the ssl_* options are
# shared with the daemon connections so one private CA covers the whole topology.

# Tight TCP keepalive so a silently-dead server (a network partition or frozen host that never sends
# FIN/RST) is noticed in roughly TCP_KEEPIDLE + TCP_KEEPCNT * TCP_KEEPINTVL seconds instead of the OS
# default (~2h on Linux), letting a Sentinel pool re-resolve the promoted master promptly. The probes
# only fire on an otherwise-idle socket and a healthy peer answers them. These match redis-py 8.0's
# own defaults, which prefect-redis relies on; Infrahub pins redis-py 6.0, where connections default
# to no keepalive, so they are pinned explicitly here.
_KEEPALIVE_TIMERS: tuple[tuple[str, int], ...] = (
    ("TCP_KEEPIDLE", 30),
    ("TCP_KEEPINTVL", 5),
    ("TCP_KEEPCNT", 3),
)
REDIS_SOCKET_KEEPALIVE_OPTIONS: dict[int, int] = {
    int(getattr(socket, name)): value for name, value in _KEEPALIVE_TIMERS if hasattr(socket, name)
}

# Bound the connect and per-command read so a connection to a server that has just failed over fails
# fast and the pool reconnects, instead of hanging on the dead address until the OS gives up (tens of
# seconds of SYN retries). On a Sentinel pool reconnecting re-resolves the promoted master, and the
# same bounds on the daemon connections let discovery skip a dead daemon promptly. Cache and lock
# operations are short round-trips with no long blocking reads, so a finite read timeout is safe.
REDIS_SOCKET_CONNECT_TIMEOUT: float = 5.0
REDIS_SOCKET_TIMEOUT: float = 5.0
# Retry a command across reconnections so a failover in progress is followed transparently rather
# than surfaced to the caller.
REDIS_COMMAND_RETRIES: int = 5


def _url_connection_defaults() -> dict[str, Any]:
    """Connection options applied to every URL-configured connection.

    These are defaults: ``redis_from_url`` lets the URL's own query options override them, so a
    deployment can still pin its own ``?socket_timeout=`` or ``?health_check_interval=``.
    """
    # Imported lazily so this module stays importable (and cheap) without pulling in redis; the
    # settings validator only needs the URL grammar, not a client.
    from redis.backoff import ExponentialBackoff  # noqa: PLC0415
    from redis.retry import Retry  # noqa: PLC0415

    return {
        "socket_keepalive": True,
        "socket_keepalive_options": REDIS_SOCKET_KEEPALIVE_OPTIONS,
        "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
        "socket_timeout": REDIS_SOCKET_TIMEOUT,
        "retry": Retry(ExponentialBackoff(cap=1.0, base=0.2), retries=REDIS_COMMAND_RETRIES),
    }


def validate_redis_url(url: str) -> None:
    """Check that ``url`` is a connection URL ``build_redis_connection`` can build a client from.

    Building a client is lazy and opens no connection, so this validates the grammar without
    touching the network.

    Raises:
        ValueError: When the URL is malformed. prefect-redis guarantees the message does not echo
            the URL, so credentials embedded in it are not leaked into a validation error.

    """
    # Imported lazily to keep the settings module, which calls this, free of prefect and redis.
    from prefect_redis.connection import close_redis_client, redis_from_url  # noqa: PLC0415

    # Closing releases the per-daemon Sentinel clients a Sentinel URL builds.
    close_redis_client(redis_from_url(url))


def build_redis_connection(settings: CacheSettings) -> redis.Redis:
    """Build the Redis connection shared by the cache adapter and the lock registry.

    When ``settings.url`` is set it is authoritative and selects single-node or Sentinel mode from
    its scheme. Otherwise the scalar connection settings are used (single-node).

    Close the result with :func:`aclose_redis_connection`.
    """
    # Imported lazily to avoid pulling redis and prefect into every importer of this module.
    import redis.asyncio as redis  # noqa: PLC0415

    if settings.url is None:
        from redis import UsernamePasswordCredentialProvider  # noqa: PLC0415

        credential_provider: UsernamePasswordCredentialProvider | None = None
        if settings.password:
            # Username is optional: a password-only configuration authenticates as the Redis
            # default user (the common requirepass case), which a username-and-password guard drops.
            credential_provider = UsernamePasswordCredentialProvider(
                username=settings.username or None, password=settings.password
            )
        return redis.Redis(
            host=settings.address,
            port=settings.service_port,
            db=settings.database,
            credential_provider=credential_provider,
            ssl=settings.tls_enabled,
            ssl_cert_reqs="optional" if not settings.tls_insecure else "none",
            ssl_check_hostname=not settings.tls_insecure,
            ssl_ca_certs=settings.tls_ca_file,
        )

    from prefect_redis.connection import redis_from_url  # noqa: PLC0415

    return redis_from_url(settings.url.get_secret_value(), asynchronous=True, **_url_connection_defaults())


async def aclose_redis_connection(connection: redis.Redis) -> None:
    """Close a connection built by :func:`build_redis_connection` and release its pool.

    A plain ``aclose()`` is not enough for a Sentinel-backed connection: redis-py keeps one client
    per Sentinel daemon on the pool's ``sentinel_manager`` and never closes those itself, so they
    would be left to the garbage collector. ``aclose_redis_client`` closes the client (which owns
    and disconnects its pool) and then those daemon clients.
    """
    # Imported lazily for the same reason as the builder.
    from prefect_redis.connection import aclose_redis_client  # noqa: PLC0415

    await aclose_redis_client(connection)
