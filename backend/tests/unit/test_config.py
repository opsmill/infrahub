import pytest

from infrahub.config import GitSettings, UserInfoMethod, load
from tests.conftest import TestHelper


def test_load_sso_config(helper: TestHelper) -> None:
    config_file = str(helper.get_fixtures_dir() / "config_files" / "sso_config_methods.toml")

    config = load(config_file_name=config_file)
    assert config.security.public_sso_config.enabled
    assert len(config.security.public_sso_config.providers) == 4

    oauth_provider1 = config.security.get_oauth2_provider("provider1")
    oauth_provider2 = config.security.get_oauth2_provider("provider2")

    oidc_provider1 = config.security.get_oidc_provider("provider1")
    oidc_provider2 = config.security.get_oidc_provider("provider2")

    assert oauth_provider1.userinfo_method == UserInfoMethod.POST
    assert oauth_provider2.userinfo_method == UserInfoMethod.GET
    assert oidc_provider1.userinfo_method == UserInfoMethod.POST
    assert oidc_provider2.userinfo_method == UserInfoMethod.GET


def test_valid_git_settings__sync_branch_names():
    sync_branch_names = ["main", "/infrahub/.*/", "/release/.*/"]
    git_settings = GitSettings(sync_branch_names=sync_branch_names)
    assert git_settings.sync_branch_names == sync_branch_names
    assert git_settings._compiled_branch_names == ["main", "infrahub/.*", "release/.*"]


def test_invalid_git_settings__sync_branch_names():
    with pytest.raises(ValueError):
        GitSettings(sync_branch_names=["main", "/infrahub/.*/", "/release/.*/", "/a[b/"])
