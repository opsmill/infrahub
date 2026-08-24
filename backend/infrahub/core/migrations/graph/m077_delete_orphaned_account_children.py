from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.exceptions import NodeNotFoundError

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

BATCH_SIZE = 100

ORPHANED_KINDS = (InfrahubKind.EXTERNALIDENTITY, InfrahubKind.ACCOUNTTOKEN)


class Migration077(ArbitraryMigration):
    """Delete the external identities and the API tokens whose account is gone.

    Deleting an account used to leave them behind, each with an account relationship that no longer
    resolves. A surviving external identity keeps matching the SSO login of the provider user, which
    locked that user out: the login found the identity, found no account behind it, and failed.
    """

    name: str = "077_delete_orphaned_account_children"
    description: str = "Delete external identities and API tokens whose account no longer exists."
    minimum_version: int = 76

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        try:
            root_node = await get_root_node(db=db, initialize=False)
            default_branch = await Branch.get_by_name(db=db, name=root_node.default_branch)
            await get_or_load_schema_branch(db=db, branch=default_branch)
        except Exception as exc:
            return MigrationResult(errors=[f"Unable to load the schema of the default branch: {exc}"])

        for kind in ORPHANED_KINDS:
            try:
                orphans = await self._collect_orphans(db=db, branch=default_branch, kind=kind)
            except Exception as exc:
                result.errors.append(f"Unable to look up {kind} nodes: {exc}")
                continue

            if not orphans:
                continue

            console.log(f"Found {len(orphans)} {kind} node(s) with no account, deleting them...")
            for orphan in orphans:
                try:
                    await orphan.delete(db=db)
                except Exception as exc:
                    result.errors.append(f"{kind} '{orphan.get_id()}' could not be deleted: {exc}")

        return result

    async def _collect_orphans(self, db: InfrahubDatabase, branch: Branch, kind: str) -> list[Node]:
        """Collect every node of that kind whose account relationship resolves to nothing.

        The whole set is read before anything is deleted, because deleting during the walk would
        shift the pages that are still to be read.
        """
        orphans: list[Node] = []
        offset = 0
        while True:
            nodes = await NodeManager.query(db=db, schema=kind, branch=branch, offset=offset, limit=BATCH_SIZE)
            if not nodes:
                return orphans
            offset += len(nodes)
            for node in nodes:
                if await self._account_is_missing(db=db, node=node):
                    orphans.append(node)

    async def _account_is_missing(self, db: InfrahubDatabase, node: Node) -> bool:
        try:
            return await node.get_relationship(name="account").get_peer(db=db) is None
        except NodeNotFoundError:
            return True
