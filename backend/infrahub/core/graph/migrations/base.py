from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


class MigrationResult(BaseModel):
    errors: List[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        if not self.errors:
            return True

        return False


class InfrahubMigration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    queries: Sequence[type[Query]] = Field(..., description="List of queries to execute for this migration")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()

            for migration_query in self.queries:
                try:
                    query = await migration_query.init(db=ts)
                    await query.execute(db=ts)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    result.errors.append(str(exc))
                    return result

        return result
