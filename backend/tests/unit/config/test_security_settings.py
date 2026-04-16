import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from infrahub.config import SecuritySettings, Settings, UserInfoMethod, load
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


def test_security_settings_requires_secret_key() -> None:
    """SecuritySettings must reject instantiation when secret_key is not provided."""
    env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
    with patch.dict(os.environ, env_clean, clear=True), pytest.raises(ValidationError, match="secret_key"):
        SecuritySettings()  # type: ignore[missing-argument]


def test_security_settings_accepts_explicit_secret_key() -> None:
    """SecuritySettings works when secret_key is passed as a constructor argument."""
    settings = SecuritySettings(secret_key="test-secret-key")
    assert settings.secret_key == "test-secret-key"


def test_security_settings_reads_secret_key_from_env() -> None:
    """SecuritySettings reads secret_key from INFRAHUB_SECURITY_SECRET_KEY env var."""
    with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "from-env"}):
        settings = SecuritySettings()  # type: ignore[missing-argument]
        assert settings.secret_key == "from-env"


def test_settings_fails_without_secret_key() -> None:
    """Settings() fails when secret_key is not available from any source."""
    env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
    with patch.dict(os.environ, env_clean, clear=True), pytest.raises(ValidationError, match="secret_key"):
        Settings()


def test_settings_from_env() -> None:
    """Settings() succeeds when INFRAHUB_SECURITY_SECRET_KEY is in the environment."""
    with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "env-secret"}):
        settings = Settings()
        assert settings.security.secret_key == "env-secret"


def test_settings_from_config_data() -> None:
    """Settings() succeeds when secret_key is provided via config data dict (toml path)."""
    env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
    with patch.dict(os.environ, env_clean, clear=True):
        settings = load(config_data={"security": {"secret_key": "from-toml"}})
        assert settings.security.secret_key == "from-toml"


def test_settings_config_data_without_secret_key_and_no_env_fails() -> None:
    """Config data that provides [security] without secret_key still fails if env var is unset."""
    env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
    with patch.dict(os.environ, env_clean, clear=True), pytest.raises(ValidationError, match="secret_key"):
        load(config_data={"security": {"access_token_lifetime": 7200}})
