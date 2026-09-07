from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from pydantic_core import ValidationError
from redis.asyncio.connection import Connection, SSLConnection
from redis.asyncio.sentinel import (
    SentinelConnectionPool,
    SentinelManagedConnection,
    SentinelManagedSSLConnection,
)

from infrahub.config import CacheSettings
from infrahub.services.adapters.cache.connection import (
    REDIS_COMMAND_RETRIES,
    REDIS_SOCKET_CONNECT_TIMEOUT,
    REDIS_SOCKET_KEEPALIVE_OPTIONS,
    REDIS_SOCKET_TIMEOUT,
    aclose_redis_connection,
    build_redis_connection,
    validate_redis_url,
)


def _build(url: str) -> Any:
    return build_redis_connection(CacheSettings(url=SecretStr(url)))


@dataclass
class UrlCase:
    name: str
    url: str
    connection_class: type
    connection_kwargs: dict[str, Any] = field(default_factory=dict)


URL_CASES = [
    UrlCase(
        name="single_node_minimal",
        url="redis://localhost:6379/0",
        connection_class=Connection,
        connection_kwargs={"host": "localhost", "port": 6379},
    ),
    UrlCase(
        name="single_node_default_port_and_db",
        url="redis://cache",
        connection_class=Connection,
        connection_kwargs={"host": "cache"},
    ),
    UrlCase(
        name="single_node_tls_with_auth_and_encoded_password",
        url="rediss://user:pa%40ss@cache:6380/2",
        connection_class=SSLConnection,
        connection_kwargs={"host": "cache", "port": 6380, "db": 2, "username": "user", "password": "pa@ss"},
    ),
    UrlCase(
        name="single_node_tls_native_ssl_options",
        url="rediss://cache:6379?ssl_cert_reqs=none&ssl_check_hostname=false&ssl_ca_certs=/etc/ca.pem",
        connection_class=SSLConnection,
        connection_kwargs={"ssl_cert_reqs": "none", "ssl_check_hostname": False, "ssl_ca_certs": "/etc/ca.pem"},
    ),
    UrlCase(
        name="single_node_pool_options_funneled",
        url="redis://cache:6379/0?max_connections=50&health_check_interval=15",
        connection_class=Connection,
        connection_kwargs={"health_check_interval": 15},
    ),
]


@pytest.mark.parametrize("case", URL_CASES, ids=lambda case: case.name)
def test_build_redis_connection_from_url(case: UrlCase) -> None:
    pool = _build(case.url).connection_pool

    assert pool.connection_class is case.connection_class
    for key, expected in case.connection_kwargs.items():
        assert pool.connection_kwargs.get(key) == expected, f"kwarg {key!r}"


def test_omitted_port_and_db_fall_back_to_the_redis_py_defaults() -> None:
    """redis-py leaves an omitted port/db out of connection_kwargs; the connection still defaults."""
    pool = _build("redis://cache").connection_pool
    connection = pool.connection_class(**pool.connection_kwargs)

    assert (connection.host, connection.port, connection.db) == ("cache", 6379, 0)


def test_url_connection_applies_ha_defaults() -> None:
    """Every URL-configured connection gets the keepalive, timeout and retry hardening."""
    kwargs = _build("redis://cache:6379/0").connection_pool.connection_kwargs

    assert kwargs["socket_keepalive"] is True
    assert kwargs["socket_keepalive_options"] == REDIS_SOCKET_KEEPALIVE_OPTIONS
    assert kwargs["socket_connect_timeout"] == REDIS_SOCKET_CONNECT_TIMEOUT
    assert kwargs["socket_timeout"] == REDIS_SOCKET_TIMEOUT
    assert kwargs["retry"].get_retries() == REDIS_COMMAND_RETRIES


def test_url_query_option_overrides_ha_default() -> None:
    """The HA settings are defaults: an explicit query option in the URL wins."""
    kwargs = _build("redis://cache:6379/0?socket_timeout=7").connection_pool.connection_kwargs

    assert kwargs["socket_timeout"] == 7.0
    assert kwargs["socket_connect_timeout"] == REDIS_SOCKET_CONNECT_TIMEOUT


def test_max_connections_reaches_the_pool() -> None:
    # max_connections is consumed by the pool itself rather than kept in connection_kwargs.
    assert _build("redis://cache:6379/0?max_connections=50").connection_pool.max_connections == 50


@dataclass
class SentinelCase:
    name: str
    url: str
    service_name: str
    sentinels: list[tuple[str, int]]
    connection_class: type
    db: int = 0
    connection_kwargs: dict[str, Any] = field(default_factory=dict)
    sentinel_kwargs: dict[str, Any] = field(default_factory=dict)


