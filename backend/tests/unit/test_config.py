from infrahub.config import UserInfoMethod, load
from tests.conftest import TestHelper


def test_load_sso_config(helper: TestHelper) -> None:
    fixture_dir = helper.get_fixtures_dir()
    config_file = str(fixture_dir / "config_files" / "sso_config_methods.toml")

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
