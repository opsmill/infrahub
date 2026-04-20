import os
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from infrahub import config
from infrahub.config import SecuritySettings, Settings, UserInfoMethod, load
from infrahub.prefect_server.app import create_infrahub_prefect
from infrahub.server import create_app
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


class TestFactoryValidation:
    """ASGI factories must validate settings before building the app so the server."""

    @staticmethod
    def _unload_settings_with_env(env_overrides: dict[str, str] | None = None) -> Iterator[None]:
        env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
        if env_overrides:
            env_clean.update(env_overrides)
        original_settings = config.SETTINGS.settings
        config.SETTINGS.settings = None
        try:
            with patch.dict(os.environ, env_clean, clear=True):
                yield
        finally:
            config.SETTINGS.settings = original_settings

    @pytest.fixture
    def _with_unloaded_settings_and_no_env(self) -> Iterator[None]:
        yield from self._unload_settings_with_env()

    @pytest.fixture
    def _with_unloaded_settings_and_prefect_distributed_mode(self) -> Iterator[None]:
        # Single-node Prefect skips Infrahub settings validation; these two env
        # vars force the distributed-mode branch in `create_infrahub_prefect()`
        # so the validator runs.
        yield from self._unload_settings_with_env(
            {
                "PREFECT_API_BLOCKS_REGISTER_ON_START": "false",
                "PREFECT_API_DATABASE_MIGRATE_ON_START": "false",
            }
        )

    @pytest.mark.usefixtures("_with_unloaded_settings_and_no_env")
    def test_create_app_fails_without_secret_key(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            create_app()
        assert excinfo.value.code == 1
        output = capsys.readouterr().out
        assert "Configuration not valid, found 1 error(s)" in output
        assert "secret_key must be provided via config or INFRAHUB_SECURITY_SECRET_KEY environment variable" in output

    @pytest.mark.usefixtures("_with_unloaded_settings_and_prefect_distributed_mode")
    def test_create_infrahub_prefect_fails_without_secret_key_in_distributed_mode(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            create_infrahub_prefect()
        assert excinfo.value.code == 1
        output = capsys.readouterr().out
        assert "Configuration not valid, found 1 error(s)" in output
        assert "secret_key must be provided via config or INFRAHUB_SECURITY_SECRET_KEY environment variable" in output

    def test_create_app_succeeds_with_secret_key(self) -> None:
        original_settings = config.SETTINGS.settings
        config.SETTINGS.settings = None
        try:
            with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "test-key"}):
                app = create_app()
        finally:
            config.SETTINGS.settings = original_settings
        assert isinstance(app, FastAPI)
