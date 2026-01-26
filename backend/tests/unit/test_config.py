import os
import ssl
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from infrahub.config import SETTINGS, GitSettings, HTTPSettings, StorageSettings, UserInfoMethod, load
from tests.conftest import TestHelper

TEST_DATA_DIR = Path(__file__).parent / "test_data"


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


def test_http_settings_get_tls_context__default_returns_verified() -> None:
    """Default settings should return a context that verifies certificates."""
    settings = HTTPSettings()
    context = settings.get_tls_context()

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_http_settings_get_tls_context__tls_insecure_returns_unverified() -> None:
    """When tls_insecure=True, should return an unverified context."""
    settings = HTTPSettings(tls_insecure=True)
    context = settings.get_tls_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_http_settings_get_tls_context__tls_insecure_with_force_verify_returns_verified() -> None:
    """When tls_insecure=True but force_verify=True, should return a verified context."""
    settings = HTTPSettings(tls_insecure=True)
    context = settings.get_tls_context(force_verify=True)

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_http_settings_get_tls_context__ca_bundle_file_with_force_verify() -> None:
    """When tls_insecure=True with ca_bundle file path and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=str(ca_file))

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_http_settings_get_tls_context__ca_bundle_string_with_force_verify() -> None:
    """When tls_insecure=True with ca_bundle as PEM string and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"
    ca_bundle_content = ca_file.read_text()
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=ca_bundle_content)

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_http_settings_get_tls_context__ca_bundle_long_string_triggers_oserror() -> None:
    """When ca_bundle is a very long string (>500 chars), OSError from Path.exists() is caught.

    This test uses a 4096-bit certificate which is long enough (1600+ chars without newlines)
    to trigger an OSError when Python tries to check if it's a valid file path. The code
    catches this OSError and correctly treats the string as PEM content.
    """
    ca_file = TEST_DATA_DIR / "ca-bundle-4096.pem"
    ca_bundle_content = ca_file.read_text()
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=ca_bundle_content)

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True
