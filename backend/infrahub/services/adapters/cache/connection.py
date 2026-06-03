from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from urllib.parse import SplitResult, parse_qs, unquote, urlencode, urlsplit, urlunsplit

from infrahub.exceptions import RedisUrlError

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.config import CacheSettings

logger: logging.Logger = logging.getLogger(__name__)

# Connection URL schemes. A `+sentinel` suffix selects Sentinel discovery; a `rediss`
# prefix turns on TLS for the data nodes. The grammar follows the `redis-sentinel-url`
# convention: redis+sentinel://[user:pass@]host[:port][,host2[:port2],...]/service_name[/db][?params]
SCHEME_SENTINEL = frozenset({"redis+sentinel", "rediss+sentinel"})
SCHEME_TLS = frozenset({"rediss", "rediss+sentinel"})
SCHEME_ALL = frozenset({"redis", "rediss"}) | SCHEME_SENTINEL

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_SECRET_QUERY_KEYS = frozenset({"password", "sentinel_password"})
_REDACTED = "***"
# Redis data nodes listen on 6379, Sentinel daemons on 26379; a member without an explicit
# port defaults to whichever applies to the scheme.
_DEFAULT_DATA_PORT = 6379
_DEFAULT_SENTINEL_PORT = 26379

# Query keys the parser consumes itself (TLS knobs and Sentinel-daemon settings). Every other
# query parameter is treated as a standard redis-py connection option and funneled through
# redis-py's own URL parser so it gets identical typing and validation.
_RESERVED_QUERY_KEYS = frozenset(
    {
        "tls_insecure",
        "tls_ca_file",
        "sentinel_username",
        "sentinel_password",
        "sentinel_ssl",
        "sentinel_tls_insecure",
        "sentinel_tls_ca_file",
    }
)

# Tight TCP keepalive for the data-node connections so a silently-dead master (a network
# partition or frozen host that never sends FIN/RST) is noticed in roughly
# TCP_KEEPIDLE + TCP_KEEPCNT * TCP_KEEPINTVL seconds instead of the OS default (~2h on Linux),
# letting the Sentinel pool re-resolve the promoted master promptly. The probes only fire on an
# otherwise-idle socket and a healthy peer answers them. These match redis-py 8.0's own defaults;
# pinning them keeps the behaviour identical on the redis 6.x line, where connections default to
# no keepalive.
_KEEPALIVE_TIMERS: tuple[tuple[str, int], ...] = (
    ("TCP_KEEPIDLE", 30),
    ("TCP_KEEPINTVL", 5),
    ("TCP_KEEPCNT", 3),
)
SENTINEL_SOCKET_KEEPALIVE_OPTIONS: dict[int, int] = {
    int(getattr(socket, name)): value for name, value in _KEEPALIVE_TIMERS if hasattr(socket, name)
}

# Bound the connect and per-command read so a connection to a master that has just failed over fails
# fast and the pool re-resolves the promoted master, instead of hanging on the dead address until the
# OS gives up (tens of seconds of SYN retries). The same bounds on the Sentinel daemon connections let
# master discovery skip a dead daemon promptly. Cache and lock operations are short round-trips with no
# long blocking reads, so a finite read timeout is safe here.
SENTINEL_SOCKET_CONNECT_TIMEOUT: float = 5.0
SENTINEL_SOCKET_TIMEOUT: float = 5.0
# Retry a command across reconnections so a failover in progress is followed transparently rather than
# surfaced to the caller: each retry closes the stale connection, which re-resolves the master.
SENTINEL_COMMAND_RETRIES: int = 5


@dataclass(frozen=True)
class RedisConnectionConfig:
    """Validated description of a Redis connection parsed from a URL.

    ``connection_kwargs`` and ``sentinel_kwargs`` hold redis-py-native keys (``username``,
    ``password``, ``ssl``, ``ssl_cert_reqs``, ``ssl_check_hostname``, ``ssl_ca_certs``, plus any
    standard connection options from the URL query string) so a caller can splat them directly. In
    Sentinel mode ``connection_kwargs`` applies to the data-node (master) connections and
    ``sentinel_kwargs`` to the Sentinel daemons.
    """

    db: int
    is_sentinel: bool
    host: str | None = None
    port: int | None = None
    service_name: str | None = None
    sentinels: tuple[tuple[str, int], ...] = ()
    connection_kwargs: dict[str, object] = field(default_factory=dict)
    sentinel_kwargs: dict[str, object] = field(default_factory=dict)


