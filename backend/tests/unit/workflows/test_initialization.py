from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import redis
from redis.connection import Connection, SSLConnection

from infrahub.config import CacheSettings
from infrahub.workflows.initialization import build_cache_connection_string


@dataclass
class ConnectionStringCase:
    name: str
    cache_kwargs: dict
    expected_url: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            ConnectionStringCase(
                name="plain_defaults",
                cache_kwargs={"address": "localhost"},
                expected_url="redis://localhost:6379/0",
            ),
            id="plain_defaults",
        ),
        pytest.param(
            ConnectionStringCase(
                name="plain_custom_port_and_db",
                cache_kwargs={"address": "redis.internal", "port": 6400, "database": 7},
                expected_url="redis://redis.internal:6400/7",
            ),
            id="plain_custom_port_and_db",
        ),
        pytest.param(
            ConnectionStringCase(
                name="plain_user_and_password",
                cache_kwargs={"address": "redis.internal", "username": "user", "password": "secret"},
                expected_url="redis://user:secret@redis.internal:6379/0",
            ),
            id="plain_user_and_password",
        ),
        pytest.param(
            ConnectionStringCase(
                name="plain_password_only",
                cache_kwargs={"address": "redis.internal", "password": "secret"},
                expected_url="redis://:secret@redis.internal:6379/0",
            ),
            id="plain_password_only",
        ),
        pytest.param(
            ConnectionStringCase(
                name="plain_special_chars_escaped",
                cache_kwargs={
                    "address": "redis.internal",
                    "username": "us er@name",
                    "password": "p@ss:wor/d?#&",
                },
                expected_url="redis://us%20er%40name:p%40ss%3Awor%2Fd%3F%23%26@redis.internal:6379/0",
            ),
            id="plain_special_chars_escaped",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_defaults",
                cache_kwargs={"address": "redis.internal", "tls_enabled": True},
                expected_url="rediss://redis.internal:6379/0",
            ),
            id="tls_defaults",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_with_credentials",
                cache_kwargs={
                    "address": "redis.internal",
                    "username": "user",
                    "password": "secret",
                    "tls_enabled": True,
                },
                expected_url="rediss://user:secret@redis.internal:6379/0",
            ),
            id="tls_with_credentials",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_insecure",
                cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True},
                expected_url="rediss://redis.internal:6379/0?ssl_cert_reqs=none&ssl_check_hostname=False",
            ),
            id="tls_insecure",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_ca_file",
                cache_kwargs={
                    "address": "redis.internal",
                    "tls_enabled": True,
                    "tls_ca_file": "/etc/ssl/ca.pem",
                },
                expected_url="rediss://redis.internal:6379/0?ssl_ca_certs=%2Fetc%2Fssl%2Fca.pem",
            ),
            id="tls_ca_file",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_insecure_and_ca_file",
                cache_kwargs={
                    "address": "redis.internal",
                    "tls_enabled": True,
                    "tls_insecure": True,
                    "tls_ca_file": "/etc/ssl/ca.pem",
                },
                expected_url=(
                    "rediss://redis.internal:6379/0"
                    "?ssl_cert_reqs=none&ssl_check_hostname=False&ssl_ca_certs=%2Fetc%2Fssl%2Fca.pem"
                ),
            ),
            id="tls_insecure_and_ca_file",
        ),
        pytest.param(
            ConnectionStringCase(
                name="tls_disabled_ignores_tls_options",
                cache_kwargs={
                    "address": "redis.internal",
                    "tls_enabled": False,
                    "tls_insecure": True,
                    "tls_ca_file": "/etc/ssl/ca.pem",
                },
                expected_url="redis://redis.internal:6379/0",
            ),
            id="tls_disabled_ignores_tls_options",
        ),
        pytest.param(
            ConnectionStringCase(
                name="url_single_node",
                cache_kwargs={"url": "redis://cache:6380/2"},
                expected_url="redis://cache:6380/2",
            ),
            id="url_single_node",
        ),
        pytest.param(
            ConnectionStringCase(
                name="url_single_node_with_auth",
                cache_kwargs={"url": "redis://user:secret@cache:6379/0"},
                expected_url="redis://user:secret@cache:6379/0",
            ),
            id="url_single_node_with_auth",
        ),
        pytest.param(
            ConnectionStringCase(
                name="url_single_node_tls_insecure_native_params",
                cache_kwargs={"url": "rediss://cache:6379?ssl_cert_reqs=none&ssl_check_hostname=false"},
                expected_url="rediss://cache:6379/0?ssl_cert_reqs=none&ssl_check_hostname=False",
            ),
            id="url_single_node_tls_insecure_native_params",
        ),
        pytest.param(
            ConnectionStringCase(
                name="url_sentinel_best_effort_first_member_data_port",
                cache_kwargs={"url": "redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster/1"},
                expected_url="redis://sentinel-a:6379/1",
            ),
            id="url_sentinel_best_effort_first_member_data_port",
        ),
        pytest.param(
            ConnectionStringCase(
                name="url_sentinel_tls_and_auth_best_effort",
                cache_kwargs={"url": "rediss+sentinel://user:secret@sentinel-a:26379/mymaster"},
                expected_url="rediss://user:secret@sentinel-a:6379/0",
            ),
            id="url_sentinel_tls_and_auth_best_effort",
        ),
    ],
)
def test_build_cache_connection_string(case: ConnectionStringCase) -> None:
    cache = CacheSettings(**case.cache_kwargs)
    assert build_cache_connection_string(cache) == case.expected_url


