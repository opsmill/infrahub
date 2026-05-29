import uuid
from collections.abc import Iterator

import pytest

from infrahub import config
from infrahub.auth import ExternalAuthProtocol, ExternalIdentity, signin_sso_account
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ProcessingError


@pytest.fixture
def sso_account_name_fallback_disabled() -> Iterator[None]:
    original = config.SETTINGS.security.sso_account_name_fallback
    config.SETTINGS.security.sso_account_name_fallback = False
    yield
    config.SETTINGS.security.sso_account_name_fallback = original


async def test_new_user_creates_account_and_identity(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A first-time login must bootstrap both the account and the identity node in a single.

    call so that subsequent logins resolve via the stable sub rather than the mutable display name.

    """
    identity = ExternalIdentity(
        sub="sub-new-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Alice Baker",
        email="alice@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    assert auth_result.token.access_token
    assert auth_result.token.refresh_token

    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Alice Baker"})
    assert len(accounts) == 1
    account = accounts[0]
    assert account.label.value == "Alice Baker"

    identity_nodes = await NodeManager.query(
        db=db,
        schema=InfrahubKind.EXTERNALIDENTITY,
        filters={"sub__value": "sub-new-001", "provider_name__value": "provider1", "protocol__value": "oidc"},
    )
    assert len(identity_nodes) == 1
    linked_account = await identity_nodes[0].account.get_peer(db=db)
    assert linked_account.id == account.id


async def test_returning_user_resolves_via_identity_node(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Once an identity node exists the account lookup must use it exclusively, ensuring.

    that renaming the display_name in the provider cannot redirect a login to a different account.

    """
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="Bob Smith", label="Bob Smith", account_type="User", password=str(uuid.uuid4()))
    await account.save(db=db)

    identity_node = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity_node.new(
        db=db, sub="sub-returning-001", provider_name="provider1", protocol="oidc", account=account.id
    )
    await identity_node.save(db=db)

    identity = ExternalIdentity(
        sub="sub-returning-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Bob Smith",
        email="bob@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    assert auth_result.token.access_token

    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Bob Smith"})
    assert len(accounts) == 1

    identity_nodes = await NodeManager.query(
        db=db, schema=InfrahubKind.EXTERNALIDENTITY, filters={"sub__value": "sub-returning-001"}
    )
    assert len(identity_nodes) == 1


async def test_label_is_updated_when_display_name_changes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The label is the human-readable name shown in the UI.

    When the provider changes
    the display name the label must follow so that the UI stays consistent with the IdP.

    """
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="Carol Jones", label="Carol Jones", account_type="User", password=str(uuid.uuid4()))
    await account.save(db=db)

    identity_node = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity_node.new(db=db, sub="sub-label-001", provider_name="provider1", protocol="oidc", account=account.id)
    await identity_node.save(db=db)

    identity = ExternalIdentity(
        sub="sub-label-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Carol J.",
        email="carol@example.com",
    )

    await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    updated_account = await NodeManager.get_one(db=db, id=account.id)
    assert updated_account.label.value == "Carol J."

    identity_nodes = await NodeManager.query(
        db=db, schema=InfrahubKind.EXTERNALIDENTITY, filters={"sub__value": "sub-label-001"}
    )
    assert len(identity_nodes) == 1


async def test_transition_fallback_unclaimed_account_is_linked(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Accounts created before this feature was introduced have no identity node.

    The first
    post-upgrade login must claim the existing account rather than creating a duplicate,
    preserving the user's history, permissions, and group memberships.

    """
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="Eve Turner", account_type="User", password=str(uuid.uuid4()))
    await account.save(db=db)

    identity = ExternalIdentity(
        sub="sub-transition-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Eve Turner",
        email="eve@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    assert auth_result.token.access_token

    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Eve Turner"})
    assert len(accounts) == 1

    identity_nodes = await NodeManager.query(
        db=db,
        schema=InfrahubKind.EXTERNALIDENTITY,
        filters={"sub__value": "sub-transition-001", "account__ids": [account.id]},
    )
    assert len(identity_nodes) == 1


async def test_transition_fallback_claimed_account_uses_email_as_name(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """If a name-matched account is already linked to a different provider identity it cannot.

    be claimed. A new account must be created using the email as the unique name so that both
    users can log in without either being locked out or silently redirected to the wrong account.

    """
    existing_account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await existing_account.new(db=db, name="Frank Hall", account_type="User", password=str(uuid.uuid4()))
    await existing_account.save(db=db)

    other_identity = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await other_identity.new(
        db=db, sub="sub-other-001", provider_name="provider1", protocol="oidc", account=existing_account.id
    )
    await other_identity.save(db=db)

    identity = ExternalIdentity(
        sub="sub-collision-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Frank Hall",
        email="frank@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    assert auth_result.token.access_token

    new_accounts = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "frank@example.com"}
    )
    assert len(new_accounts) == 1
    assert new_accounts[0].label.value == "Frank Hall"

    original_accounts = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Frank Hall"}
    )
    assert len(original_accounts) == 1
    assert original_accounts[0].id == existing_account.id


