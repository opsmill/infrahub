from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit

import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from redis.asyncio.connection import Connection, SSLConnection
from redis.asyncio.sentinel import (
    SentinelConnectionPool,
    SentinelManagedConnection,
    SentinelManagedSSLConnection,
)

from infrahub.config import CacheDriver, CacheSettings
from infrahub.redis_connection import (
    REDIS_HEALTH_CHECK_INTERVAL,
    build_cache_connection_string,
    build_redis_connection,
    validate_redis_url,
)

# The socket bounds a Sentinel pool relies on to drop a dead master, asserted against the values
# redis-py 8 defaults to rather than against its own constants, so a bump that loosens them fails
# here instead of silently stretching a failover.
REDIS_PY_SOCKET_TIMEOUTS = 5
REDIS_PY_KEEPALIVE_OPTIONS = {socket.TCP_KEEPIDLE: 30, socket.TCP_KEEPINTVL: 5, socket.TCP_KEEPCNT: 3}

# CA settings are validated at load, so the cases need a bundle that exists.
CA_BUNDLE = str(Path(__file__).parent / "test_data" / "ca-bundle.pem")
CA_BUNDLE_QUOTED = quote_plus(CA_BUNDLE, safe="")


def _build(url: str, **cache_kwargs: Any) -> Any:
    return build_redis_connection(CacheSettings(url=SecretStr(url), **cache_kwargs))


@dataclass
class ConnectionStringCase:
    name: str
    cache_kwargs: dict[str, Any]
    expected_url: str


