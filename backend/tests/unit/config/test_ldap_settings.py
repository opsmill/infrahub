from __future__ import annotations

import pytest
from pydantic import ValidationError

from infrahub.config import (
    LDAPGroupResolutionStrategy,
    LDAPSettings,
    LDAPTLSMinimumVersion,
)


class TestLDAPServerURIValidation:
    def test_valid_ldap_uri(self) -> None:
        s = LDAPSettings(servers=["ldap://dc1.example.com:389"])
        assert s.servers == ["ldap://dc1.example.com:389"]

    def test_valid_ldaps_uri(self) -> None:
        s = LDAPSettings(servers=["ldaps://dc1.example.com:636"])
        assert s.servers == ["ldaps://dc1.example.com:636"]

    def test_invalid_scheme_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"LDAP URI scheme must be 'ldap' or 'ldaps'"):
            LDAPSettings(servers=["http://dc1.example.com"])

    def test_missing_hostname_rejected(self) -> None:
        with pytest.raises(ValidationError, match="LDAP URI must include a hostname"):
            LDAPSettings(servers=["ldap://"])

    def test_port_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="LDAP URI must include a hostname"):
            LDAPSettings(servers=["ldap://:389"])

    def test_csv_env_var_is_parsed_into_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Operators set this from a single env var; CSV is the wire format.
        monkeypatch.setenv("INFRAHUB_LDAP_SERVERS", "ldap://dc1.example.com:389, ldap://dc2.example.com:389")
        s = LDAPSettings()
        assert s.servers == ["ldap://dc1.example.com:389", "ldap://dc2.example.com:389"]


class TestLDAPTLS:
    def test_defaults(self) -> None:
        s = LDAPSettings()
        assert s.tls_enabled is False
        assert s.tls_starttls is False
        assert s.tls_ca_bundle is None
        assert s.tls_insecure is False
        assert s.tls_minimum_version is LDAPTLSMinimumVersion.TLS_1_2

    def test_disabled_skips_context_build(self) -> None:
        # Should not raise even if the bundle path is bogus, because TLS is off.
        s = LDAPSettings(tls_enabled=False, tls_ca_bundle="/does/not/exist/anywhere.pem")
        assert s.tls_enabled is False

    def test_insecure_with_ca_bundle_is_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"tls_insecure cannot be combined with .*tls_ca_bundle",
        ):
            LDAPSettings(tls_enabled=True, tls_insecure=True, tls_ca_bundle="/etc/ssl/certs/corp.pem")

    def test_enabled_with_no_bundle_and_no_insecure_builds_ok(self) -> None:
        s = LDAPSettings(tls_enabled=True)
        assert s.tls_enabled is True
        assert s.tls_ca_bundle is None
        assert s.tls_insecure is False

    def test_enabled_with_invalid_ca_bundle_is_rejected(self) -> None:
        bogus_pem = "-----BEGIN CERTIFICATE-----\nnot a real cert\n-----END CERTIFICATE-----"
        with pytest.raises(ValidationError, match=r"Unable to load LDAP CA bundle"):
            LDAPSettings(tls_enabled=True, tls_ca_bundle=bogus_pem)


class TestLDAPAttributeMapping:
    def test_defaults_target_active_directory(self) -> None:
        s = LDAPSettings()
        assert s.attribute_username == "sAMAccountName"
        assert s.attribute_email == "mail"
        assert s.attribute_display_name == "displayName"
        assert s.attribute_disabled == "userAccountControl"
        assert s.attribute_disabled_bitmask == 0x2

    def test_disabled_attribute_can_be_disabled(self) -> None:
        # Operators with non-AD directories can null out the disabled check.
        s = LDAPSettings(attribute_disabled=None)
        assert s.attribute_disabled is None


class TestLDAPGroupResolution:
    def test_defaults(self) -> None:
        s = LDAPSettings()
        assert s.group_enabled is False
        assert s.group_base_dn is None
        assert s.group_filter == "(member={user_dn})"
        assert s.group_name_attribute == "cn"
        assert s.group_strategy is LDAPGroupResolutionStrategy.BFS
        assert s.group_bfs_max_depth == 16

    def test_group_enabled_without_base_dn_is_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"ldap\.group_base_dn is required when ldap\.group_enabled is true",
        ):
            LDAPSettings(
                enabled=True,
                servers=["ldap://dc.example.com:389"],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
                group_enabled=True,
                group_base_dn=None,
            )

    def test_group_enabled_with_base_dn_passes(self) -> None:
        s = LDAPSettings(
            enabled=True,
            servers=["ldap://dc.example.com:389"],
            service_account_dn="cn=svc,dc=example,dc=com",
            service_account_password="hunter2",
            user_search_base="ou=Users,dc=example,dc=com",
            group_enabled=True,
            group_base_dn="ou=Groups,dc=example,dc=com",
        )
        assert s.group_enabled is True
        assert s.group_base_dn == "ou=Groups,dc=example,dc=com"

    def test_group_disabled_with_base_dn_does_not_raise(self) -> None:
        # An operator may have group_base_dn pre-set in config but disable
        # group resolution for now; that should not fail validation.
        s = LDAPSettings(
            enabled=True,
            servers=["ldap://dc.example.com:389"],
            service_account_dn="cn=svc,dc=example,dc=com",
            service_account_password="hunter2",
            user_search_base="ou=Users,dc=example,dc=com",
            group_enabled=False,
            group_base_dn="ou=Groups,dc=example,dc=com",
        )
        assert s.group_enabled is False


class TestLDAPSettingsDefaults:
    def test_defaults(self) -> None:
        s = LDAPSettings()
        assert s.enabled is False
        assert s.servers == []
        assert s.service_account_dn is None
        assert s.service_account_password is None
        assert s.user_search_base is None
        # user_search_filter is derived at model-construction time from
        # attribute_username (sAMAccountName by default).
        assert s.user_search_filter == "(sAMAccountName={username})"
        assert s.per_server_timeout == 10.0
        assert s.display_label == "Sign in with LDAP"
        assert s.icon == "mdi:account-key-outline"
        assert s.admin_enabled is False
        assert s.enterprise_features == []

    def test_user_search_filter_derives_from_custom_username_attribute(self) -> None:
        s = LDAPSettings(attribute_username="uid")
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
            servers=["ldap://dc.example.com:389"],
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
                servers=["ldap://dc.example.com:389"],
                service_account_dn=None,
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
            )

    def test_enabled_without_service_account_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.service_account_password is required"):
            LDAPSettings(
                enabled=True,
                servers=["ldap://dc.example.com:389"],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password=None,
                user_search_base="ou=Users,dc=example,dc=com",
            )

    def test_enabled_without_user_search_base_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"ldap\.user_search_base is required"):
            LDAPSettings(
                enabled=True,
                servers=["ldap://dc.example.com:389"],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base=None,
            )

    def test_starttls_and_ldaps_uri_are_mutually_exclusive(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"ldap\.tls_starttls cannot be combined with an ldaps://",
        ):
            LDAPSettings(
                enabled=True,
                servers=["ldaps://dc.example.com:636"],
                service_account_dn="cn=svc,dc=example,dc=com",
                service_account_password="hunter2",
                user_search_base="ou=Users,dc=example,dc=com",
                tls_enabled=True,
                tls_starttls=True,
            )

    def test_disabled_with_incomplete_config_does_not_raise(self) -> None:
        s = LDAPSettings(enabled=False, servers=[], service_account_dn=None)
        assert s.admin_enabled is False
