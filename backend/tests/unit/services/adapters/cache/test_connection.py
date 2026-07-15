from dataclasses import dataclass

import pytest

from infrahub.exceptions import RedisUrlError
from infrahub.services.adapters.cache.connection import (
    RedisConnectionConfig,
    parse_redis_url,
    redact_redis_url,
)


@dataclass
class ParseCase:
    name: str
    url: str
    expected: RedisConnectionConfig


PARSE_CASES = [
    ParseCase(
        name="single_node_minimal",
        url="redis://localhost:6379/0",
        expected=RedisConnectionConfig(db=0, is_sentinel=False, host="localhost", port=6379, connection_kwargs={}),
    ),
    ParseCase(
        name="single_node_default_port_and_db",
        url="redis://cache",
        expected=RedisConnectionConfig(db=0, is_sentinel=False, host="cache", port=6379, connection_kwargs={}),
    ),
    ParseCase(
        name="single_node_tls_with_auth_and_encoded_password",
        url="rediss://user:pa%40ss@cache:6380/2",
        expected=RedisConnectionConfig(
            db=2,
            is_sentinel=False,
            host="cache",
            port=6380,
            connection_kwargs={"username": "user", "password": "pa@ss", "ssl": True},
        ),
    ),
    ParseCase(
        name="single_node_username_only",
        url="redis://user@cache:6379",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={"username": "user"},
        ),
    ),
    ParseCase(
        name="single_node_tls_native_ssl_options",
        url="rediss://cache:6379?ssl_cert_reqs=none&ssl_check_hostname=false&ssl_ca_certs=/etc/ca.pem",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={
                "ssl": True,
                "ssl_cert_reqs": "none",
                "ssl_check_hostname": False,
                "ssl_ca_certs": "/etc/ca.pem",
            },
        ),
    ),
    ParseCase(
        name="sentinel_multi_member_with_data_and_sentinel_auth",
        url="redis+sentinel://app:secret@s1:26379,s2:26379,s3:26379/mymaster/1"
        "?sentinel_username=su&sentinel_password=sp",
        expected=RedisConnectionConfig(
            db=1,
            is_sentinel=True,
            service_name="mymaster",
            sentinels=(("s1", 26379), ("s2", 26379), ("s3", 26379)),
            connection_kwargs={"username": "app", "password": "secret"},
            sentinel_kwargs={"username": "su", "password": "sp"},
        ),
    ),
    ParseCase(
        name="sentinel_tls_data_nodes_follow_scheme",
        url="rediss+sentinel://s1:26379/svc",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379),),
            connection_kwargs={"ssl": True},
            sentinel_kwargs={"ssl": True},
        ),
    ),
    ParseCase(
        name="sentinel_tls_ssl_options_shared_with_daemons",
        url="rediss+sentinel://s1:26379/svc?ssl_cert_reqs=none&ssl_check_hostname=false",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379),),
            connection_kwargs={"ssl": True, "ssl_cert_reqs": "none", "ssl_check_hostname": False},
            sentinel_kwargs={"ssl": True, "ssl_cert_reqs": "none", "ssl_check_hostname": False},
        ),
    ),
    ParseCase(
        name="sentinel_member_default_port",
        url="redis+sentinel://s1,s2/svc",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379), ("s2", 26379)),
            connection_kwargs={},
            sentinel_kwargs={},
        ),
    ),
    ParseCase(
        name="sentinel_ipv6_members",
        url="redis+sentinel://[2001:db8::1]:26379,[2001:db8::2]:26380/svc",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("2001:db8::1", 26379), ("2001:db8::2", 26380)),
            connection_kwargs={},
            sentinel_kwargs={},
        ),
    ),
    ParseCase(
        name="single_node_pool_options_funneled",
        url="redis://cache:6379/0?max_connections=50&socket_timeout=5",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=False,
            host="cache",
            port=6379,
            connection_kwargs={"max_connections": 50, "socket_timeout": 5.0},
        ),
    ),
    ParseCase(
        name="sentinel_pool_options_funneled_to_data_nodes",
        url="redis+sentinel://s1:26379/svc?max_connections=10&sentinel_username=su",
        expected=RedisConnectionConfig(
            db=0,
            is_sentinel=True,
            service_name="svc",
            sentinels=(("s1", 26379),),
            connection_kwargs={"max_connections": 10},
            sentinel_kwargs={"username": "su"},
        ),
    ),
]


@pytest.mark.parametrize("case", PARSE_CASES, ids=lambda case: case.name)
def test_parse_redis_url(case: ParseCase) -> None:
    assert parse_redis_url(case.url) == case.expected


@dataclass
class ErrorCase:
    name: str
    url: str
    match: str


ERROR_CASES = [
    ErrorCase(name="unknown_scheme", url="http://cache:6379", match="Unsupported scheme"),
    ErrorCase(name="sentinel_without_service", url="redis+sentinel://s1:26379", match="requires a service name"),
    ErrorCase(name="multiple_hosts_without_sentinel", url="redis://h1:6379,h2:6379", match="require a \\+sentinel"),
    ErrorCase(name="invalid_port", url="redis://cache:notaport", match="Invalid port"),
    ErrorCase(name="db_out_of_range", url="redis://cache:6379/99", match="out of range"),
    ErrorCase(name="invalid_db", url="redis://cache:6379/abc", match="Invalid database index"),
    ErrorCase(name="no_host", url="redis://", match="No host found"),
    ErrorCase(
        name="invalid_pool_option",
        url="redis://cache:6379?socket_timeout=abc",
        match="Invalid connection option",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=lambda case: case.name)
def test_parse_redis_url_errors(case: ErrorCase) -> None:
    with pytest.raises(RedisUrlError, match=case.match):
        parse_redis_url(case.url)


@dataclass
class RedactCase:
    name: str
    url: str
    expected: str


REDACT_CASES = [
    RedactCase(name="no_secret_unchanged", url="redis://cache:6379/0", expected="redis://cache:6379/0"),
    RedactCase(
        name="userinfo_password_masked",
        url="redis://app:secret@cache:6379/0",
        expected="redis://app:***@cache:6379/0",
    ),
    RedactCase(
        name="username_only_kept",
        url="redis://app@cache:6379/0",
        expected="redis://app@cache:6379/0",
    ),
    RedactCase(
        name="sensitive_query_params_masked",
        url="redis+sentinel://app:secret@s1:26379/mymaster?sentinel_password=sp&sentinel_username=su",
        expected="redis+sentinel://app:***@s1:26379/mymaster?sentinel_password=***&sentinel_username=su",
    ),
]


@pytest.mark.parametrize("case", REDACT_CASES, ids=lambda case: case.name)
def test_redact_redis_url(case: RedactCase) -> None:
    assert redact_redis_url(case.url) == case.expected


@dataclass
class NoLeakCase:
    name: str
    url: str
    secret: str


NO_LEAK_CASES = [
    NoLeakCase(name="sentinel_no_service", url="redis+sentinel://u:topsecret@s1:26379", secret="topsecret"),
    NoLeakCase(name="bad_port", url="redis://u:topsecret@cache:nope", secret="topsecret"),
    NoLeakCase(name="bad_pool_option", url="rediss://u:topsecret@cache:6379?socket_timeout=abc", secret="topsecret"),
]


@pytest.mark.parametrize("case", NO_LEAK_CASES, ids=lambda case: case.name)
def test_parse_redis_url_errors_redact_secrets(case: NoLeakCase) -> None:
    with pytest.raises(RedisUrlError) as exc_info:
        parse_redis_url(case.url)
    assert case.secret not in str(exc_info.value)
