from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress

from infrahub.core import registry
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationResult
from infrahub.lock import initialize_lock

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class Migration042(ArbitraryMigration):
    """
    Backfill `human_friendly_id` and `display_label` attributes for nodes with schemas that define them.
    """

    name: str = "042_backfill_hfid_display_label_in_db"
    minimum_version: int = 41

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _create_hfids_for_kind(
        self, db: InfrahubDatabase, node_schema: MainSchemaTypes, nodes: list[Node]
    ) -> None:
        if not node_schema.human_friendly_id:
            return

        with Progress() as progress:
            update_hfid_task = progress.add_task(
                f"Creating {len(nodes)} HFIDs in database for {node_schema.kind}", total=len(nodes)
            )
            for node in nodes:
                await node.add_human_friendly_id(db=db)
                await node.save(db=db, fields=["human_friendly_id"])
                progress.update(update_hfid_task, advance=1)

    async def _create_display_labels_for_kind(
        self, db: InfrahubDatabase, node_schema: MainSchemaTypes, nodes: list[Node]
    ) -> None:
        if not node_schema.display_label:
            return

        with Progress() as progress:
            update_display_label_task = progress.add_task(
                f"Creating {len(nodes)} display labels in database for {node_schema.kind}", total=len(nodes)
            )
            for node in nodes:
                await node.add_display_label(db=db)
                await node.save(db=db, fields=["display_label"])
                progress.update(update_display_label_task, advance=1)

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        for node_schema in registry.get_full_schema(duplicate=False).values():
            if node_schema.is_generic_schema:
                continue

            nodes: list[Node] = await NodeManager.query(db=db, schema=node_schema)
            if not nodes:
                continue

            await self._create_hfids_for_kind(db=db, node_schema=node_schema, nodes=nodes)
            await self._create_display_labels_for_kind(db=db, node_schema=node_schema, nodes=nodes)

        return result
