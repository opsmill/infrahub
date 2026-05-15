"""Functional tests for the auto-creation flow under `signin_sso_account`.

Drives the real `signin_sso_account` (and therefore the real `autocreate_groups_for_login`
service) against the test database — no mocking of either. Fixtures follow the pattern in
`backend/tests/component/core/test_signin_sso_account.py` (`db`, `default_branch`,
`register_core_models_schema`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.auth import ExternalAuthProtocol, ExternalIdentity, signin_sso_account
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccount, CoreAccountGroup

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
def autocreate_filter_enabled() -> Iterator[None]:
    """Enable the auto-creation filter for the duration of the test.

    Uses the real `SecuritySettings` validator chain so the compiled-pattern invariant from
    config.py is exercised end-to-end. Restores the previous setting on teardown.
    """
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = r"^LDAP/group/(?P<name>.+)$"
    config.SETTINGS.security._compile_auto_create_groups_filter_patterns()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


@pytest.fixture
def autocreate_filter_disabled() -> Iterator[None]:
    """Force the auto-creation filter OFF for the duration of the test (legacy path)."""
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = None
    config.SETTINGS.security._auto_create_groups_filter_patterns = ()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


def _make_identity(
    sub: str, *, provider_name: str = "AzureAD-corp", display_name: str = "Alice Auto"
) -> ExternalIdentity:
    return ExternalIdentity(
        sub=sub,
        provider_name=provider_name,
        protocol=ExternalAuthProtocol.OIDC,
        display_name=display_name,
        email=f"{display_name.lower().replace(' ', '.')}@example.com",
    )


class TestAutoCreationWhenFilterEnabled:
    """Behavior of the SSO sign-in path when `auto_create_groups_filter` is configured."""

    async def test_filter_match_creates_group_with_origin_set_to_provider_name(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
    ) -> None:
        """A first-time login with a matching claim creates a local group named from the captured
        `name` group, with `origin` set to the configured provider name and the user added as a
        member.
        """
        identity = _make_identity(sub="sub-autocreate-001", provider_name="AzureAD-corp")

        await signin_sso_account(db=db, external_identity=identity, sso_groups=["LDAP/group/network-engineering-a"])

        groups = await NodeManager.query(
            db=db, schema=CoreAccountGroup, filters={"name__value": "network-engineering-a"}
        )
        assert len(groups) == 1, "exactly one group must be created"
        group = groups[0]
        assert group.origin.value == "AzureAD-corp", "origin must hold the configured provider name verbatim"

        refreshed = await NodeManager.get_one(db=db, id=group.id, prefetch_relationships=True)
        members = await refreshed.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Alice Auto"})
        assert len(accounts) == 1
        assert accounts[0].id in members

    async def test_subsequent_login_reuses_existing_group_and_origin_is_not_overwritten(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
    ) -> None:
        """A second user's login carrying the same external claim reuses the existing group (no
        duplicate creation) and `origin` is not re-written.
        """
        identity_a = _make_identity(
            sub="sub-autocreate-shared-1", provider_name="AzureAD-corp", display_name="Carol Auto"
        )
        identity_b = _make_identity(
            sub="sub-autocreate-shared-2", provider_name="OktaProd", display_name="Dave Auto"
        )

        await signin_sso_account(db=db, external_identity=identity_a, sso_groups=["LDAP/group/network-engineering-b"])
        await signin_sso_account(db=db, external_identity=identity_b, sso_groups=["LDAP/group/network-engineering-b"])

        groups = await NodeManager.query(
            db=db, schema=CoreAccountGroup, filters={"name__value": "network-engineering-b"}
        )
        assert len(groups) == 1, "no duplicate group must be created on second login"
        assert groups[0].origin.value == "AzureAD-corp", (
            "origin must retain the first-creation provider name; subsequent contributions do not overwrite it"
        )

        refreshed = await NodeManager.get_one(db=db, id=groups[0].id, prefetch_relationships=True)
        members = await refreshed.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
        carol = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Carol Auto"})
        dave = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Dave Auto"})
        assert carol[0].id in members
        assert dave[0].id in members

    async def test_filter_without_named_capture_uses_full_claim_as_name(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        """A pattern without a `name` named capture group uses the full claim string as the local
        group name.
        """
        original_filter = config.SETTINGS.security.auto_create_groups_filter
        original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns
        config.SETTINGS.security.auto_create_groups_filter = r"^network-.*$"
        config.SETTINGS.security._compile_auto_create_groups_filter_patterns()

        try:
            identity = _make_identity(sub="sub-autocreate-fullclaim", display_name="Eve Auto")
            await signin_sso_account(db=db, external_identity=identity, sso_groups=["network-eng-c"])

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "network-eng-c"})
            assert len(groups) == 1
            assert groups[0].origin.value == "AzureAD-corp"
        finally:
            config.SETTINGS.security.auto_create_groups_filter = original_filter
            config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled

    async def test_within_login_dedup_collapses_duplicate_effective_names(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
    ) -> None:
        """Two claims that resolve to the same effective name within one login produce one
        membership operation and one group.
        """
        identity = _make_identity(sub="sub-autocreate-dedup-001", display_name="Frank Auto")

        # Both claims match the filter and resolve to the same captured name `dedup-target-1`.
        await signin_sso_account(
            db=db,
            external_identity=identity,
            sso_groups=["LDAP/group/dedup-target-1", "LDAP/group/dedup-target-1"],
        )

        groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "dedup-target-1"})
        assert len(groups) == 1

    async def test_non_matching_claims_produce_no_groups_when_filter_is_on(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
    ) -> None:
        """Claims that do not match the filter are silently skipped; only matching claims drive
        group creation.
        """
        identity = _make_identity(sub="sub-non-matching-001", display_name="Hugo Auto")

        await signin_sso_account(
            db=db,
            external_identity=identity,
            sso_groups=["slack/general-y", "github/contributors-y", "LDAP/group/matched-y"],
        )

        assert await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "slack/general-y"}) == []
        assert (
            await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "github/contributors-y"})
            == []
        )
        matched = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "matched-y"})
        assert len(matched) == 1


class TestAutoCreationWhenFilterDisabled:
    """Behavior of the SSO sign-in path when `auto_create_groups_filter` is unset / empty."""

    async def test_legacy_lookup_path_runs_when_filter_disabled(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_disabled: None,
    ) -> None:
        """When the filter is unset, the auto-creation flow does NOT run and the legacy
        exact-name-lookup-and-add path is used. Verifies that no group is auto-created from a claim
        that has no matching pre-existing group.
        """
        identity = _make_identity(sub="sub-legacy-noop-001", display_name="Greta Legacy")

        await signin_sso_account(db=db, external_identity=identity, sso_groups=["LDAP/group/should-not-be-created-x"])

        groups = await NodeManager.query(
            db=db, schema=CoreAccountGroup, filters={"name__value": "should-not-be-created-x"}
        )
        assert len(groups) == 0, "auto-creation must be inactive when no filter is configured"
