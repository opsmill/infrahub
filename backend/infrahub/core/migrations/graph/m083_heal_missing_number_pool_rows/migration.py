from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.migrations.graph.missing_attribute_rows.migration_base import MissingAttributeRowsMigration
from infrahub.core.migrations.graph.missing_attribute_rows.repairers import PoolBackedRowRepairer
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.migrations.graph.missing_attribute_rows.repairers import MissingRowRepairer
    from infrahub.database import InfrahubDatabase


class Migration083(MissingAttributeRowsMigration):
    """Backfill missing generic-inherited number pool attribute rows on active nodes.

    In earlier versions, adding a generic to an existing kind did not create rows
    for the newly inherited attributes on the kind's pre-existing nodes. The rows
    carrying a schema default are backfilled by an earlier migration; the rows a
    number pool has to fill are backfilled here, once every pool holds the ranges
    it allocates from and every reservation record sits where allocation reads it.
    Each damaged (active node, inherited attribute) pair gets an active row with a
    fresh reservation-aware allocation from the attribute's pool, which is upserted
    when missing.
    """

    name: str = "083_heal_missing_number_pool_rows"
    description: str = (
        "Backfill number pool attribute rows that earlier versions failed to create when an "
        "existing kind started inheriting a number pool attribute from a generic"
    )
    minimum_version: int = 82

    def _repairers(self, db: InfrahubDatabase, console: Console) -> list[MissingRowRepairer]:
        upserter = SchemaNumberPoolUpserter(
            db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
        )
        return [PoolBackedRowRepairer(db=db, console=console, batch_size=self.repair_batch_size, upserter=upserter)]
