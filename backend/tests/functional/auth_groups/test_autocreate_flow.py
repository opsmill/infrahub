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
from infrahub.core.node import Node
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


@pytest.fixture
def sso_user_default_group_configured() -> Iterator[str]:
    """Set `sso_user_default_group` to a stable name and restore on teardown.

    The fixture does NOT pre-create the matching `CoreAccountGroup` row — each test creates
    it explicitly so the membership assertion is unambiguous about what was set up.
    """
    original = config.SETTINGS.security.sso_user_default_group
    default_name = "sso-default-group"
    config.SETTINGS.security.sso_user_default_group = default_name
    try:
        yield default_name
    finally:
        config.SETTINGS.security.sso_user_default_group = original


@pytest.fixture
def sso_user_default_group_unset() -> Iterator[None]:
    """Force `sso_user_default_group` to None for the duration of the test."""
    original = config.SETTINGS.security.sso_user_default_group
    config.SETTINGS.security.sso_user_default_group = None
    try:
        yield
    finally:
        config.SETTINGS.security.sso_user_default_group = original


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
        identity_b = _make_identity(sub="sub-autocreate-shared-2", provider_name="OktaProd", display_name="Dave Auto")

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


class TestDefaultGroupFallback:
    """IFC-922 default-group fallback behavior owned by `_assign_group_memberships`.

    These tests pin down the spec contract that when auto-creation produces no memberships
    (filter active but no claim matches, or filter inactive with empty claims), the user is
    added to `sso_user_default_group` if it is configured. They also lock down that a
    matched claim takes precedence over the default group (Story 3 #2).
    """

    async def test_filter_active_non_matching_claims_fall_through_to_default_group(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
        sso_user_default_group_configured: str,
    ) -> None:
        """Filter active + non-empty claims + zero matches + default configured: user lands in
        the default group. The non-matching original claims must NOT have become groups
        (FR-001 / Story 2 #1 silently-skip semantics).
        """
        default_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await default_group.new(db=db, name=sso_user_default_group_configured)
        await default_group.save(db=db)

        identity = _make_identity(sub="sub-default-fallback-1", display_name="Iris Default")

        await signin_sso_account(
            db=db,
            external_identity=identity,
            sso_groups=["slack/general-z", "github/contributors-z"],
        )

        assert await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "slack/general-z"}) == []
        assert (
            await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "github/contributors-z"})
            == []
        )

        refreshed = await NodeManager.get_one(db=db, id=default_group.id, prefetch_relationships=True)
        members_rel = refreshed.get_relationship(name="members")
        members = await members_rel.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Iris Default"})
        assert len(accounts) == 1
        assert accounts[0].id in members

    async def test_filter_active_empty_claims_fall_through_to_default_group(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
        sso_user_default_group_configured: str,
    ) -> None:
        """Filter active + empty claims + default configured: user lands in the default group.

        Pre-refactor, the `if not sso_groups: sso_groups = [default]` swap-in lived upstream in
        oidc.py / oauth2.py. Post-refactor it is owned by `_assign_group_memberships`; this test
        invokes that function directly with an empty claim list, which is the path the upstream
        callers now always take.
        """
        default_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await default_group.new(db=db, name=sso_user_default_group_configured)
        await default_group.save(db=db)

        identity = _make_identity(sub="sub-default-fallback-empty", display_name="Jules Default")

        await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

        refreshed = await NodeManager.get_one(db=db, id=default_group.id, prefetch_relationships=True)
        members_rel = refreshed.get_relationship(name="members")
        members = await members_rel.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Jules Default"})
        assert len(accounts) == 1
        assert accounts[0].id in members

    async def test_filter_active_no_match_no_default_configured_yields_no_membership(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
        sso_user_default_group_unset: None,
    ) -> None:
        """Filter active + non-empty claims + zero matches + no default configured: the login
        completes but the user gets no group membership. This locks down that "no default" is
        not treated as an error.
        """
        identity = _make_identity(sub="sub-no-fallback-1", display_name="Kai NoDefault")

        auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=["slack/general-w"])

        assert auth_result.token.access_token, "login must still succeed when no default exists"
        assert await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "slack/general-w"}) == []

    async def test_match_takes_precedence_over_default(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
        sso_user_default_group_configured: str,
    ) -> None:
        """When at least one claim matches the filter, the auto-created (or reused) group wins
        and the default group is NOT stacked on top (Story 3 acceptance #2).
        """
        default_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await default_group.new(db=db, name=sso_user_default_group_configured)
        await default_group.save(db=db)

        identity = _make_identity(sub="sub-match-precedence-1", display_name="Lea Match")

        await signin_sso_account(
            db=db,
            external_identity=identity,
            sso_groups=["slack/general-q", "LDAP/group/matched-precedence-q"],
        )

        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Lea Match"})
        assert len(accounts) == 1
        account_id = accounts[0].id

        matched = await NodeManager.query(
            db=db, schema=CoreAccountGroup, filters={"name__value": "matched-precedence-q"}
        )
        assert len(matched) == 1
        refreshed_match = await NodeManager.get_one(db=db, id=matched[0].id, prefetch_relationships=True)
        match_members = await refreshed_match.get_relationship(name="members").get_peers(
            db=db, branch_agnostic=True, peer_type=CoreAccount
        )
        assert account_id in match_members

        refreshed_default = await NodeManager.get_one(db=db, id=default_group.id, prefetch_relationships=True)
        default_members = await refreshed_default.get_relationship(name="members").get_peers(
            db=db, branch_agnostic=True, peer_type=CoreAccount
        )
        assert account_id not in default_members, "default group must not be added on top of a matched group"

    async def test_filter_disabled_empty_claims_fall_through_to_default_group(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_disabled: None,
        sso_user_default_group_configured: str,
    ) -> None:
        """Filter inactive + empty claims + default configured: user lands in the default group.

        Locks down legacy IFC-922 parity now that the fallback lives inside
        `_assign_group_memberships` rather than upstream in oidc.py / oauth2.py.
        """
        default_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await default_group.new(db=db, name=sso_user_default_group_configured)
        await default_group.save(db=db)

        identity = _make_identity(sub="sub-legacy-default-1", display_name="Mira Legacy")

        await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

        refreshed = await NodeManager.get_one(db=db, id=default_group.id, prefetch_relationships=True)
        members = await refreshed.get_relationship(name="members").get_peers(
            db=db, branch_agnostic=True, peer_type=CoreAccount
        )
        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Mira Legacy"})
        assert len(accounts) == 1
        assert accounts[0].id in members