CONNECTION_STRING_CASES = [
    ConnectionStringCase(
        name="plain_defaults",
        cache_kwargs={"address": "localhost"},
        expected_url="redis://localhost:6379/0",
    ),
    ConnectionStringCase(
        name="plain_custom_port_and_db",
        cache_kwargs={"address": "redis.internal", "port": 6400, "database": 7},
        expected_url="redis://redis.internal:6400/7",
    ),
    ConnectionStringCase(
        name="plain_user_and_password",
        cache_kwargs={"address": "redis.internal", "username": "user", "password": "secret"},
        expected_url="redis://user:secret@redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="plain_password_only",
        cache_kwargs={"address": "redis.internal", "password": "secret"},
        expected_url="redis://:secret@redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="plain_special_chars_escaped",
        cache_kwargs={"address": "redis.internal", "username": "us er@name", "password": "p@ss:wor/d?#&"},
        expected_url="redis://us%20er%40name:p%40ss%3Awor%2Fd%3F%23%26@redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="plain_bare_ipv6_address_bracketed",
        cache_kwargs={"address": "::1", "database": 2},
        expected_url="redis://[::1]:6379/2",
    ),
    ConnectionStringCase(
        name="plain_bracketed_ipv6_address_kept",
        cache_kwargs={"address": "[2001:db8::2]", "password": "secret"},
        expected_url="redis://:secret@[2001:db8::2]:6379/0",
    ),
    ConnectionStringCase(
        name="tls_defaults",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True},
        expected_url="rediss://redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="tls_with_credentials",
        cache_kwargs={"address": "redis.internal", "username": "user", "password": "secret", "tls_enabled": True},
        expected_url="rediss://user:secret@redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="tls_insecure",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True},
        expected_url="rediss://redis.internal:6379/0?ssl_cert_reqs=none&ssl_check_hostname=False",
    ),
    ConnectionStringCase(
        name="tls_ca_file",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_ca_file": CA_BUNDLE},
        expected_url=f"rediss://redis.internal:6379/0?ssl_ca_certs={CA_BUNDLE_QUOTED}",
    ),
    ConnectionStringCase(
        name="tls_insecure_and_ca_file",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True, "tls_ca_file": CA_BUNDLE},
        expected_url=(
            f"rediss://redis.internal:6379/0?ssl_cert_reqs=none&ssl_check_hostname=False&ssl_ca_certs={CA_BUNDLE_QUOTED}"
        ),
    ),
    ConnectionStringCase(
        name="tls_disabled_ignores_tls_options",
        cache_kwargs={
            "address": "redis.internal",
            "tls_enabled": False,
            "tls_insecure": True,
            "tls_ca_file": CA_BUNDLE,
        },
        expected_url="redis://redis.internal:6379/0",
    ),
    ConnectionStringCase(
        name="url_single_node",
        cache_kwargs={"url": "redis://cache:6380/2"},
        expected_url="redis://cache:6380/2",
    ),
    ConnectionStringCase(
        name="url_single_node_with_auth",
        cache_kwargs={"url": "redis://user:secret@cache:6379/0"},
        expected_url="redis://user:secret@cache:6379/0",
    ),
    ConnectionStringCase(
        name="url_single_node_passed_through_verbatim",
        cache_kwargs={"url": "rediss://cache:6379?ssl_cert_reqs=none&ssl_check_hostname=false"},
        expected_url="rediss://cache:6379?ssl_cert_reqs=none&ssl_check_hostname=false",
    ),
    ConnectionStringCase(
        name="url_sentinel_passed_through",
        cache_kwargs={"url": "redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster/1"},
        expected_url="redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster/1",
    ),
    ConnectionStringCase(
        name="url_sentinel_tls_and_auth_passed_through",
        cache_kwargs={"url": "rediss+sentinel://user:secret@sentinel-a:26379/mymaster"},
        expected_url="rediss+sentinel://user:secret@sentinel-a:26379/mymaster",
    ),
    ConnectionStringCase(
        name="url_supersedes_the_scalar_settings",
        cache_kwargs={"url": "redis://cache:6379/0", "address": "other", "username": "user", "tls_enabled": True},
        expected_url="redis://cache:6379/0",
    ),
    ConnectionStringCase(
        name="url_tls_verifies_against_the_configured_ca_bundle",
        cache_kwargs={"url": "rediss://cache:6379/0", "tls_ca_file": CA_BUNDLE},
        expected_url=f"rediss://cache:6379/0?ssl_ca_certs={CA_BUNDLE_QUOTED}",
    ),
    ConnectionStringCase(
        name="url_tls_keeps_its_own_options_alongside_the_ca_bundle",
        cache_kwargs={"url": "rediss+sentinel://s1:26379/mymaster?ssl_check_hostname=false", "tls_ca_file": CA_BUNDLE},
        expected_url=f"rediss+sentinel://s1:26379/mymaster?ssl_check_hostname=false&ssl_ca_certs={CA_BUNDLE_QUOTED}",
    ),
    ConnectionStringCase(
        name="url_ssl_ca_certs_wins_over_the_configured_ca_bundle",
        cache_kwargs={"url": "rediss://cache:6379/0?ssl_ca_certs=/etc/ssl/url-ca.pem", "tls_ca_file": CA_BUNDLE},
        expected_url="rediss://cache:6379/0?ssl_ca_certs=/etc/ssl/url-ca.pem",
    ),
    ConnectionStringCase(
        name="url_ssl_ca_path_wins_over_the_configured_ca_bundle",
        cache_kwargs={"url": "rediss://cache:6379/0?ssl_ca_path=/etc/ssl/certs", "tls_ca_file": CA_BUNDLE},
        expected_url="rediss://cache:6379/0?ssl_ca_path=/etc/ssl/certs",
    ),
    ConnectionStringCase(
        name="url_ssl_ca_data_wins_over_the_configured_ca_bundle",
        cache_kwargs={"url": "rediss://cache:6379/0?ssl_ca_data=PEM", "tls_ca_file": CA_BUNDLE},
        expected_url="rediss://cache:6379/0?ssl_ca_data=PEM",
    ),
    ConnectionStringCase(
        name="url_plaintext_ignores_the_configured_ca_bundle",
        cache_kwargs={"url": "redis://cache:6379/0", "tls_ca_file": CA_BUNDLE},
        expected_url="redis://cache:6379/0",
    ),
]


@pytest.mark.parametrize("case", CONNECTION_STRING_CASES, ids=lambda case: case.name)
def test_build_cache_connection_string(case: ConnectionStringCase) -> None:
    cache = CacheSettings(**case.cache_kwargs)
    assert build_cache_connection_string(cache) == case.expected_url


def test_cache_url_is_ignored_for_a_non_redis_driver() -> None:
    """CacheSettings documents the URL as Redis-only, so NATS keeps the scalar result-storage URL."""
    cache = CacheSettings(
        driver=CacheDriver.NATS,
        address="nats.internal",
        url=SecretStr("redis+sentinel://s1:26379,s2:26379/mymaster"),
    )

    assert build_cache_connection_string(cache) == "redis://nats.internal:4222/0"


