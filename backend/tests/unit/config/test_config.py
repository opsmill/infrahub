import logging
import os
import re
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from infrahub.config import (
    SETTINGS,
    ApiSettings,
    CacheDriver,
    CacheSettings,
    DatabaseSettings,
    GitSettings,
    MainSettings,
    SecurityOAuth2Provider1,
    SecurityOAuth2Provider2,
    SecurityOIDCProvider1,
    SecurityOIDCProvider2,
    SecurityOIDCSettings,
    Settings,
    StorageSettings,
    UserInfoMethod,
    default_cors_allow_headers,
    load,
)
from tests.conftest import TestHelper


def test_load_sso_config(helper: TestHelper) -> None:
    config_file = str(helper.get_fixtures_dir() / "config_files" / "sso_config_methods.toml")

    config = load(config_file_name=config_file)
    assert config.security.public_sso_config.enabled is True
    assert len(config.security.public_sso_config.providers) == 4

    oauth_provider1 = config.security.get_oauth2_provider("provider1")
    oauth_provider2 = config.security.get_oauth2_provider("provider2")

    oidc_provider1 = config.security.get_oidc_provider("provider1")
    oidc_provider2 = config.security.get_oidc_provider("provider2")

    assert oauth_provider1.userinfo_method == UserInfoMethod.POST
    assert oauth_provider2.userinfo_method == UserInfoMethod.GET
    assert oidc_provider1.userinfo_method == UserInfoMethod.POST
    assert oidc_provider2.userinfo_method == UserInfoMethod.GET


def test_default_cors_allow_headers_includes_x_priority() -> None:
    """The shipped CORS allow-list lets cross-origin browsers send the X-Priority header."""
    assert "x-priority" in default_cors_allow_headers()


# no inf/nan values allowed for backpressure settings
_NON_FINITE_BACKPRESSURE_FIELDS = [
    "backpressure_codel_target_seconds",
    "backpressure_codel_interval_seconds",
    "backpressure_high_target_multiplier",
    "backpressure_stress_window_seconds",
    "backpressure_shed_low_stress_ratio",
    "backpressure_shed_medium_stress_ratio",
    "backpressure_shed_high_stress_ratio",
    "backpressure_backstop_low_multiplier",
    "backpressure_backstop_high_multiplier",
    "backpressure_max_concurrency_factor",
    "backpressure_significant_load_stress_ratio",
    "backpressure_sustained_load_warn_seconds",
    "backpressure_sustained_load_high_seconds",
]


@pytest.mark.parametrize("field", _NON_FINITE_BACKPRESSURE_FIELDS)
def test_backpressure_floats_reject_non_finite_values(field: str) -> None:
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValidationError):
            ApiSettings.model_validate({field: value})


def test_backstop_multipliers_keep_the_caps_ordered_by_priority() -> None:
    # MEDIUM's cap is the unscaled base, so a high multiplier below 1 or a low multiplier above 1
    # would leave a higher-priority class with less waiter room than a lower-priority one.
    with pytest.raises(ValidationError):
        ApiSettings(backpressure_backstop_high_multiplier=0.5)
    with pytest.raises(ValidationError):
        ApiSettings(backpressure_backstop_low_multiplier=2.0)

    # A cap equal to the base is the boundary and stays legal for both classes.
    settings = ApiSettings(backpressure_backstop_high_multiplier=1.0, backpressure_backstop_low_multiplier=1.0)
    assert settings.backpressure_backstop_high_multiplier == 1.0
    assert settings.backpressure_backstop_low_multiplier == 1.0


def test_shed_stress_ratios_must_be_ordered_by_priority() -> None:
    message = re.escape("so lower-priority traffic sheds first")
    # HIGH triggering before LOW would shed interactive traffic first — the inverse of the feature.
    with pytest.raises(ValidationError, match=message):
        ApiSettings(backpressure_shed_low_stress_ratio=100.0, backpressure_shed_high_stress_ratio=5.0)
    # MEDIUM may not overtake HIGH either.
    with pytest.raises(ValidationError, match=message):
        ApiSettings(backpressure_shed_medium_stress_ratio=200.0)


