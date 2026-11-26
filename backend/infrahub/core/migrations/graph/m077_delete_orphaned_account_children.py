from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

ORPHANED_KINDS: dict[str, str] = {
    InfrahubKind.EXTERNALIDENTITY: "account__external_identity",
    InfrahubKind.ACCOUNTTOKEN: "account__token",
    InfrahubKind.REFRESHTOKEN: "account__refreshtoken",
}

# Every kind here is branch-agnostic, so every edge of theirs lives on the global branch.
ACTIVE_NODES_WITHOUT_ACCOUNT = """
MATCH (node:Node)-[part_of:IS_PART_OF]->(root:Root)
WHERE node.kind = $kind AND part_of.branch = $global_branch AND part_of.from <= $at
WITH node, root, part_of
  ORDER BY part_of.from DESC, part_of.status ASC
WITH node, root, head(collect(part_of)) AS latest_edge
WHERE latest_edge.status = "active" AND latest_edge.to IS NULL

// A closed edge keeps status "active" and gains a "to", so both have to be checked.
// One subquery per node is enough only because these kinds are branch-agnostic: a node and its
// account cannot carry different statuses on different branches. If they could, this would need
// one subquery per node and account pair.
CALL (node) {
    MATCH (node)-[r1:IS_RELATED]-(:Relationship { name: $relationship })
          -[r2:IS_RELATED]-(account:%(generic_account)s)-[account_part_of:IS_PART_OF]->(:Root)
    WITH r1, r2, account_part_of
      ORDER BY r1.from DESC, r1.status ASC,
               r2.from DESC, r2.status ASC,
               account_part_of.from DESC, account_part_of.status ASC
    WITH head(collect([
        r1.status = "active" AND r1.to IS NULL,
        r2.status = "active" AND r2.to IS NULL,
        account_part_of.status = "active" AND account_part_of.to IS NULL
    ])) AS live_edges
    WHERE live_edges = [true, true, true]
    RETURN count(*) AS live_accounts
}
WITH node, root, latest_edge, live_accounts
WHERE live_accounts = 0
"""


class OrphanedAccountChildrenQuery(Query):
    name: str = "orphaned_account_children"
    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(self, kind: str, relationship: str, **kwargs: Any) -> None:
        self.kind = kind
        self.relationship = relationship
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["kind"] = self.kind
        self.params["relationship"] = self.relationship
        self.params["global_branch"] = GLOBAL_BRANCH_NAME
        self.params["at"] = self.at.to_string()
        self.add_to_query(ACTIVE_NODES_WITHOUT_ACCOUNT % {"generic_account": InfrahubKind.GENERICACCOUNT})
        self.add_to_query("RETURN node.uuid AS uuid ORDER BY uuid")
        self.return_labels = ["uuid"]

    def get_uuids(self) -> list[str]:
        return [result.get_as_type(label="uuid", return_type=str) for result in self.get_results()]


class DeleteOrphanedAccountChildrenQuery(Query):
    """Close every active edge of the orphaned nodes and record the delete on the node itself."""

    name: str = "delete_orphaned_account_children"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(self, kind: str, relationship: str, user_id: str, **kwargs: Any) -> None:
        self.kind = kind
        self.relationship = relationship
        self.user_id = user_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["kind"] = self.kind
        self.params["relationship"] = self.relationship
        self.params["global_branch"] = GLOBAL_BRANCH_NAME
        self.params["user_id"] = self.user_id
        self.params["at"] = self.at.to_string()

        self.add_to_query(ACTIVE_NODES_WITHOUT_ACCOUNT % {"generic_account": InfrahubKind.GENERICACCOUNT})
        self.add_to_query("""
CREATE (node)-[:IS_PART_OF {
    branch: latest_edge.branch,
    branch_level: latest_edge.branch_level,
    status: "deleted",
    from: $at,
    from_user_id: $user_id
}]->(root)
SET latest_edge.to = $at, latest_edge.to_user_id = $user_id

WITH node
OPTIONAL MATCH (node)-[field_edge:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE field_edge.branch = $global_branch AND field_edge.from <= $at
  AND field_edge.status = "active" AND field_edge.to IS NULL
CALL (field_edge) {
    SET field_edge.to = $at, field_edge.to_user_id = $user_id
}

WITH node, field
OPTIONAL MATCH (field)-[property_edge]-()
WHERE property_edge.branch = $global_branch AND property_edge.from <= $at
  AND property_edge.status = "active" AND property_edge.to IS NULL
CALL (property_edge) {
    SET property_edge.to = $at, property_edge.to_user_id = $user_id
}
RETURN DISTINCT node.uuid AS uuid
ORDER BY uuid
        """)
        self.return_labels = ["uuid"]

    def get_uuids(self) -> list[str]:
        return [result.get_as_type(label="uuid", return_type=str) for result in self.get_results()]


class Migration077(ArbitraryMigration):
    """Delete the external identities, the API tokens and the refresh tokens whose account is gone.

    Deleting an account used to leave them behind, each with an account relationship that no longer
    resolves. A surviving external identity keeps matching the SSO login of the provider user, which
    locked that user out: the login found the identity, found no account behind it, and failed.
    """

    name: str = "077_delete_orphaned_account_children"
    description: str = "Delete external identities, API tokens and refresh tokens whose account no longer exists."
    minimum_version: int = 76

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        for kind, relationship in ORPHANED_KINDS.items():
            query = await OrphanedAccountChildrenQuery.init(db=db, kind=kind, relationship=relationship)
            await query.execute(db=db)
            remaining = query.get_uuids()
            if remaining:
                result.errors.append(f"{len(remaining)} {kind} node(s) still have no account: {remaining}")
        return result

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        for kind, relationship in ORPHANED_KINDS.items():
            try:
                query = await DeleteOrphanedAccountChildrenQuery.init(
                    db=db,
                    kind=kind,
                    relationship=relationship,
                    user_id=migration_input.user_id,
                    at=migration_input.at,
                )
                await query.execute(db=db)
            # A per-kind failure becomes a reported migration error instead of aborting the run.
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"Unable to delete the {kind} nodes with no account: {exc}")
                continue

            deleted = query.get_uuids()
            if deleted:
                console.log(f"Deleted {len(deleted)} {kind} node(s) with no account.")

        return result