def _describe(connection: Connection) -> dict[str, Any]:
    ssl_context = connection.ssl_context if isinstance(connection, SSLConnection) else None
    return {
        "class": type(connection),
        "host": connection.host,
        "port": connection.port,
        "db": connection.db,
        "username": connection.username,
        "password": connection.password,
        "cert_reqs": ssl_context.cert_reqs if ssl_context else None,
        "check_hostname": ssl_context.check_hostname if ssl_context else None,
        "ca_certs": ssl_context.ca_certs if ssl_context else None,
    }


PLAINTEXT = {"class": Connection, "cert_reqs": None, "check_hostname": None, "ca_certs": None}
VERIFIED_TLS = {"class": SSLConnection, "cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True, "ca_certs": None}
NO_CREDENTIALS = {"username": None, "password": None}
DEFAULT_ENDPOINT = {"host": "redis.internal", "port": 6379, "db": 0}


@dataclass
class ScalarCase:
    name: str
    cache_kwargs: dict[str, Any]
    expected: dict[str, Any]


SCALAR_CASES = [
    ScalarCase(
        name="plaintext",
        cache_kwargs={"address": "redis.internal", "port": 6400, "database": 3},
        expected={**PLAINTEXT, **NO_CREDENTIALS, "host": "redis.internal", "port": 6400, "db": 3},
    ),
    ScalarCase(
        name="tls_verifies_the_certificate_and_the_hostname",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True},
        expected={**VERIFIED_TLS, **NO_CREDENTIALS, **DEFAULT_ENDPOINT},
    ),
    ScalarCase(
        name="tls_insecure_skips_verification",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True},
        expected={
            **VERIFIED_TLS,
            **NO_CREDENTIALS,
            **DEFAULT_ENDPOINT,
            "cert_reqs": ssl.CERT_NONE,
            "check_hostname": False,
        },
    ),
    ScalarCase(
        name="tls_ca_file",
        cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_ca_file": CA_BUNDLE},
        expected={**VERIFIED_TLS, **NO_CREDENTIALS, **DEFAULT_ENDPOINT, "ca_certs": CA_BUNDLE},
    ),
    ScalarCase(
        name="username_and_password",
        cache_kwargs={"address": "redis.internal", "username": "user", "password": "secret"},
        expected={**PLAINTEXT, **DEFAULT_ENDPOINT, "username": "user", "password": "secret"},
    ),
    ScalarCase(
        name="password_only_authenticates_as_default_user",
        cache_kwargs={"address": "redis.internal", "password": "secret"},
        expected={**PLAINTEXT, **DEFAULT_ENDPOINT, "username": None, "password": "secret"},
    ),
    ScalarCase(
        name="special_chars_decode_back",
        cache_kwargs={"address": "redis.internal", "username": "us er@name", "password": "p@ss:wor/d?#&"},
        expected={**PLAINTEXT, **DEFAULT_ENDPOINT, "username": "us er@name", "password": "p@ss:wor/d?#&"},
    ),
]


@pytest.mark.parametrize("case", SCALAR_CASES, ids=lambda case: case.name)
def test_build_redis_connection_from_scalar_settings(case: ScalarCase) -> None:
    connection = build_redis_connection(CacheSettings(**case.cache_kwargs)).connection_pool.make_connection()

    assert isinstance(connection, Connection)
    assert _describe(connection) == case.expected


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
    connection = _build("redis://cache").connection_pool.make_connection()

    assert (connection.host, connection.port, connection.db) == ("cache", 6379, 0)


def test_url_connection_retries_like_the_client_default() -> None:
    """Redis.from_url hands the pool no retry policy, so the client default has to be rebuilt.

    Compared against the policy redis-py installs when it builds the pool itself, so a redis-py change
    to the policy's class, count or backoff fails here.
    """
    connection = _build("redis://cache:6379/0").connection_pool.make_connection()
    client_default = Redis().connection_pool.connection_kwargs["retry"]

    assert type(connection.retry) is type(client_default)
    assert connection.retry.get_retries() == client_default.get_retries()
    assert type(connection.retry._backoff) is type(client_default._backoff)
    assert vars(connection.retry._backoff) == vars(client_default._backoff)


