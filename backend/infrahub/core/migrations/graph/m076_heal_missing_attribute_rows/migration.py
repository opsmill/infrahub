from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.migrations.graph.missing_attribute_rows.migration_base import MissingAttributeRowsMigration
from infrahub.core.migrations.graph.missing_attribute_rows.repairers import DefaultValueRowRepairer

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.migrations.graph.missing_attribute_rows.repairers import MissingRowRepairer
    from infrahub.database import InfrahubDatabase


class Migration076(MissingAttributeRowsMigration):
    """Backfill missing generic-inherited attribute rows on active nodes.

    In earlier versions, adding a generic to an existing kind did not create rows
    for the newly inherited attributes on the kind's pre-existing nodes, leaving
    active nodes without rows their schema requires. Every damaged (active node,
    inherited attribute) pair gets an active row created at migration run time,
    carrying the schema default (a null value when the attribute has none).

    Pool-backed attributes are left to the migration that runs once the number
    pool ranges and reservation records have been migrated: allocating before
    then would not see the numbers already handed out.
    """

    name: str = "076_heal_missing_attribute_rows"
    description: str = (
        "Backfill attribute rows that earlier versions failed to create when an "
        "existing kind started inheriting attributes from a generic"
    )
    minimum_version: int = 75

    def _repairers(self, db: InfrahubDatabase, console: Console) -> list[MissingRowRepairer]:
        return [DefaultValueRowRepairer(db=db, console=console, batch_size=self.repair_batch_size)]