async def test_name_and_email_collision_raises_processing_error(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """When both the display name and the email are already taken by other accounts there is no.

    safe automatic resolution. A hard error forces an admin to intervene rather than silently
    dropping the login or overwriting someone else's account.

    """
    account1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account1.new(db=db, name="Grace Lee", account_type="User", password=str(uuid.uuid4()))
    await account1.save(db=db)

    identity1 = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity1.new(db=db, sub="sub-other-002", provider_name="provider1", protocol="oidc", account=account1.id)
    await identity1.save(db=db)

    account2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account2.new(db=db, name="grace@example.com", account_type="User", password=str(uuid.uuid4()))
    await account2.save(db=db)

    identity = ExternalIdentity(
        sub="sub-both-taken-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Grace Lee",
        email="grace@example.com",
    )

    with pytest.raises(ProcessingError):
        await signin_sso_account(db=db, external_identity=identity, sso_groups=[])


async def test_name_fallback_disabled_does_not_claim_unclaimed_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    sso_account_name_fallback_disabled: None,
) -> None:
    """When the name fallback is disabled an SSO login must never adopt a pre-existing account.

    A separate account, keyed by the email, is created instead so a controlled display name
    cannot be used to claim a never-yet-linked account.

    """
    existing_account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await existing_account.new(db=db, name="Mona West", account_type="User", password=str(uuid.uuid4()))
    await existing_account.save(db=db)

    identity = ExternalIdentity(
        sub="sub-nofallback-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Mona West",
        email="mona@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=[])

    assert auth_result.token.access_token

    new_accounts = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "mona@example.com"}
    )
    assert len(new_accounts) == 1
    assert new_accounts[0].label.value == "Mona West"
    assert new_accounts[0].id != existing_account.id

    original = await NodeManager.get_one(db=db, id=existing_account.id)
    original_identities = await NodeManager.query(
        db=db, schema=InfrahubKind.EXTERNALIDENTITY, filters={"account__ids": [existing_account.id]}
    )
    assert original.name.value == "Mona West"
    assert len(original_identities) == 0

    new_identities = await NodeManager.query(
        db=db,
        schema=InfrahubKind.EXTERNALIDENTITY,
        filters={"sub__value": "sub-nofallback-001", "account__ids": [new_accounts[0].id]},
    )
    assert len(new_identities) == 1