def test_url_connection_inherits_the_redis_py_socket_bounds() -> None:
    """The keepalive and the connect/read bounds come from redis-py, so nothing pins them here."""
    connection = _build("redis://cache:6379/0").connection_pool.make_connection()

    assert connection.socket_keepalive is True
    assert connection.socket_keepalive_options == REDIS_PY_KEEPALIVE_OPTIONS
    assert connection.socket_connect_timeout == REDIS_PY_SOCKET_TIMEOUTS
    assert connection.socket_timeout == REDIS_PY_SOCKET_TIMEOUTS


def test_tls_url_ca_bundle_reaches_the_sentinel_daemons() -> None:
    """One CA covers the data nodes and the daemons, which authenticate the same topology."""
    manager = _build("rediss+sentinel://s1:26379/svc", tls_ca_file=CA_BUNDLE).connection_pool.sentinel_manager

    assert manager.sentinel_kwargs["ssl_ca_certs"] == CA_BUNDLE


def test_tls_is_detected_on_a_sentinel_url_urlsplit_cannot_parse() -> None:
    """The scheme is read by hand because urlsplit rejects this member arrangement."""
    url = "rediss+sentinel://sentinel-a:26379,[2001:db8::1]:26379/mymaster"
    with pytest.raises(ValueError, match=r"^Invalid IPv6 URL$"):
        urlsplit(url)

    kwargs = _build(url, tls_ca_file=CA_BUNDLE).connection_pool.connection_kwargs

    assert kwargs["ssl_ca_certs"] == CA_BUNDLE


def test_health_check_interval_pings_idle_connections() -> None:
    """Both paths PING a connection idle past the interval, and a URL option still overrides it."""
    url_pool = _build("redis://cache:6379/0").connection_pool
    scalar_pool = build_redis_connection(CacheSettings(address="redis.internal")).connection_pool
    overridden_pool = _build("redis://cache:6379/0?health_check_interval=7").connection_pool

    assert url_pool.connection_kwargs["health_check_interval"] == REDIS_HEALTH_CHECK_INTERVAL
    assert scalar_pool.connection_kwargs["health_check_interval"] == REDIS_HEALTH_CHECK_INTERVAL
    assert overridden_pool.connection_kwargs["health_check_interval"] == 7


def test_url_query_option_overrides_a_socket_bound() -> None:
    """A URL query option wins over the redis-py default it replaces, and only over that one."""
    connection = _build("redis://cache:6379/0?socket_timeout=7").connection_pool.make_connection()

    assert connection.socket_timeout == 7.0
    assert connection.socket_connect_timeout == REDIS_PY_SOCKET_TIMEOUTS


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
    """The daemon connections carry the same connect/read bounds, so discovery skips a dead daemon."""
    manager = _build("redis+sentinel://s1:26379/svc?sentinel_password=sp").connection_pool.sentinel_manager
    daemon_kwargs = manager.sentinels[0].connection_pool.connection_kwargs

    assert daemon_kwargs["socket_connect_timeout"] == REDIS_PY_SOCKET_TIMEOUTS
    assert daemon_kwargs["socket_timeout"] == REDIS_PY_SOCKET_TIMEOUTS


def test_sentinel_daemons_share_a_socket_option_from_the_url() -> None:
    """A socket option set on the URL reaches the daemons too, not just the data nodes."""
    manager = _build("redis+sentinel://s1:26379/svc?socket_timeout=7").connection_pool.sentinel_manager

    assert manager.sentinel_kwargs["socket_timeout"] == 7.0


def test_sentinel_credentials_do_not_leak_to_the_daemons() -> None:
    """Data-node credentials must not be replayed to the daemons, which authenticate separately."""
    pool = _build("redis+sentinel://app:secret@s1:26379/svc?sentinel_username=su&sentinel_password=sp").connection_pool

    assert pool.connection_kwargs["username"] == "app"
    assert pool.connection_kwargs["password"] == "secret"
    assert pool.sentinel_manager.sentinel_kwargs["username"] == "su"
    assert pool.sentinel_manager.sentinel_kwargs["password"] == "sp"


