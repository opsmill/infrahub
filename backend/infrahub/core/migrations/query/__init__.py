from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import QueryType

from .selection import MigrationSelectionQuery

if TYPE_CHECKING:
    from ..shared import AttributeSchemaMigration, SchemaMigration


class MigrationBaseQuery(MigrationSelectionQuery):
    def get_nbr_migrations_executed(self) -> int:
        return self.num_of_results


class MigrationQuery(MigrationBaseQuery):
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        migration: SchemaMigration,
        **kwargs: Any,
    ) -> None:
        self.migration = migration
        super().__init__(**kwargs)


class AttributeMigrationQuery(MigrationBaseQuery):
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        self.migration = migration
        super().__init__(**kwargs)
