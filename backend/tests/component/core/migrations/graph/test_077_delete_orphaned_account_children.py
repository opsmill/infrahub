import uuid

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m077_delete_orphaned_account_children import Migration077
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def _create_account_with_children(db: InfrahubDatabase, name: str, sub: str) -> tuple[Node, Node, Node]:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, account_type="User", password=str(uuid.uuid4()))
    await account.save(db=db)

    identity = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity.new(db=db, sub=sub, provider_name="provider1", protocol="oidc", account=account.id)
    await identity.save(db=db)

    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token=f"token-{sub}", account=account.id)
    await token.save(db=db)

    return account, identity, token


async def _existing_ids(db: InfrahubDatabase, kind: str) -> set[str]:
    return {node.get_id() for node in await NodeManager.query(db=db, schema=kind)}


async def test_migration_077(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The children of a deleted account are removed, the children of a live account are kept."""
    deleted_account, orphaned_identity, orphaned_token = await _create_account_with_children(
        db=db, name="Deleted User", sub="sub-orphan-001"
    )
    live_account, live_identity, live_token = await _create_account_with_children(
        db=db, name="Live User", sub="sub-live-001"
    )

    # Reproduce what an account delete used to leave behind: the account gone, its children not.
    await deleted_account.delete(db=db)
    assert await _existing_ids(db=db, kind=InfrahubKind.EXTERNALIDENTITY) == {
        orphaned_identity.get_id(),
        live_identity.get_id(),
    }

    migration = Migration077()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    assert await _existing_ids(db=db, kind=InfrahubKind.EXTERNALIDENTITY) == {live_identity.get_id()}
    assert await _existing_ids(db=db, kind=InfrahubKind.ACCOUNTTOKEN) == {live_token.get_id()}
    assert await _existing_ids(db=db, kind=InfrahubKind.ACCOUNT) == {live_account.get_id()}
    assert orphaned_token.get_id() not in await _existing_ids(db=db, kind=InfrahubKind.ACCOUNTTOKEN)

    # The live account keeps a usable link to its own children.
    reloaded_identity = await NodeManager.get_one(db=db, id=live_identity.get_id(), raise_on_error=True)
    linked_account = await reloaded_identity.get_relationship(name="account").get_peer(db=db)
    assert linked_account is not None
    assert linked_account.get_id() == live_account.get_id()

    # Running it again has nothing left to do and must not touch the survivors.
    second_result = await Migration077().execute(migration_input=MigrationInput(db=db))
    assert not second_result.errors
    assert await _existing_ids(db=db, kind=InfrahubKind.EXTERNALIDENTITY) == {live_identity.get_id()}
    assert await _existing_ids(db=db, kind=InfrahubKind.ACCOUNTTOKEN) == {live_token.get_id()}


async def test_migration_077_no_orphans(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """With every account still in place, nothing is deleted."""
    account, identity, token = await _create_account_with_children(db=db, name="Kept User", sub="sub-kept-001")

    execution_result = await Migration077().execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    assert await _existing_ids(db=db, kind=InfrahubKind.EXTERNALIDENTITY) == {identity.get_id()}
    assert await _existing_ids(db=db, kind=InfrahubKind.ACCOUNTTOKEN) == {token.get_id()}
    assert await _existing_ids(db=db, kind=InfrahubKind.ACCOUNT) == {account.get_id()}