SENTINEL_CASES = [
    SentinelCase(
        name="multi_member_with_data_and_sentinel_auth",
        url="redis+sentinel://app:secret@s1:26379,s2:26379,s3:26379/mymaster/1"
        "?sentinel_username=su&sentinel_password=sp",
        service_name="mymaster",
        sentinels=[("s1", 26379), ("s2", 26379), ("s3", 26379)],
        connection_class=SentinelManagedConnection,
        db=1,
        connection_kwargs={"username": "app", "password": "secret"},
        sentinel_kwargs={"username": "su", "password": "sp"},
    ),
    SentinelCase(
        name="member_default_port",
        url="redis+sentinel://s1,s2/svc",
        service_name="svc",
        sentinels=[("s1", 26379), ("s2", 26379)],
        connection_class=SentinelManagedConnection,
    ),
    SentinelCase(
        name="ipv6_members",
        url="redis+sentinel://[2001:db8::1]:26379,[2001:db8::2]:26380/svc",
        service_name="svc",
        sentinels=[("2001:db8::1", 26379), ("2001:db8::2", 26380)],
        connection_class=SentinelManagedConnection,
    ),
    SentinelCase(
        name="tls_data_nodes_follow_scheme",
        url="rediss+sentinel://s1:26379/svc",
        service_name="svc",
        sentinels=[("s1", 26379)],
        connection_class=SentinelManagedSSLConnection,
        sentinel_kwargs={"ssl": True},
    ),
    SentinelCase(
        name="tls_ssl_options_shared_with_daemons",
        url="rediss+sentinel://s1:26379/svc?ssl_cert_reqs=none&ssl_check_hostname=false",
        service_name="svc",
        sentinels=[("s1", 26379)],
        connection_class=SentinelManagedSSLConnection,
        connection_kwargs={"ssl_cert_reqs": "none", "ssl_check_hostname": False},
        sentinel_kwargs={"ssl": True, "ssl_cert_reqs": "none", "ssl_check_hostname": False},
    ),
    SentinelCase(
        name="pool_options_funneled_to_data_nodes",
        url="redis+sentinel://s1:26379/svc?health_check_interval=15&sentinel_username=su",
        service_name="svc",
        sentinels=[("s1", 26379)],
        connection_class=SentinelManagedConnection,
        connection_kwargs={"health_check_interval": 15},
        sentinel_kwargs={"username": "su"},
    ),
]


@pytest.mark.parametrize("case", SENTINEL_CASES, ids=lambda case: case.name)
def test_build_redis_connection_from_sentinel_url(case: SentinelCase) -> None:
    pool = _build(case.url).connection_pool

    assert isinstance(pool, SentinelConnectionPool)
    assert pool.service_name == case.service_name
    assert pool.connection_class is case.connection_class
    assert pool.connection_kwargs.get("db", 0) == case.db

    manager = pool.sentinel_manager
    members = [
        (daemon.connection_pool.connection_kwargs["host"], daemon.connection_pool.connection_kwargs["port"])
        for daemon in manager.sentinels
    ]
    assert members == case.sentinels

    for key, expected in case.connection_kwargs.items():
        assert pool.connection_kwargs.get(key) == expected, f"data-node kwarg {key!r}"
    for key, expected in case.sentinel_kwargs.items():
        assert manager.sentinel_kwargs.get(key) == expected, f"sentinel kwarg {key!r}"


def test_sentinel_daemons_inherit_socket_options() -> None:
    """The daemon connections get the same connect/read bounds, so discovery skips a dead daemon."""
    manager = _build("redis+sentinel://s1:26379/svc?sentinel_password=sp").connection_pool.sentinel_manager

    assert manager.sentinel_kwargs["socket_connect_timeout"] == REDIS_SOCKET_CONNECT_TIMEOUT
    assert manager.sentinel_kwargs["socket_timeout"] == REDIS_SOCKET_TIMEOUT


def test_sentinel_credentials_do_not_leak_to_the_daemons() -> None:
    """Data-node credentials must not be replayed to the daemons, which authenticate separately."""
    pool = _build("redis+sentinel://app:secret@s1:26379/svc?sentinel_username=su&sentinel_password=sp").connection_pool

    assert pool.connection_kwargs["username"] == "app"
    assert pool.connection_kwargs["password"] == "secret"
    assert pool.sentinel_manager.sentinel_kwargs["username"] == "su"
    assert pool.sentinel_manager.sentinel_kwargs["password"] == "sp"


@dataclass
class ScalarCase:
    name: str
    cache_kwargs: dict[str, Any]
    connection_class: type
    connection_kwargs: dict[str, Any] = field(default_factory=dict)
    credentials: tuple[str, ...] | None = None