def test_shed_stress_ratios_may_be_equal() -> None:
    # Collapsing the triggers makes every class shed together, which is degenerate but coherent.
    settings = ApiSettings(
        backpressure_shed_low_stress_ratio=20.0,
        backpressure_shed_medium_stress_ratio=20.0,
        backpressure_shed_high_stress_ratio=20.0,
    )
    assert settings.backpressure_shed_medium_stress_ratio == 20.0


def test_shipped_backpressure_defaults_satisfy_the_priority_ordering() -> None:
    settings = ApiSettings()

    assert (
        settings.backpressure_shed_low_stress_ratio
        < settings.backpressure_shed_medium_stress_ratio
        < settings.backpressure_shed_high_stress_ratio
    )
    assert settings.backpressure_backstop_low_multiplier <= 1 <= settings.backpressure_backstop_high_multiplier


def test_valid_git_settings__sync_branch_names() -> None:
    import_sync_branch_names = ["main", "infrahub/.*", "release/.*"]
    git_settings = GitSettings(import_sync_branch_names=import_sync_branch_names)
    assert git_settings.import_sync_branch_names == import_sync_branch_names


def test_invalid_git_settings__sync_branch_names() -> None:
    with pytest.raises(ValueError, match="Invalid regex pattern for import_sync_branch_names"):
        GitSettings(import_sync_branch_names=["main", "infrahub/.*", "release/.*", "a[b"])


def test_delete_git_branch_after_merge_without_delete_branch_after_merge_raises() -> None:
    with pytest.raises(ValueError, match=re.escape("requires 'delete_branch_after_merge' to be enabled")):
        Settings(
            git=GitSettings(delete_git_branch_after_merge=True), main=MainSettings(delete_branch_after_merge=False)
        )


def test_storage_max_file_size() -> None:
    assert StorageSettings().max_file_size == 50
    assert StorageSettings(max_file_size=100).max_file_size == 100
    assert StorageSettings(max_file_size=1).max_file_size == 1


@pytest.mark.parametrize("invalid_value", [0, -10])
def test_storage_max_file_size_rejects_invalid_values(invalid_value: int) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        StorageSettings(max_file_size=invalid_value)


def test_storage_max_file_size_environment_variable() -> None:
    with patch.dict(os.environ, {"INFRAHUB_STORAGE_MAX_FILE_SIZE": "75"}):
        assert StorageSettings().max_file_size == 75
    assert isinstance(SETTINGS.storage.max_file_size, int)


def test_database_address_single_member() -> None:
    settings = DatabaseSettings(address="localhost")
    assert settings.address_members == ["localhost"]
    assert settings.database_uri == "bolt://localhost:7687"


def test_database_address_multiple_members() -> None:
    settings = DatabaseSettings(address="member1, member2:7777,member3")
    assert settings.address_members == ["member1", "member2:7777", "member3"]
    assert settings.database_uri == "bolt://member1:7687"


def test_database_address_first_member_with_port() -> None:
    settings = DatabaseSettings(address="member1:9999,member2")
    assert settings.database_uri == "bolt://member1:9999"


def test_database_address_ipv6_member() -> None:
    settings = DatabaseSettings(address="[::1]:9999,member2")
    assert settings.address_members == ["[::1]:9999", "member2"]
    assert settings.database_uri == "bolt://[::1]:9999"


def test_database_uri_with_policy() -> None:
    settings = DatabaseSettings(address="member1,member2", policy="europe")
    assert settings.database_uri == "bolt://member1:7687?policy=europe"