def is_sentinel_url(url: str) -> bool:
    """Whether ``url`` selects Sentinel discovery (redis+sentinel:// or rediss+sentinel://).

    A plain string-prefix check so the scheme is known before handing the URL to ``urlsplit``,
    which rejects the multi-host netloc a Sentinel URL carries.
    """
    return url.partition("://")[0].lower() in SCHEME_SENTINEL


def _split_url(url: str) -> SplitResult:
    """``urlsplit`` a connection URL while preserving a multi-host Sentinel netloc.

    A Sentinel URL lists several daemons in its netloc, e.g. ``s1:26379,[::1]:26379``. ``urlsplit``
    raises ``ValueError("Invalid IPv6 URL")`` for any netloc where data precedes a ``[`` bracket, so
    for Sentinel URLs the netloc is carved off by hand, the remainder is parsed with a placeholder
    host, and the real netloc is restored on the result.
    """
    if not is_sentinel_url(url):
        return urlsplit(url)
    scheme, _, remainder = url.partition("://")
    end = len(remainder)
    for terminator in "/?#":
        index = remainder.find(terminator)
        if index != -1:
            end = min(end, index)
    netloc, tail = remainder[:end], remainder[end:]
    parsed = urlsplit(f"{scheme}://netloc-placeholder{tail}")
    return parsed._replace(netloc=netloc)


