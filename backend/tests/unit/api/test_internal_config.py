from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider

from infrahub import config
from infrahub.api.internal import get_config
from infrahub.config import LDAPServer, LDAPSettings, Settings
from infrahub.telemetry.constants import InfrahubType
from infrahub.workers.dependencies import build_installation_type

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def reset_settings() -> Iterator[None]:
    """Snapshot config.SETTINGS.settings, replace with a fresh Settings, restore on teardown."""
    saved = config.SETTINGS.settings
    config.SETTINGS.settings = Settings()
    yield
    config.SETTINGS.settings = saved


@pytest.fixture
def enterprise_installation_type() -> Iterator[None]:
    """Override `build_installation_type` to return 'enterprise' for the test."""

    def _ent() -> str:
        return InfrahubType.ENTERPRISE.value

    dependency_provider.override(build_installation_type, _ent)
    yield
    dependency_provider.override(build_installation_type, build_installation_type)


def _set_ldap(ldap_settings: LDAPSettings) -> None:
    assert config.SETTINGS.settings is not None
    config.SETTINGS.settings.ldap = ldap_settings


class TestConfigAPILdapShape:
    async def test_default_response_on_community_returns_false_enabled(self, reset_settings: None) -> None:
        cfg = await get_config()
        assert cfg.ldap.enabled is False

    async def test_admin_enabled_alone_does_not_flip_enabled_on_community(self, reset_settings: None) -> None:
        # Community deployment with LDAP config provided must still report enabled=False because the runtime is not active.
        _set_ldap(
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="pw",
                user_search_base="ou=Users,dc=example,dc=com",
            )
        )
        cfg = await get_config()
        assert cfg.ldap.enabled is False

    async def test_enterprise_runtime_alone_does_not_flip_enabled(
        self, reset_settings: None, enterprise_installation_type: None
    ) -> None:
        # Enterprise runtime active but admin has not provided/enabled LDAP
        cfg = await get_config()
        assert cfg.ldap.enabled is False

    async def test_enabled_is_true_when_both_conditions_hold(
        self, reset_settings: None, enterprise_installation_type: None
    ) -> None:
        _set_ldap(
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="pw",
                user_search_base="ou=Users,dc=example,dc=com",
            )
        )
        cfg = await get_config()
        assert cfg.ldap.enabled is True

    async def test_display_label_and_icon_carry_through_resolved_settings(
        self, reset_settings: None, enterprise_installation_type: None
    ) -> None:
        _set_ldap(
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="pw",
                user_search_base="ou=Users,dc=example,dc=com",
                display_label="Sign in with Corp AD",
                icon="mdi:microsoft-active-directory",
            )
        )
        cfg = await get_config()
        assert cfg.ldap.display_label == "Sign in with Corp AD"
        assert cfg.ldap.icon == "mdi:microsoft-active-directory"
