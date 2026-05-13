from __future__ import annotations

import pytest
from pydantic import ValidationError

from infrahub.config import (
    LDAPAttributeMap,
    LDAPGroupResolutionStrategy,
    LDAPGroupSearch,
    LDAPServer,
    LDAPSettings,
    LDAPTLSMinimumVersion,
    LDAPTLSSettings,
)


class TestLDAPServer:
    def test_valid_ldap_uri(self) -> None:
        assert LDAPServer(uri="ldap://dc1.example.com:389").uri == "ldap://dc1.example.com:389"

    def test_valid_ldaps_uri(self) -> None:
        assert LDAPServer(uri="ldaps://dc1.example.com:636").uri == "ldaps://dc1.example.com:636"

    def test_invalid_scheme_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"LDAP URI scheme must be 'ldap' or 'ldaps'"):
            LDAPServer(uri="http://dc1.example.com")

    def test_missing_hostname_rejected(self) -> None:
        with pytest.raises(ValidationError, match="LDAP URI must include a hostname"):
            LDAPServer(uri="ldap://")

    def test_port_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="LDAP URI must include a hostname"):
            LDAPServer(uri="ldap://:389")


class TestLDAPTLSSettings:
    def test_defaults(self) -> None:
        tls = LDAPTLSSettings()
        assert tls.enabled is False
        assert tls.starttls is False
        assert tls.tls_ca_bundle is None
        assert tls.tls_insecure is False
        assert tls.minimum_version is LDAPTLSMinimumVersion.TLS_1_2

    def test_disabled_skips_context_build(self) -> None:
        # Should not raise even if the bundle path is bogus, because TLS is off.
        tls = LDAPTLSSettings(enabled=False, tls_ca_bundle="/does/not/exist/anywhere.pem")
        assert tls.enabled is False

    def test_insecure_with_ca_bundle_is_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"tls_insecure cannot be combined with a .*tls_ca_bundle",
        ):
            LDAPTLSSettings(enabled=True, tls_insecure=True, tls_ca_bundle="/etc/ssl/certs/corp.pem")

    def test_enabled_with_no_bundle_and_no_insecure_builds_ok(self) -> None:
        tls = LDAPTLSSettings(enabled=True)
        assert tls.enabled is True
        assert tls.tls_ca_bundle is None
        assert tls.tls_insecure is False


class TestLDAPAttributeMap:
    def test_defaults_target_active_directory(self) -> None:
        m = LDAPAttributeMap()
        assert m.username == "sAMAccountName"
        assert m.email == "mail"
        assert m.display_name == "displayName"
        assert m.disabled_attribute == "userAccountControl"
        assert m.disabled_bitmask == 0x2

    def test_disabled_attribute_can_be_disabled(self) -> None:
        # Operators with non-AD directories can null out the disabled check.
        m = LDAPAttributeMap(disabled_attribute=None)
        assert m.disabled_attribute is None


class TestLDAPGroupSearch:
    def test_defaults(self) -> None:
        gs = LDAPGroupSearch(base_dn="ou=Groups,dc=example,dc=com")
        assert gs.search_filter == "(member={user_dn})"
        assert gs.name_attribute == "cn"
        assert gs.strategy is LDAPGroupResolutionStrategy.BFS
        assert gs.max_depth == 16


class TestLDAPSettingsDefaults:
    def test_defaults(self) -> None:
        s = LDAPSettings()
        assert s.enabled is False
        assert s.servers == []
        assert s.service_account_dn is None
        assert s.service_account_password is None
        assert s.user_search_base is None
        # user_search_filter is derived at model-construction time from
        # attribute_mapping.username (sAMAccountName by default).
        assert s.user_search_filter == "(sAMAccountName={username})"
        assert s.per_server_timeout == 10.0
        assert s.display_label == "Sign in with LDAP"
        assert s.icon == "mdi:account-key-outline"
        assert s.has_any_server is False
        assert s.admin_enabled is False
        assert s.enterprise_features == []

    def test_user_search_filter_derives_from_custom_username_attribute(self) -> None:
        s = LDAPSettings(attribute_mapping=LDAPAttributeMap(username="uid"))
        assert s.user_search_filter == "(uid={username})"

    def test_user_search_filter_explicit_value_is_preserved(self) -> None:
        explicit = "(&(sAMAccountName={username})(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        s = LDAPSettings(user_search_filter=explicit)
        assert s.user_search_filter == explicit


class TestLDAPSettingsEnabledRequirements:
    """Setting `enabled = true` triggers the completeness checks on the rest of the configuration."""

    def test_complete_configuration_passes(self) -> None:
        s = LDAPSettings(
            enabled=True,
            servers=[LDAPServer(uri="ldap://dc.example.com:389")],
            service_account_dn="cn=svc,dc=example,dc=com",
            service_account_password="hunter2",
            user_search_base="ou=Users,dc=example,dc=com",
        )
        assert s.admin_enabled is True

    def test_enabled_without_servers_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.servers must be non-empty"):
            LDAPSettings(
                enabled=True,
                servers=[],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
            )

    def test_enabled_without_service_account_dn_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.service_account_dn is required"):
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn=None,
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
            )

    def test_enabled_without_service_account_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.service_account_password is required"):
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password=None,
                user_search_base="ou=Users,dc=example,dc=com",
            )

    def test_enabled_without_user_search_base_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.user_search_base is required"):
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldap://dc.example.com:389")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base=None,
            )

    def test_starttls_and_ldaps_uri_are_mutually_exclusive(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"ldap\.tls\.starttls cannot be combined with an ldaps://",
        ):
            LDAPSettings(
                enabled=True,
                servers=[LDAPServer(uri="ldaps://dc.example.com:636")],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
                tls=LDAPTLSSettings(enabled=True, starttls=True),
            )

    def test_disabled_with_incomplete_config_does_not_raise(self) -> None:
        s = LDAPSettings(enabled=False, servers=[], service_account_dn=None)
        assert s.admin_enabled is False
