from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, urlencode

from prefect_redis.connection import redis_from_url
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.config import BrokerSettings, CacheSettings

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


def _build_single_node_url(
    *,
    address: str,
    port: int,
    database: int,
    username: str,
    password: str,
    tls_enabled: bool,
    tls_insecure: bool,
    tls_ca_file: str | None,
) -> str:
    """Assemble scalar connection settings into a single-node Redis URL."""
    scheme = "rediss" if tls_enabled else "redis"

    userinfo = ""
    if username and password:
        userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    elif password:
        userinfo = f":{quote(password, safe='')}@"

    query: dict[str, str] = {}
    if tls_enabled:
        if tls_insecure:
            query["ssl_cert_reqs"] = "none"
            query["ssl_check_hostname"] = "False"
        if tls_ca_file:
            query["ssl_ca_certs"] = tls_ca_file

    qs = f"?{urlencode(query)}" if query else ""
    # A bare IPv6 address is a valid host setting but has to be bracketed to be read back from a URL.
    host = f"[{address}]" if ":" in address and not address.startswith("[") else address
    return f"{scheme}://{userinfo}{host}:{port}/{database}{qs}"


def build_cache_connection_string(cache: CacheSettings) -> str:
    """Return the Redis connection URL that the cache settings describe.

    A configured ``cache.url`` is returned as written, verifying against ``cache.tls_ca_file`` unless it
    names CA certificates itself; otherwise the scalar settings are assembled into a single-node URL.
    """
    url = cache.url
    if url is not None:
        return add_default_ca_bundle(url.get_secret_value(), cache.tls_ca_file)

    return _build_single_node_url(
        address=cache.address,
        port=cache.service_port,
        database=cache.database,
        username=cache.username,
        password=cache.password,
        tls_enabled=cache.tls_enabled,
        tls_insecure=cache.tls_insecure,
        tls_ca_file=cache.tls_ca_file,
    )


def build_broker_connection_string(broker: BrokerSettings) -> str:
    """Return the Redis connection URL that the broker settings describe for the redis message bus driver.

    A configured ``broker.url`` is returned as written, verifying against ``broker.tls_ca_file`` unless it
    names CA certificates itself; otherwise the scalar settings are assembled into a single-node URL on
    database 0, leaving out a username or password still at its RabbitMQ default.
    """
    url = broker.url
    if url is not None:
        return add_default_ca_bundle(url.get_secret_value(), broker.tls_ca_file)

    return _build_single_node_url(
        address=broker.address,
        port=broker.service_port,
        database=0,
        username=broker.redis_username,
        password=broker.redis_password,
        tls_enabled=broker.tls_enabled,
        tls_insecure=broker.tls_insecure,
        tls_ca_file=broker.tls_ca_file,
    )


def _connection_defaults() -> dict[str, Any]:
    """Connection options that the URL's own query options override."""
    backoff = ExponentialWithJitterBackoff(base=REDIS_RETRY_BACKOFF_BASE, cap=REDIS_RETRY_BACKOFF_CAP)
    return {
        # Redis may already have run a command whose reply timed out, so only connection errors, which a failover raises,
        # are retried.
        "retry": Retry(backoff, retries=REDIS_COMMAND_RETRIES, supported_errors=(RedisConnectionError,)),
        "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
    }


def _redis_from_url(url: str) -> redis.Redis:
    return redis_from_url(url, asynchronous=True, **_connection_defaults())


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
    return _redis_from_url(build_cache_connection_string(settings))


def build_broker_redis_connection(settings: BrokerSettings) -> redis.Redis:
    """Build the redis message bus client, selecting single-node or Sentinel mode from the broker URL.

    Close it with ``prefect_redis.connection.aclose_redis_client``, which also releases a Sentinel
    client's daemon connections.
    """
    return _redis_from_url(build_broker_connection_string(settings))
