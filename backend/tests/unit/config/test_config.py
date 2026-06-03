import logging
import os
import re
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from infrahub.config import (
    SETTINGS,
    GitSettings,
    MainSettings,
    SecurityOIDCSettings,
    Settings,
    StorageSettings,
    UserInfoMethod,
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
