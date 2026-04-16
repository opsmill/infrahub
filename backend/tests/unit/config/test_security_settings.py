import os
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from infrahub.config import SecuritySettings, Settings, UserInfoMethod, load
from tests.conftest import TestHelper


class TestSSOConfig:
    def test_load_sso_config(self, helper: TestHelper) -> None:
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


class TestSecretKeyRequired:
    """Tests for the mandatory secret_key field on SecuritySettings."""

    @pytest.fixture
    def _without_secret_key_env(self) -> Iterator[None]:
        """Remove INFRAHUB_SECURITY_SECRET_KEY from the environment so tests don't depend on the developer's shell."""
        env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
        with patch.dict(os.environ, env_clean, clear=True):
            yield

    @pytest.mark.usefixtures("_without_secret_key_env")
    def test_security_settings_requires_secret_key(self) -> None:
        with pytest.raises(ValidationError, match="secret_key"):
            SecuritySettings()

    @pytest.mark.usefixtures("_without_secret_key_env")
    def test_settings_fails_without_secret_key(self) -> None:
        with pytest.raises(ValidationError, match="secret_key"):
            Settings()

    @pytest.mark.usefixtures("_without_secret_key_env")
    def test_settings_config_data_without_secret_key_and_no_env_fails(self) -> None:
        with pytest.raises(ValidationError, match="secret_key"):
            load(config_data={"security": {"access_token_lifetime": 7200}})

    def test_security_settings_accepts_explicit_secret_key(self) -> None:
        settings = SecuritySettings(secret_key="test-secret-key")
        assert settings.secret_key == "test-secret-key"

    def test_security_settings_reads_secret_key_from_env(self) -> None:
        with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "from-env"}):
            settings = SecuritySettings()
            assert settings.secret_key == "from-env"

    def test_settings_from_env(self) -> None:
        with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "env-secret"}):
            settings = Settings()
            assert settings.security.secret_key == "env-secret"

    def test_settings_from_config_data(self) -> None:
        settings = load(config_data={"security": {"secret_key": "from-toml"}})
        assert settings.security.secret_key == "from-toml"
