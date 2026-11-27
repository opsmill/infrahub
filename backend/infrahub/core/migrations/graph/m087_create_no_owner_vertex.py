from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.core.ownership.queries import NoOwnerVertexCreateQuery
from infrahub.core.query import Query  # noqa: TC001  needed for pydantic

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration087(GraphMigration):
    """Create the `NoOwner` vertex before any write, so that two writes at the same time cannot each create one."""

    name: str = "087_create_no_owner_vertex"
    description: str = "Create the vertex that marks a node, an attribute or a relationship as having no owner"
    minimum_version: int = 86
    queries: Sequence[type[Query]] = [NoOwnerVertexCreateQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