def test_database_pool_timeout_defaults() -> None:
    # Both unset by default: the driver's own defaults apply (3600s lifetime, no liveness check).
    settings = DatabaseSettings()
    assert settings.max_connection_lifetime is None
    assert settings.liveness_check_timeout is None


def test_database_pool_timeout_environment_variables() -> None:
    with patch.dict(
        os.environ,
        {"INFRAHUB_DB_MAX_CONNECTION_LIFETIME": "600", "INFRAHUB_DB_LIVENESS_CHECK_TIMEOUT": "0"},
    ):
        settings = DatabaseSettings()
    assert settings.max_connection_lifetime == 600
    assert settings.liveness_check_timeout == 0


def _make_oidc_provider(verify_signature: bool) -> SecurityOIDCSettings:
    return SecurityOIDCSettings(
        client_id="testing-client",
        discovery_url="https://oidc.example.com/.well-known/openid-configuration",
        id_token_verify_signature=verify_signature,
    )


def test_oidc_disabled_signature_verification_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub"):
        provider = _make_oidc_provider(verify_signature=False)

    assert provider.id_token_verify_signature is False
    warnings = [record for record in caplog.records if "OIDC id_token verification is disabled" in record.message]
    assert len(warnings) == 1


def test_oidc_default_signature_verification_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub"):
        provider = _make_oidc_provider(verify_signature=True)

    assert provider.id_token_verify_signature is True
    assert not [record for record in caplog.records if "OIDC id_token verification is disabled" in record.message]


def _build_oauth2_provider(groups_claim: str = "groups") -> SecurityOAuth2Provider1:
    return SecurityOAuth2Provider1(
        client_id="infrahub-client",
        client_secret="secret",
        authorization_url="https://idp.example.com/auth",
        token_url="https://idp.example.com/token",
        userinfo_url="https://idp.example.com/userinfo",
        groups_claim=groups_claim,
    )


def _build_oauth2_provider_2(groups_claim: str = "groups") -> SecurityOAuth2Provider2:
    return SecurityOAuth2Provider2(
        client_id="infrahub-client",
        client_secret="secret",
        authorization_url="https://idp.example.com/auth",
        token_url="https://idp.example.com/token",
        userinfo_url="https://idp.example.com/userinfo",
        groups_claim=groups_claim,
    )


def _build_oidc_provider(groups_claim: str = "groups") -> SecurityOIDCProvider1:
    return SecurityOIDCProvider1(
        client_id="infrahub-client",
        client_secret="secret",
        discovery_url="https://idp.example.com/.well-known/openid-configuration",
        groups_claim=groups_claim,
    )


def _build_oidc_provider_2(groups_claim: str = "groups") -> SecurityOIDCProvider2:
    return SecurityOIDCProvider2(
        client_id="infrahub-client",
        client_secret="secret",
        discovery_url="https://idp.example.com/.well-known/openid-configuration",
        groups_claim=groups_claim,
    )


def test_groups_claim_default_is_groups() -> None:
    assert _build_oauth2_provider().groups_claim == "groups"
    assert _build_oauth2_provider_2().groups_claim == "groups"
    assert _build_oidc_provider().groups_claim == "groups"
    assert _build_oidc_provider_2().groups_claim == "groups"


@pytest.mark.parametrize("empty_value", ["", " ", "\t", "\n", "  \t\n  "])
def test_groups_claim_empty_string_is_rejected_at_startup_oauth2(empty_value: str) -> None:
    with pytest.raises(ValidationError, match=r"groups_claim must not be empty or whitespace-only"):
        _build_oauth2_provider(groups_claim=empty_value)


@pytest.mark.parametrize("empty_value", ["", " ", "\t", "\n", "  \t\n  "])
def test_groups_claim_empty_string_is_rejected_at_startup_oidc(empty_value: str) -> None:
    with pytest.raises(ValidationError, match=r"groups_claim must not be empty or whitespace-only"):
        _build_oidc_provider(groups_claim=empty_value)


