from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, urlencode

from prefect_redis.connection import redis_from_url
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import RedisError

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.config import CacheSettings

# redis-py's own client retry policy, which it applies only to a pool it builds itself and never to one built from a URL.
REDIS_COMMAND_RETRIES: int = 10
REDIS_RETRY_BACKOFF_BASE: float = 0.01
REDIS_RETRY_BACKOFF_CAP: float = 1.0

# The interval prefect-redis uses, so that an idle connection to a server that went away is found before a command uses it.
REDIS_HEALTH_CHECK_INTERVAL: int = 20

TLS_URL_SCHEMES = frozenset({"rediss", "rediss+sentinel"})


def _is_tls_url(url: str) -> bool:
    """Whether the URL's scheme selects TLS.

    The scheme is cut off by hand rather than read with ``urlsplit``, which raises
    ``ValueError: Invalid IPv6 URL`` on a Sentinel URL whose bracketed member is not the first one,
    as in ``rediss+sentinel://sentinel-a:26379,[2001:db8::1]:26379/mymaster``.
    """
    scheme, separator, _ = url.partition("://")
    return bool(separator) and scheme.lower() in TLS_URL_SCHEMES


def add_default_ca_bundle(url: str, ca_file: str | None) -> str:
    """Return ``url`` verifying against ``ca_file`` when it selects TLS and names no CA bundle itself.

    On a ``rediss+sentinel://`` URL the ``ssl_*`` options also reach the Sentinel daemon connections,
    so the one CA covers the whole topology.
    """
    base, _, query = url.partition("?")
    if ca_file is None or not _is_tls_url(url) or "ssl_ca_certs" in parse_qs(query, keep_blank_values=True):
        return url
    option = urlencode({"ssl_ca_certs": ca_file})
    return f"{base}?{query}&{option}" if query else f"{base}?{option}"


def build_cache_connection_string(cache: CacheSettings) -> str:
    """Return the Redis connection URL that the cache settings describe.

    A configured ``cache.url`` is returned as written, verifying against ``cache.tls_ca_file`` unless it
    names a CA bundle itself; otherwise the scalar settings are assembled into a single-node URL.

    Raises:
        ValueError: When ``INFRAHUB_CACHE_USERNAME`` is set without ``INFRAHUB_CACHE_PASSWORD``.

    """
    url = cache.active_url
    if url is not None:
        return add_default_ca_bundle(url.get_secret_value(), cache.tls_ca_file)

    if cache.username and not cache.password:
        raise ValueError("INFRAHUB_CACHE_USERNAME is set but INFRAHUB_CACHE_PASSWORD is not. Both are required.")

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
        "retry": Retry(backoff, retries=REDIS_COMMAND_RETRIES),
        "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
    }


def _redis_from_url(url: str) -> redis.Redis:
    return redis_from_url(url, asynchronous=True, **_connection_defaults())


def validate_redis_url(url: str) -> None:
    """Check that a client and its connections can be built from ``url``, without opening a connection.

    Raises:
        ValueError: When the URL is malformed or names an option the connection does not accept. The
            message does not echo the URL, so credentials embedded in it are not leaked.

    """
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
    return _redis_from_url(build_cache_connection_string(settings))