VALID_URLS = [
    "redis://cache:6379/0",
    "rediss://user:pass@cache:6380/2",
    "rediss://user:s3cr%2Fet%3Fpa%23ss@cache:6380/2",
    "redis+sentinel://s1:26379/mymaster?sentinel_password=p%40ss",
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
    secret_fragments: tuple[str, ...] = ("topsecret",)


UNENCODED_CREDENTIALS = r"^Redis URL has an '@' after its host\. Percent-encode the characters"
SPLIT_PASSWORD = ("s3cr", "etpass")


INVALID_URL_CASES = [
    InvalidUrlCase(
        name="unknown_scheme",
        url="http://u:topsecret@cache:6379",
        match=r"^Redis URL must specify one of the following schemes \(redis://, rediss://, unix://\)$",
    ),
    InvalidUrlCase(
        name="sentinel_without_service",
        url="redis+sentinel://u:topsecret@s1:26379",
        match=r"^A Sentinel connection URL requires a service name",
    ),
    InvalidUrlCase(
        name="invalid_port",
        url="redis://u:topsecret@cache:notaport",
        match=r"^Port could not be cast to integer value as 'notaport'$",
    ),
    InvalidUrlCase(
        name="invalid_sentinel_member_port",
        url="redis+sentinel://u:topsecret@s1:bad/svc",
        match=r"^Invalid port for Sentinel member",
    ),
    InvalidUrlCase(
        name="invalid_pool_option",
        url="rediss://u:topsecret@cache:6379?socket_timeout=abc",
        match=r"^Invalid value for 'socket_timeout' in connection URL\.$",
    ),
    InvalidUrlCase(
        name="misspelled_option",
        url="redis+sentinel://u:topsecret@s1:26379/mymaster?sockettimeout=3",
        match=r"^Redis URL is not valid: .* got an unexpected keyword argument 'sockettimeout'",
    ),
    InvalidUrlCase(
        name="tls_option_on_a_plaintext_scheme",
        url="redis://u:topsecret@cache:6379?ssl_ca_certs=/etc/ca.pem",
        match=r"^Redis URL is not valid: .* got an unexpected keyword argument 'ssl_ca_certs'$",
    ),
    InvalidUrlCase(
        name="unknown_certificate_requirement",
        url="rediss://u:topsecret@cache:6379?ssl_cert_reqs=bogus",
        match=r"^Redis URL is not valid: Invalid SSL Certificate Requirements Flag: bogus$",
    ),
    InvalidUrlCase(
        name="unencoded_slash_in_the_password",
        url="redis://user:s3cr/etpass@cache:6379/0",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=SPLIT_PASSWORD,
    ),
    InvalidUrlCase(
        name="unencoded_question_mark_in_the_password",
        url="redis://user:s3cr?etpass@cache:6379/0",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=SPLIT_PASSWORD,
    ),
    InvalidUrlCase(
        name="unencoded_hash_in_the_password",
        url="redis://user:s3cr#etpass@cache:6379/0",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=SPLIT_PASSWORD,
    ),
    InvalidUrlCase(
        # The digits read as a port, so the rest of the password would be reported as an unknown option.
        name="unencoded_question_mark_after_digits_in_the_password",
        url="redis://user:1234?etpass=x@cache:6379/0",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=("1234", "etpass"),
    ),
    InvalidUrlCase(
        # This one parses, as host "user" and port 1234, which a connection error would then report.
        name="unencoded_slash_after_digits_in_the_password",
        url="redis://user:1234/etpass@cache:6379/0",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=("1234", "etpass"),
    ),
    InvalidUrlCase(
        name="unencoded_slash_in_a_sentinel_password",
        url="redis+sentinel://user:s3cr/etpass@s1:26379/mymaster",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=SPLIT_PASSWORD,
    ),
    InvalidUrlCase(
        name="unencoded_at_sign_in_a_query_value",
        url="redis+sentinel://s1:26379/mymaster?sentinel_password=top@secret",
        match=UNENCODED_CREDENTIALS,
        secret_fragments=("top@secret",),
    ),
]


@pytest.mark.parametrize("case", INVALID_URL_CASES, ids=lambda case: case.name)
def test_validate_redis_url_rejects_without_echoing_the_url(case: InvalidUrlCase) -> None:
    with pytest.raises(ValueError, match=case.match) as exc_info:
        validate_redis_url(case.url)

    for fragment in case.secret_fragments:
        assert fragment not in str(exc_info.value)