@dataclass
class GroupsClaimStripCase:
    name: str
    value: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        GroupsClaimStripCase(name="trailing_space", value="groups ", expected="groups"),
        GroupsClaimStripCase(name="leading_space", value=" groups", expected="groups"),
        GroupsClaimStripCase(name="surrounding_whitespace", value="  roles\t\n", expected="roles"),
    ],
    ids=lambda case: case.name,
)
def test_groups_claim_is_stripped_oauth2(case: GroupsClaimStripCase) -> None:
    assert _build_oauth2_provider(groups_claim=case.value).groups_claim == case.expected
    assert _build_oauth2_provider_2(groups_claim=case.value).groups_claim == case.expected


@pytest.mark.parametrize(
    "case",
    [
        GroupsClaimStripCase(name="trailing_space", value="groups ", expected="groups"),
        GroupsClaimStripCase(name="leading_space", value=" groups", expected="groups"),
        GroupsClaimStripCase(name="surrounding_whitespace", value="  roles\t\n", expected="roles"),
    ],
    ids=lambda case: case.name,
)
def test_groups_claim_is_stripped_oidc(case: GroupsClaimStripCase) -> None:
    assert _build_oidc_provider(groups_claim=case.value).groups_claim == case.expected
    assert _build_oidc_provider_2(groups_claim=case.value).groups_claim == case.expected


@dataclass
class DatabaseNameCase:
    name: str
    value: str


@pytest.mark.parametrize(
    "case",
    [
        DatabaseNameCase(name="simple", value="infrahub"),
        DatabaseNameCase(name="minimum_length", value="abc"),
        DatabaseNameCase(name="with_digits", value="infrahub2"),
        DatabaseNameCase(name="leading_digit", value="1nfrahub"),
        DatabaseNameCase(name="with_dash", value="my-database"),
        DatabaseNameCase(name="with_dot", value="my.database"),
        DatabaseNameCase(name="dash_and_dot", value="my-infrahub.db"),
        DatabaseNameCase(name="maximum_length", value="a" * 63),
        DatabaseNameCase(name="default_neo4j", value="neo4j"),
        DatabaseNameCase(name="default_memgraph", value="memgraph"),
    ],
    ids=lambda case: case.name,
)
def test_database_name_accepts_valid_neo4j_names(case: DatabaseNameCase) -> None:
    assert DatabaseSettings(database=case.value).database == case.value


@pytest.mark.parametrize(
    "case",
    [
        DatabaseNameCase(name="too_short", value="ab"),
        DatabaseNameCase(name="too_long", value="a" * 64),
        DatabaseNameCase(name="trailing_dot", value="infrahub."),
        DatabaseNameCase(name="trailing_dash", value="infrahub-"),
        DatabaseNameCase(name="leading_dot", value=".infrahub"),
        DatabaseNameCase(name="leading_dash", value="-infrahub"),
        DatabaseNameCase(name="uppercase", value="Infrahub"),
        DatabaseNameCase(name="underscore", value="my_database"),
        DatabaseNameCase(name="space", value="my database"),
        DatabaseNameCase(name="backtick", value="my`database"),
    ],
    ids=lambda case: case.name,
)
def test_database_name_rejects_invalid_neo4j_names(case: DatabaseNameCase) -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        DatabaseSettings(database=case.value)


def test_fixture_loaded_providers_have_expected_groups_claim(helper: TestHelper) -> None:
    config_file = str(helper.get_fixtures_dir() / "config_files" / "sso_config_methods.toml")
    config = load(config_file_name=config_file)

    assert config.security.get_oauth2_provider("provider1").groups_claim == "roles"
    assert config.security.get_oauth2_provider("provider2").groups_claim == "groups"
    assert config.security.get_oidc_provider("provider1").groups_claim == "roles"
    assert config.security.get_oidc_provider("provider2").groups_claim == "groups"


