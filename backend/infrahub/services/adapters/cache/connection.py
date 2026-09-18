from __future__ import annotations

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

# Nothing tunes the socket here: redis-py 8 already connects with TCP keepalive (30s idle, 5s
# interval, 3 probes) and bounds the connect and per-command read at 5s, on the data-node and the
# Sentinel daemon connections alike. Those are the bounds a Sentinel pool needs to notice a
# silently-dead master and re-resolve the promoted one, and the scalar path below gets them from the
# same defaults, so pinning them again would only duplicate the pin on redis-py in pyproject.toml.
# The command retry policy is the one thing that has to be passed: redis-py applies its client-level
# default only when it builds the pool itself, which is the scalar path below, while Redis.from_url
# and Sentinel.master_for take a pool carrying just what the URL spelled out, leaving a
# URL-configured connection with no retry at all. prefect-redis leaves that gap to the caller, so the
# client default is rebuilt here and both paths follow a failover the same way: the command is
# retried across reconnections until the pool resolves the promoted master, instead of the
# ConnectionError reaching the cache or the lock. The values below are redis-py's own defaults and
# test_url_connection_retries_like_the_client_default holds them to that.
REDIS_COMMAND_RETRIES: int = 10
REDIS_RETRY_BACKOFF_BASE: float = 0.01
REDIS_RETRY_BACKOFF_CAP: float = 1.0

# PING a connection that has been idle longer than this before a command goes out, and re-establish
# it when the PING fails. A pooled connection whose server has gone unreachable would otherwise sit
# unnoticed until a caller trips over it. A demoted master that is still reachable answers the PING,
# so that case is caught elsewhere: redis-py turns the READONLY reply into a ConnectionError on a
# Sentinel-managed connection and the retry above re-resolves the promoted master. redis-py runs no
# such check by default (0); prefect-redis runs one every 20s, so the cache and the lock connections
# keep to the same interval on both paths.
REDIS_HEALTH_CHECK_INTERVAL: int = 20

# The schemes that select TLS; on the others an ssl_* option has nothing to configure.
TLS_URL_SCHEMES = frozenset({"rediss", "rediss+sentinel"})


def _is_tls_url(url: str) -> bool:
    """Whether the URL's scheme selects TLS.

    The scheme is cut off by hand rather than read with ``urlsplit``, which raises
    ``ValueError: Invalid IPv6 URL`` on a Sentinel URL whose bracketed member is not the first one,
    as in ``rediss+sentinel://sentinel-a:26379,[2001:db8::1]:26379/mymaster``.
    """
    scheme, separator, _ = url.partition("://")
    return bool(separator) and scheme.lower() in TLS_URL_SCHEMES


def _url_connection_defaults() -> dict[str, Any]:
    """Connection options applied to every URL-configured connection.

    These are defaults: ``redis_from_url`` lets the URL's own query options override them, so a
    deployment can still pin its own ``?socket_timeout=`` or ``?health_check_interval=``.
    """
    # Imported lazily so this module stays importable (and cheap) without pulling in redis; the
    # settings validator only needs the URL grammar, not a client.
    from redis.backoff import ExponentialWithJitterBackoff  # noqa: PLC0415
    from redis.retry import Retry  # noqa: PLC0415

    backoff = ExponentialWithJitterBackoff(base=REDIS_RETRY_BACKOFF_BASE, cap=REDIS_RETRY_BACKOFF_CAP)
    return {
        "retry": Retry(backoff, retries=REDIS_COMMAND_RETRIES),
        "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
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
    its scheme. Otherwise the scalar connection settings are used (single-node). Either way the
    connection verifies against ``settings.tls_ca_file`` when TLS is on, so a private CA configured
    once through the global ``INFRAHUB_TLS_CA_BUNDLE`` covers the cache as well.

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
            health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
            ssl=settings.tls_enabled,
            ssl_cert_reqs="optional" if not settings.tls_insecure else "none",
            ssl_check_hostname=not settings.tls_insecure,
            ssl_ca_certs=settings.tls_ca_file,
        )

    from prefect_redis.connection import redis_from_url  # noqa: PLC0415

    url = settings.url.get_secret_value()
    options = _url_connection_defaults()
    if settings.tls_ca_file is not None and _is_tls_url(url):
        # The CA the deployment configured, either as INFRAHUB_CACHE_TLS_CA_FILE or through the
        # global INFRAHUB_TLS_CA_BUNDLE that fills it, is the default for a TLS URL; an explicit
        # ?ssl_ca_certs= still wins. On a rediss+sentinel:// URL prefect-redis shares the ssl_*
        # options with the daemon connections, so the one CA covers the whole topology.
        options["ssl_ca_certs"] = settings.tls_ca_file
    return redis_from_url(url, asynchronous=True, **options)


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