def test_username_without_password_raises() -> None:
    cache = CacheSettings(address="redis.internal", username="user")
    with pytest.raises(ValueError, match=r"INFRAHUB_CACHE_USERNAME is set but INFRAHUB_CACHE_PASSWORD is not"):
        build_cache_connection_string(cache)


@dataclass
class RoundTripCase:
    name: str
    cache_kwargs: dict
    expected_connection_class: type
    expected_kwargs: dict = field(default_factory=dict)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            RoundTripCase(
                name="plaintext_routes_to_plain_connection",
                cache_kwargs={"address": "redis.internal", "port": 6400, "database": 3},
                expected_connection_class=Connection,
                expected_kwargs={"host": "redis.internal", "port": 6400, "db": 3},
            ),
            id="plaintext_routes_to_plain_connection",
        ),
        pytest.param(
            RoundTripCase(
                name="tls_routes_to_ssl_connection",
                cache_kwargs={"address": "redis.internal", "tls_enabled": True},
                expected_connection_class=SSLConnection,
                expected_kwargs={"host": "redis.internal", "port": 6379, "db": 0},
            ),
            id="tls_routes_to_ssl_connection",
        ),
        pytest.param(
            RoundTripCase(
                name="tls_insecure_relaxes_cert_checks",
                cache_kwargs={"address": "redis.internal", "tls_enabled": True, "tls_insecure": True},
                expected_connection_class=SSLConnection,
                expected_kwargs={
                    "host": "redis.internal",
                    "port": 6379,
                    "db": 0,
                    "ssl_cert_reqs": "none",
                    "ssl_check_hostname": False,
                },
            ),
            id="tls_insecure_relaxes_cert_checks",
        ),
        pytest.param(
            RoundTripCase(
                name="tls_ca_file_propagates",
                cache_kwargs={
                    "address": "redis.internal",
                    "tls_enabled": True,
                    "tls_ca_file": "/etc/ssl/ca.pem",
                },
                expected_connection_class=SSLConnection,
                expected_kwargs={
                    "host": "redis.internal",
                    "port": 6379,
                    "db": 0,
                    "ssl_ca_certs": "/etc/ssl/ca.pem",
                },
            ),
            id="tls_ca_file_propagates",
        ),
        pytest.param(
            RoundTripCase(
                name="credentials_propagate",
                cache_kwargs={
                    "address": "redis.internal",
                    "username": "user",
                    "password": "secret",
                    "tls_enabled": True,
                },
                expected_connection_class=SSLConnection,
                expected_kwargs={
                    "host": "redis.internal",
                    "port": 6379,
                    "db": 0,
                    "username": "user",
                    "password": "secret",
                },
            ),
            id="credentials_propagate",
        ),
        pytest.param(
            RoundTripCase(
                name="special_chars_decode_back",
                cache_kwargs={
                    "address": "redis.internal",
                    "username": "us er@name",
                    "password": "p@ss:wor/d?#&",
                },
                expected_connection_class=Connection,
                expected_kwargs={
                    "host": "redis.internal",
                    "port": 6379,
                    "db": 0,
                    "username": "us er@name",
                    "password": "p@ss:wor/d?#&",
                },
            ),
            id="special_chars_decode_back",
        ),
    ],
)
def test_connection_string_round_trip_through_redis_py(case: RoundTripCase) -> None:
    """The URL we build must parse back through redis.ConnectionPool.from_url.

    The parsed connection class and kwargs must match the cache configuration.
    This guards against silent regressions where the URL is syntactically valid
    but semantically wrong (e.g. redis-py changing how it parses ssl_* params).
    """
    cache = CacheSettings(**case.cache_kwargs)
    url = build_cache_connection_string(cache)

    pool = redis.ConnectionPool.from_url(url)

    assert pool.connection_class is case.expected_connection_class
    for key, expected_value in case.expected_kwargs.items():
        assert pool.connection_kwargs.get(key) == expected_value, (
            f"kwarg {key!r}: expected {expected_value!r}, got {pool.connection_kwargs.get(key)!r}"
        )