def test_cache_url_supersedes_scalar_connection_fields() -> None:
    """A URL alongside scalar settings is accepted; the URL wins and the override is reported.

    Rejecting the combination is not an option: the shipped Compose files set every scalar cache
    variable unconditionally, so an exclusivity error would make INFRAHUB_CACHE_URL unusable there.
    """
    with patch("infrahub.config.log") as mock_log:
        settings = CacheSettings(url=SecretStr("redis://cache:6379/0"), address="other")

    assert settings.url is not None
    assert settings.url.get_secret_value() == "redis://cache:6379/0"
    mock_log.warning.assert_called_once()
    assert mock_log.warning.call_args.kwargs["superseded_settings"] == ["INFRAHUB_CACHE_ADDRESS"]


def test_cache_url_loads_under_the_compose_environment() -> None:
    """The shipped docker-compose.yml sets every scalar cache variable, most at their default.

    A default-valued scalar carries no operator intent, so it must neither fail the load nor be
    reported as superseded. Only INFRAHUB_CACHE_ADDRESS differs from its default here.
    """
    compose_env = {
        "INFRAHUB_CACHE_URL": "redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster",
        "INFRAHUB_CACHE_ADDRESS": "cache",
        "INFRAHUB_CACHE_DATABASE": "0",
        "INFRAHUB_CACHE_DRIVER": "redis",
        "INFRAHUB_CACHE_PASSWORD": "",
        "INFRAHUB_CACHE_USERNAME": "",
        "INFRAHUB_CACHE_TLS_ENABLED": "false",
        "INFRAHUB_CACHE_TLS_INSECURE": "false",
    }
    with patch.dict(os.environ, compose_env), patch("infrahub.config.log") as mock_log:
        settings = CacheSettings()

    assert settings.url is not None
    assert settings.url.get_secret_value() == compose_env["INFRAHUB_CACHE_URL"]
    assert mock_log.warning.call_args.kwargs["superseded_settings"] == ["INFRAHUB_CACHE_ADDRESS"]


def test_cache_url_does_not_report_defaulted_scalars() -> None:
    """Scalars explicitly set to their own default value are not reported as superseded."""
    with (
        patch.dict(os.environ, {"INFRAHUB_CACHE_ADDRESS": "localhost", "INFRAHUB_CACHE_PASSWORD": ""}),
        patch("infrahub.config.log") as mock_log,
    ):
        settings = CacheSettings(url=SecretStr("redis://cache:6379/0"))

    assert settings.url is not None
    mock_log.warning.assert_not_called()


def test_cache_url_coexists_with_redis_driver() -> None:
    settings = CacheSettings(url=SecretStr("redis://cache:6379/0"), driver=CacheDriver.Redis)
    assert settings.driver is CacheDriver.Redis
    assert settings.url is not None


def test_cache_url_ignored_for_non_redis_driver() -> None:
    # The URL is only consulted by the Redis driver, so a non-Redis driver neither enforces
    # exclusivity with the scalar fields nor parses the URL as a Redis URL: this combines a scalar
    # field with a URL whose scheme is not a valid Redis scheme, and neither should raise.
    settings = CacheSettings(url=SecretStr("nats://nats:4222"), address="nats", driver=CacheDriver.NATS)
    assert settings.driver is CacheDriver.NATS
    assert settings.url is not None


def test_cache_url_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError, match="requires a service name"):
        CacheSettings(url=SecretStr("redis+sentinel://sentinel-a:26379"))


def test_cache_url_validation_error_redacts_secret() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CacheSettings(url=SecretStr("redis+sentinel://user:topsecret@sentinel-a:26379"))
    assert "topsecret" not in str(exc_info.value)


def test_cache_url_environment_variable() -> None:
    url = "redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster"
    with patch.dict(os.environ, {"INFRAHUB_CACHE_URL": url}):
        settings = CacheSettings()
    assert settings.url is not None
    assert settings.url.get_secret_value() == url
