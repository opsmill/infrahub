from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from rich.progress import Progress, TaskID

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

    async def _update_batch(
        self,
        db: InfrahubDatabase,
        node_schema: MainSchemaTypes,
        nodes: Sequence[Node],
        progress: Progress,
        update_task: TaskID,
    ) -> None:
        for node in nodes:
            fields = []
            if node_schema.human_friendly_id:
                await node.add_human_friendly_id(db=db)
                fields.append("human_friendly_id")
            if node_schema.display_label:
                await node.add_display_label(db=db)
                fields.append("display_label")

            if fields:
                await node.save(db=db, fields=fields)

            progress.update(task_id=update_task, advance=1)

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        schemas_to_update: dict[MainSchemaTypes, int] = {}
        for node_schema in registry.get_full_schema(duplicate=False).values():
            if node_schema.is_generic_schema or (not node_schema.human_friendly_id and not node_schema.display_label):
                continue

            node_count = await NodeManager.count(db=db, schema=node_schema)
            if node_count:
                schemas_to_update[node_schema] = node_count

        with Progress() as progress:
            batch_size = 1000
            update_task = progress.add_task(
                "Backfill HFID and display_label for nodes in database", total=sum(schemas_to_update.values())
            )

            for schema, count in schemas_to_update.items():
                for offset in range(0, count, batch_size):
                    limit = min(batch_size, count - offset)
                    nodes: list[Node] = await NodeManager.query(db=db, schema=schema, offset=offset, limit=limit)
                    await self._update_batch(
                        db=db, node_schema=schema, nodes=nodes, progress=progress, update_task=update_task
                    )

        return result
