from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
)
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


# Kinds whose schema now defaults group_type to "internal". All are LOCAL or AWARE,
# so their attribute edges carry the writing branch's name.
INTERNAL_GROUP_KINDS = [
    "CoreGeneratorGroup",
    "CoreGeneratorAwareGroup",
    "CoreGraphQLQueryGroup",
    "CoreRepositoryGroup",
]


class Migration072Query01(Query):
    """Flip group_type from 'default' to 'internal' on existing system-managed group instances.

    The schema now defaults group_type to 'internal' for these kinds, but existing instances
    created before the schema change still carry 'default' and would leak into user-facing
    'add to group' selectors that filter on group_type.
    """

    name = "migration_072_01"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()

        query = """
MATCH (n:Node)
WHERE any(label IN labels(n) WHERE label IN $kinds)
MATCH p = (n)-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "group_type"})-[hv:HAS_VALUE]->(:AttributeValue {value: "default"})
WHERE all(r IN relationships(p) WHERE r.status = "active" AND r.to IS NULL AND r.branch IN $branch_names)

// close the edge to the 'default' value on the targeted branches
SET hv.to = $at

// reuse or create the 'internal' value node
MERGE (new_value:AttributeValue:AttributeValueIndexed {value: "internal", is_default: true})

// link each affected attribute to the 'internal' value, preserving branch metadata from the matched edge
CREATE (attr)-[new_hv:HAS_VALUE]->(new_value)
SET new_hv = properties(hv)
SET new_hv.from = $at, new_hv.to = NULL
        """
        self.add_to_query(query)


class Migration072(MigrationRequiringRebase):
    name: str = "072_internal_group_type_on_system_kinds"
    minimum_version: int = 71

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _run(
        self,
        db: InfrahubDatabase,
        at: Timestamp,
        branch_names: list[str],
    ) -> MigrationResult:
        try:
            query = await Migration072Query01.init(db=db, at=at)
            query.params["branch_names"] = branch_names
            query.params["kinds"] = INTERNAL_GROUP_KINDS
            await query.execute(db=db)
        except Exception as exc:
            return MigrationResult(errors=[str(exc) or f"{type(exc).__name__}: {exc!r}"])
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        """Default-branch pass."""
        return await self._run(
            db=migration_input.db,
            at=migration_input.at,
            branch_names=[registry.default_branch],
        )

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        """Per-branch pass; the rebase framework calls this once per non-default branch."""
        return await self._run(
            db=migration_input.db,
            at=migration_input.at,
            branch_names=[branch.name],
        )