async def test_name_fallback_disabled_both_names_taken_raises(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    sso_account_name_fallback_disabled: None,
) -> None:
    """With the fallback disabled a display-name match is not adopted, so a separate account is.

    provisioned under the email instead. When the email is also already taken as an account name
    there is no unique name left to use, so the login fails rather than guessing.

    """
    account_by_name = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account_by_name.new(db=db, name="Nora Park", account_type="User", password=str(uuid.uuid4()))
    await account_by_name.save(db=db)

    account_by_email = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account_by_email.new(db=db, name="nora@example.com", account_type="User", password=str(uuid.uuid4()))
    await account_by_email.save(db=db)

    identity = ExternalIdentity(
        sub="sub-nofallback-002",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Nora Park",
        email="nora@example.com",
    )

    with pytest.raises(ProcessingError, match=r"already in use as account names"):
        await signin_sso_account(db=db, external_identity=identity, sso_groups=[])


async def test_account_is_added_to_matching_group(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Group membership is the mechanism for assigning permissions in Infrahub.

    SSO group claims
    must be reflected at login so that access rights stay in sync with the IdP without requiring
    manual admin intervention after each user is provisioned.

    """
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="network-engineers-001")
    await group.save(db=db)

    identity = ExternalIdentity(
        sub="sub-group-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Hank Brown",
        email="hank@example.com",
    )

    await signin_sso_account(db=db, external_identity=identity, sso_groups=["network-engineers-001"])

    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Hank Brown"})
    assert len(accounts) == 1
    account = accounts[0]

    refreshed_group = await NodeManager.get_one(db=db, id=group.id, prefetch_relationships=True)
    members = await refreshed_group.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
    assert account.id in members


async def test_account_already_in_group_is_not_duplicated(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Group membership relationships must be idempotent.

    A second login with the same group
    claims must not create a duplicate edge, which would corrupt membership counts and
    potentially cause permission evaluation to behave unpredictably.

    """
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="network-engineers-002")
    await group.save(db=db)

    identity = ExternalIdentity(
        sub="sub-dedup-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Ivy Clark",
        email="ivy@example.com",
    )

    await signin_sso_account(db=db, external_identity=identity, sso_groups=["network-engineers-002"])
    await signin_sso_account(db=db, external_identity=identity, sso_groups=["network-engineers-002"])

    refreshed_group = await NodeManager.get_one(db=db, id=group.id, prefetch_relationships=True)
    members = await refreshed_group.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
    assert len(members) == 1


async def test_unknown_group_is_silently_ignored(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The IdP may send group names that have not yet been created in Infrahub.

    Failing the
    login in that case would lock users out for a misconfiguration that is outside their
    control, so unknown groups are skipped and the login proceeds.

    """
    identity = ExternalIdentity(
        sub="sub-nogroup-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Jake Davis",
        email="jake@example.com",
    )

    auth_result = await signin_sso_account(db=db, external_identity=identity, sso_groups=["nonexistent-group"])

    assert auth_result.token.access_token

    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Jake Davis"})
    assert len(accounts) == 1


async def test_two_different_identities_produce_two_accounts(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Each unique (sub, provider, protocol) triple must map to its own account.

    This guards
    against a regression where a shared attribute — such as a common display name — would
    cause two distinct users to be merged into one account.

    """
    identity1 = ExternalIdentity(
        sub="sub-two-001",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Kate Evans",
        email="kate@example.com",
    )
    identity2 = ExternalIdentity(
        sub="sub-two-002",
        provider_name="provider1",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Liam Foster",
        email="liam@example.com",
    )

    await signin_sso_account(db=db, external_identity=identity1, sso_groups=[])
    await signin_sso_account(db=db, external_identity=identity2, sso_groups=[])

    for name, sub in [("Kate Evans", "sub-two-001"), ("Liam Foster", "sub-two-002")]:
        accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": name})
        assert len(accounts) == 1

        identity_nodes = await NodeManager.query(
            db=db, schema=InfrahubKind.EXTERNALIDENTITY, filters={"sub__value": sub}
        )
        assert len(identity_nodes) == 1

        linked = await identity_nodes[0].account.get_peer(db=db)
        assert linked.id == accounts[0].id
