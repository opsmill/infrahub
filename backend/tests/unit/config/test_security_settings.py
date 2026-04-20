import os
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from infrahub import config
from infrahub.config import SecuritySettings, Settings, UserInfoMethod, load
from infrahub.prefect_server import app as prefect_app_module
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
    """ASGI factories must validate settings before building the app so the server
    cannot bind a socket with invalid configuration."""

    @pytest.fixture(autouse=True)
    def _reset_settings_cache(self) -> Iterator[None]:
        """Snapshot + restore `config.SETTINGS.settings` around every test so
        factory calls start from an unloaded cache and never leak into sibling
        tests (the session-wide autouse fixture in conftest has already loaded
        a real settings object with a dummy key)."""
        original_settings = config.SETTINGS.settings
        config.SETTINGS.settings = None
        try:
            yield
        finally:
            config.SETTINGS.settings = original_settings

    def test_create_app_fails_without_secret_key(self, capsys: pytest.CaptureFixture[str]) -> None:
        env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
        with patch.dict(os.environ, env_clean, clear=True), pytest.raises(SystemExit) as excinfo:
            create_app()
        assert excinfo.value.code == 1
        output = capsys.readouterr().out
        assert "Configuration not valid, found 1 error(s)" in output
        assert "secret_key must be provided via config or INFRAHUB_SECURITY_SECRET_KEY environment variable" in output

    def test_create_infrahub_prefect_fails_without_secret_key_in_distributed_mode(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Single-node Prefect skips Infrahub settings validation; these two env
        # vars force the distributed-mode branch so the validator runs.
        env_clean = {k: v for k, v in os.environ.items() if not k.startswith("INFRAHUB_SECURITY_SECRET")}
        env_clean["PREFECT_API_BLOCKS_REGISTER_ON_START"] = "false"
        env_clean["PREFECT_API_DATABASE_MIGRATE_ON_START"] = "false"
        with patch.dict(os.environ, env_clean, clear=True), pytest.raises(SystemExit) as excinfo:
            create_infrahub_prefect()
        assert excinfo.value.code == 1
        output = capsys.readouterr().out
        assert "Configuration not valid, found 1 error(s)" in output
        assert "secret_key must be provided via config or INFRAHUB_SECURITY_SECRET_KEY environment variable" in output

    def test_create_app_succeeds_with_secret_key(self) -> None:
        with patch.dict(os.environ, {"INFRAHUB_SECURITY_SECRET_KEY": "test-key"}):
            app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_infrahub_prefect_succeeds_in_single_node_mode(self) -> None:
        # Single-node mode (neither PREFECT_API_*_ON_START set to "false") skips
        # the Infrahub settings validator entirely, so no secret key is needed.
        env_clean = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("INFRAHUB_SECURITY_SECRET")
            and k not in {"PREFECT_API_BLOCKS_REGISTER_ON_START", "PREFECT_API_DATABASE_MIGRATE_ON_START"}
        }
        with patch.dict(os.environ, env_clean, clear=True):
            app = create_infrahub_prefect()
        assert isinstance(app, FastAPI)

    def test_create_infrahub_prefect_succeeds_with_secret_key_in_distributed_mode(self) -> None:
        # Distributed mode validates settings and calls `_init_prefect()`, which
        # touches the cache and lock registry — mock it out so this stays a unit test.
        env = {
            "INFRAHUB_SECURITY_SECRET_KEY": "test-key",
            "PREFECT_API_BLOCKS_REGISTER_ON_START": "false",
            "PREFECT_API_DATABASE_MIGRATE_ON_START": "false",
        }
        with (
            patch.dict(os.environ, env),
            patch.object(prefect_app_module, "_init_prefect", new=AsyncMock()) as mock_init,
        ):
            app = create_infrahub_prefect()
        assert isinstance(app, FastAPI)
        mock_init.assert_awaited_once()