def redact_redis_url(url: str) -> str:
    """Return ``url`` with the userinfo password and sensitive query values masked."""
    try:
        parts = _split_url(url)
    except ValueError:
        return _REDACTED

    netloc = parts.netloc
    if "@" in netloc:
        userinfo, hostpart = netloc.rsplit("@", 1)
        if ":" in userinfo:
            user, _ = userinfo.split(":", 1)
            userinfo = f"{user}:{_REDACTED}"
        netloc = f"{userinfo}@{hostpart}"

    query = ""
    if parts.query:
        pairs = []
        for key, values in parse_qs(parts.query, keep_blank_values=True).items():
            value = _REDACTED if key in _SECRET_QUERY_KEYS else (values[0] if values else "")
            pairs.append(f"{key}={value}")
        query = "&".join(pairs)

    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def _to_bool(value: str, *, url: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise RedisUrlError(f"Invalid boolean value {value!r} in cache URL: {redact_redis_url(url)}")


def _parse_db(segment: str, *, url: str) -> int:
    try:
        db = int(segment)
    except ValueError as exc:
        raise RedisUrlError(f"Invalid database index {segment!r} in cache URL: {redact_redis_url(url)}") from exc
    if not 0 <= db <= 15:
        raise RedisUrlError(f"Database index {db} out of range (0-15) in cache URL: {redact_redis_url(url)}")
    return db


def _split_members(hostpart: str, *, url: str, default_port: int) -> list[tuple[str, int]]:
    """Split a comma-separated ``host:port,host2:port2`` netloc into members.

    ``urlsplit`` only exposes the segment before the first comma through ``.hostname``/``.port``, so
    the multi-host netloc is split by hand and each member parsed on its own with ``urlsplit``, which
    handles default ports, bracketed IPv6, and port validation per member.

    Raises:
        RedisUrlError: When a member is missing a host or has a non-numeric port, or no member is found.

    """
    members: list[tuple[str, int]] = []
    for raw_entry in hostpart.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        member = urlsplit(f"//{entry}")
        if not member.hostname:
            raise RedisUrlError(f"Missing host in cache URL: {redact_redis_url(url)}")
        try:
            port = member.port
        except ValueError as exc:
            raise RedisUrlError(f"Invalid port {entry!r} in cache URL: {redact_redis_url(url)}") from exc
        members.append((member.hostname, port if port is not None else default_port))
    if not members:
        raise RedisUrlError(f"No host found in cache URL: {redact_redis_url(url)}")
    return members


def _build_ssl_kwargs(*, enabled: bool, query: dict[str, list[str]], url: str, prefix: str = "") -> dict[str, object]:
    if not enabled:
        return {"ssl": False}
    insecure = _to_bool(query.get(f"{prefix}tls_insecure", ["false"])[0], url=url)
    return {
        "ssl": True,
        "ssl_cert_reqs": "none" if insecure else "optional",
        "ssl_check_hostname": not insecure,
        "ssl_ca_certs": query.get(f"{prefix}tls_ca_file", [None])[0],
    }


def _funnel_pool_options(query: dict[str, list[str]], *, url: str) -> dict[str, object]:
    """Type the leftover query parameters as standard redis-py connection options.

    Everything the parser does not consume itself (``max_connections``, ``socket_timeout``,
    ``health_check_interval``, ...) is funneled through redis-py's own ``parse_url`` on a synthetic
    standalone URL, so it gets exactly the same type conversion and validation as a ``redis://`` URL
    rather than being silently dropped.

    Raises:
        RedisUrlError: When a connection option has a value redis-py cannot parse.

    """
    extra = {key: values for key, values in query.items() if key not in _RESERVED_QUERY_KEYS}
    if not extra:
        return {}

    # Imported lazily so parsing a URL (e.g. the startup settings validator) needs redis only when a
    # connection option is actually present.
    from redis.asyncio.connection import parse_url

    encoded = urlencode([(key, value) for key, values in extra.items() for value in values])
    try:
        # parse_url returns a fresh TypedDict each call; view it as a plain mutable dict so the
        # governed keys can be popped.
        funneled = cast("dict[str, object]", parse_url(f"redis:///?{encoded}"))
    except ValueError as exc:
        raise RedisUrlError(f"Invalid connection option in cache URL: {redact_redis_url(url)}") from exc
    # The database comes from the path and credentials from the userinfo, so a stray query value for
    # one of those must not become a second source of truth.
    for governed in ("db", "username", "password", "host", "port"):
        funneled.pop(governed, None)
    return funneled


def _build_sentinel_kwargs(query: dict[str, list[str]], *, tls_default: bool, url: str) -> dict[str, object]:
    """Build the redis-py kwargs for the connections to the Sentinel daemons themselves.

    The ``sentinel_username``/``sentinel_password`` query parameters authenticate to the daemons
    independently of the data-node credentials, and ``sentinel_ssl`` / ``sentinel_tls_*`` override the
    scheme's TLS default for the daemon connections only.
    """
    sentinel_kwargs: dict[str, object] = {}
    sentinel_username = query.get("sentinel_username", [None])[0]
    sentinel_password = query.get("sentinel_password", [None])[0]
    if sentinel_username:
        sentinel_kwargs["username"] = sentinel_username
    if sentinel_password:
        sentinel_kwargs["password"] = sentinel_password
    sentinel_ssl_raw = query.get("sentinel_ssl", [None])[0]
    sentinel_tls = tls_default if sentinel_ssl_raw is None else _to_bool(sentinel_ssl_raw, url=url)
    sentinel_kwargs.update(_build_ssl_kwargs(enabled=sentinel_tls, query=query, url=url, prefix="sentinel_"))
    return sentinel_kwargs


def parse_redis_url(url: str) -> RedisConnectionConfig:
    """Parse a Redis connection URL into a validated ``RedisConnectionConfig``.

    Raises:
        RedisUrlError: With secrets redacted, for any unsupported scheme, malformed member list,
            missing Sentinel service name, out-of-range database index, or malformed connection option.

    """
    parts = _split_url(url)
    scheme = parts.scheme.lower()
    if scheme not in SCHEME_ALL:
        raise RedisUrlError(f"Unsupported scheme {parts.scheme!r} in cache URL: {redact_redis_url(url)}")

    is_sentinel = scheme in SCHEME_SENTINEL
    tls_default = scheme in SCHEME_TLS

    netloc = parts.netloc
    userinfo = ""
    hostpart = netloc
    if "@" in netloc:
        userinfo, hostpart = netloc.rsplit("@", 1)

    username: str | None = None
    password: str | None = None
    if userinfo:
        if ":" in userinfo:
            raw_user, raw_password = userinfo.split(":", 1)
            username = unquote(raw_user) or None
            password = unquote(raw_password)
        else:
            username = unquote(userinfo) or None

    default_port = _DEFAULT_SENTINEL_PORT if is_sentinel else _DEFAULT_DATA_PORT
    members = _split_members(hostpart, url=url, default_port=default_port)
    path_segments = [segment for segment in parts.path.split("/") if segment]
    query = parse_qs(parts.query, keep_blank_values=True)

    connection_kwargs: dict[str, object] = {}
    if username is not None:
        connection_kwargs["username"] = username
    if password is not None:
        connection_kwargs["password"] = password
    connection_kwargs.update(_build_ssl_kwargs(enabled=tls_default, query=query, url=url))
    connection_kwargs.update(_funnel_pool_options(query, url=url))

    if not is_sentinel:
        if len(members) > 1:
            raise RedisUrlError(f"Multiple hosts require a +sentinel scheme: {redact_redis_url(url)}")
        db = _parse_db(path_segments[0], url=url) if path_segments else 0
        host, port = members[0]
        return RedisConnectionConfig(
            db=db, is_sentinel=False, host=host, port=port, connection_kwargs=connection_kwargs
        )

    if not path_segments:
        raise RedisUrlError(f"A Sentinel cache URL requires a service name: {redact_redis_url(url)}")
    service_name = path_segments[0]
    db = _parse_db(path_segments[1], url=url) if len(path_segments) > 1 else 0

    return RedisConnectionConfig(
        db=db,
        is_sentinel=True,
        service_name=service_name,
        sentinels=tuple(members),
        connection_kwargs=connection_kwargs,
        sentinel_kwargs=_build_sentinel_kwargs(query, tls_default=tls_default, url=url),
    )


_owned_sentinel_pool_class: type | None = None


def _owned_sentinel_connection_pool() -> type:
    """A ``SentinelConnectionPool`` subclass that also closes its Sentinel manager's daemon clients.

    redis-py keeps one Redis client per Sentinel daemon on the manager and never closes them itself,
    so disconnecting the pool alone would leak those connections. Built lazily and cached so importing
    this module does not pull in redis.
    """
    global _owned_sentinel_pool_class
    if _owned_sentinel_pool_class is not None:
        return _owned_sentinel_pool_class

    from redis.asyncio.sentinel import SentinelConnectionPool

    class OwnedSentinelConnectionPool(SentinelConnectionPool):
        async def disconnect(self, inuse_connections: bool = True) -> None:
            await super().disconnect(inuse_connections=inuse_connections)
            for sentinel_client in getattr(self.sentinel_manager, "sentinels", ()):
                try:
                    await sentinel_client.aclose()
                except Exception:
                    # Best-effort cleanup on teardown; a daemon client failing to close must not block it.
                    logger.debug("Failed to close a Sentinel daemon client", exc_info=True)

    _owned_sentinel_pool_class = OwnedSentinelConnectionPool
    return _owned_sentinel_pool_class


def build_redis_connection(settings: CacheSettings) -> redis.Redis:
    """Build the Redis connection shared by the cache adapter and the lock registry.

    When ``settings.url`` is set it is authoritative and selects single-node or Sentinel mode from its
    scheme. Otherwise the scalar connection settings are used (single-node).
    """
    import redis.asyncio as redis
    from redis import UsernamePasswordCredentialProvider
    from redis.backoff import ExponentialBackoff
    from redis.retry import Retry

    if settings.url is None:
        credential_provider: UsernamePasswordCredentialProvider | None = None
        if settings.username and settings.password:
            credential_provider = UsernamePasswordCredentialProvider(
                username=settings.username, password=settings.password
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

    parsed = parse_redis_url(settings.url.get_secret_value())
    if parsed.is_sentinel:
        # parse_redis_url guarantees a service name in Sentinel mode.
        assert parsed.service_name is not None

        # HA defaults come first so any explicit query option in the URL overrides them. The retry
        # makes a failover transparent: a command retries across reconnections, and each reconnection
        # re-resolves the current master through Sentinel.
        retry = Retry(ExponentialBackoff(cap=1.0, base=0.2), retries=SENTINEL_COMMAND_RETRIES)
        data_node_kwargs = {
            "socket_keepalive": True,
            "socket_keepalive_options": SENTINEL_SOCKET_KEEPALIVE_OPTIONS,
            "socket_connect_timeout": SENTINEL_SOCKET_CONNECT_TIMEOUT,
            "socket_timeout": SENTINEL_SOCKET_TIMEOUT,
            "retry": retry,
            **parsed.connection_kwargs,
        }
        daemon_kwargs = {
            "socket_connect_timeout": SENTINEL_SOCKET_CONNECT_TIMEOUT,
            "socket_timeout": SENTINEL_SOCKET_TIMEOUT,
            **parsed.sentinel_kwargs,
        }

        sentinel = redis.Sentinel(list(parsed.sentinels), sentinel_kwargs=daemon_kwargs)
        pool = _owned_sentinel_connection_pool()(
            parsed.service_name, sentinel, is_master=True, db=parsed.db, **data_node_kwargs
        )
        master = redis.Redis(connection_pool=pool, retry_on_error=[redis.ConnectionError, redis.TimeoutError])
        # The pool is externally owned, so the client would not disconnect it on aclose(); flip the flag
        # so closing the cache connection tears the pool (and its Sentinel daemon clients) down.
        master.auto_close_connection_pool = True
        return master
    return redis.Redis(host=parsed.host, port=parsed.port, db=parsed.db, **parsed.connection_kwargs)