SCALAR_CASES = [
    ScalarCase(
        name="plaintext",
        cache_kwargs={"address": "redis.internal", "port": 6400, "database": 3},
        connection_class=Connection,
        connection_kwargs={"host": "redis.internal", "port": 6400, "db": 3},
    ),
    ScalarCase(
        name="tls",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True},
        connection_class=SSLConnection,
        connection_kwargs={"ssl_cert_reqs": "optional", "ssl_check_hostname": True},
    ),
    ScalarCase(
        name="tls_insecure",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True},
        connection_class=SSLConnection,
        connection_kwargs={"ssl_cert_reqs": "none", "ssl_check_hostname": False},
    ),
    ScalarCase(
        name="username_and_password",
        cache_kwargs={"address": "redis.internal", "username": "user", "password": "secret"},
        connection_class=Connection,
        credentials=("user", "secret"),
    ),
    ScalarCase(
        name="password_only_authenticates_as_default_user",
        cache_kwargs={"address": "redis.internal", "password": "secret"},
        connection_class=Connection,
        credentials=("secret",),
    ),
    ScalarCase(
        name="no_credentials",
        cache_kwargs={"address": "redis.internal"},
        connection_class=Connection,
        credentials=None,
    ),
]


@pytest.mark.parametrize("case", SCALAR_CASES, ids=lambda case: case.name)
def test_build_redis_connection_from_scalar_settings(case: ScalarCase) -> None:
    """Without a URL the scalar settings still build a single-node client directly."""
    pool = build_redis_connection(CacheSettings(**case.cache_kwargs)).connection_pool

    assert pool.connection_class is case.connection_class
    for key, expected in case.connection_kwargs.items():
        assert pool.connection_kwargs.get(key) == expected, f"kwarg {key!r}"

    provider = pool.connection_kwargs.get("credential_provider")
    if case.credentials is None:
        assert provider is None
    else:
        assert provider is not None
        assert provider.get_credentials() == case.credentials


VALID_URLS = [
    "redis://cache:6379/0",
    "rediss://user:pass@cache:6380/2",
    "redis+sentinel://s1:26379,s2:26379/mymaster",
    "rediss+sentinel://s1/mymaster/1?ssl_ca_certs=/etc/ca.pem&sentinel_password=sp",
]


@pytest.mark.parametrize("url", VALID_URLS)
def test_validate_redis_url_accepts(url: str) -> None:
    validate_redis_url(url)


@dataclass
class InvalidUrlCase:
    name: str
    url: str
    match: str


INVALID_URL_CASES = [
    InvalidUrlCase(name="unknown_scheme", url="http://cache:6379", match="must specify one of the following schemes"),
    InvalidUrlCase(name="sentinel_without_service", url="redis+sentinel://s1:26379", match="requires a service name"),
    InvalidUrlCase(name="invalid_port", url="redis://cache:notaport", match="Port could not be cast"),
    InvalidUrlCase(
        name="invalid_sentinel_member_port", url="redis+sentinel://s1:bad/svc", match="Invalid port for Sentinel member"
    ),
    InvalidUrlCase(name="invalid_pool_option", url="redis://cache:6379?socket_timeout=abc", match="Invalid value for"),
]


@pytest.mark.parametrize("case", INVALID_URL_CASES, ids=lambda case: case.name)
def test_validate_redis_url_rejects(case: InvalidUrlCase) -> None:
    with pytest.raises(ValueError, match=case.match):
        validate_redis_url(case.url)


NO_LEAK_URLS = [
    "redis+sentinel://u:topsecret@s1:26379",
    "redis://u:topsecret@cache:nope",
    "rediss://u:topsecret@cache:6379?socket_timeout=abc",
]


@pytest.mark.parametrize("url", NO_LEAK_URLS)
def test_validate_redis_url_errors_do_not_leak_secrets(url: str) -> None:
    # Deliberately unmatched: the guarantee is that *no* rejection message echoes the URL, whichever
    # layer (prefect-redis or redis-py) raises it, so pinning a message would defeat the test.
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        validate_redis_url(url)
    assert "topsecret" not in str(exc_info.value)


def test_settings_validation_error_does_not_leak_secrets() -> None:
    """The same guarantee has to hold through the settings layer, which is where a URL is loaded."""
    with pytest.raises(ValidationError) as exc_info:
        CacheSettings(url=SecretStr("redis+sentinel://u:topsecret@s1:26379"))
    assert "topsecret" not in str(exc_info.value)


async def test_aclose_releases_the_pool_and_the_sentinel_daemons() -> None:
    """Closing a Sentinel connection must reach both its pool and its Sentinel daemon clients.

    ``Sentinel.master_for()`` builds the client with ``Redis.from_pool()``, so the client owns its
    pool and disconnects it on close. The one client per Sentinel daemon that redis-py keeps on
    ``sentinel_manager`` is not covered by that, and is what the close helper adds.
    """
    connection = _build("redis+sentinel://s1:26379,s2:26379/mymaster")
    pool = connection.connection_pool
    pool.disconnect = AsyncMock()
    daemons = pool.sentinel_manager.sentinels
    for daemon in daemons:
        daemon.aclose = AsyncMock()

    await aclose_redis_connection(connection)

    pool.disconnect.assert_awaited()
    for daemon in daemons:
        daemon.aclose.assert_awaited()


async def test_aclose_single_node_connection() -> None:
    connection = _build("redis://cache:6379/0")
    connection.connection_pool.disconnect = AsyncMock()

    await aclose_redis_connection(connection)

    connection.connection_pool.disconnect.assert_awaited()
