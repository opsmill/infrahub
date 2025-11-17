from __future__ import annotations

from typing import TYPE_CHECKING

from rich.progress import Progress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.graph.m044_backfill_hfid_display_label_in_db import DefaultBranchNodeCount, Migration044
from infrahub.core.migrations.shared import MigrationResult, get_migration_console
from infrahub.exceptions import SchemaNotFoundError

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import ProfileSchema, TemplateSchema
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


class Migration045(Migration044):
    """
    Backfill `human_friendly_id` and `display_label` attributes for profile and template nodes with schemas that define them.
    """

    name: str = "045_backfill_hfid_display_label_in_db_profile_template"
    minimum_version: int = 44
    update_batch_size: int = 1000

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        kinds_to_skip = self.kinds_to_skip + main_schema_branch.node_names

        total_nodes_query = await DefaultBranchNodeCount.init(db=db, kinds_to_skip=kinds_to_skip)
        await total_nodes_query.execute(db=db)
        total_nodes_count = total_nodes_query.get_num_nodes()

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            with Progress(console=console) as progress:
                update_task = progress.add_task(
                    f"Set display_label and human_friendly_id for {total_nodes_count} nodes on default branch",
                    total=total_nodes_count,
                )
                for node_schema_name in main_schema_branch.profile_names + main_schema_branch.template_names:
                    if node_schema_name in self.kinds_to_skip:
                        continue

                    node_schema: ProfileSchema | TemplateSchema
                    if node_schema_name in main_schema_branch.profile_names:
                        node_schema = main_schema_branch.get_profile(name=node_schema_name, duplicate=False)
                    else:
                        node_schema = main_schema_branch.get_template(name=node_schema_name, duplicate=False)

                    attribute_schema_map = {}
                    if node_schema.display_labels:
                        attribute_schema_map[display_labels_attribute_schema] = display_label_attribute_schema
                    if node_schema.human_friendly_id:
                        attribute_schema_map[hfid_attribute_schema] = hfid_attribute_schema
                    if not attribute_schema_map:
                        continue

                    await self._do_one_schema_all(
                        db=db,
                        branch=default_branch,
                        schema=node_schema,
                        schema_branch=main_schema_branch,
                        attribute_schema_map=attribute_schema_map,
                        progress=progress,
                        update_task=update_task,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        default_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            for node_schema_name in schema_branch.profile_names + schema_branch.template_names:
                if node_schema_name in self.kinds_to_skip:
                    continue

                node_schema: ProfileSchema | TemplateSchema
                default_node_schema: ProfileSchema | TemplateSchema | None
                if node_schema_name in schema_branch.profile_names:
                    node_schema = schema_branch.get_profile(name=node_schema_name, duplicate=False)
                    try:
                        default_node_schema = main_schema_branch.get_profile(name=node_schema_name, duplicate=False)
                    except SchemaNotFoundError:
                        default_node_schema = None
                else:
                    node_schema = schema_branch.get_template(name=node_schema_name, duplicate=False)
                    try:
                        default_node_schema = main_schema_branch.get_template(name=node_schema_name, duplicate=False)
                    except SchemaNotFoundError:
                        default_node_schema = None

                schemas_for_universal_update_map = {}
                schemas_for_targeted_update_map = {}
                if node_schema.display_labels:
                    if default_node_schema is None or default_node_schema.display_label != node_schema.display_label:
                        schemas_for_universal_update_map[display_labels_attribute_schema] = (
                            display_label_attribute_schema
                        )
                    else:
                        schemas_for_targeted_update_map[display_labels_attribute_schema] = (
                            display_label_attribute_schema
                        )

                if node_schema.human_friendly_id:
                    if (
                        default_node_schema is None
                        or default_node_schema.human_friendly_id != node_schema.human_friendly_id
                    ):
                        schemas_for_universal_update_map[hfid_attribute_schema] = hfid_attribute_schema
                    else:
                        schemas_for_targeted_update_map[hfid_attribute_schema] = hfid_attribute_schema

                if schemas_for_universal_update_map:
                    await self._do_one_schema_all(
                        db=db,
                        branch=branch,
                        schema=node_schema,
                        schema_branch=schema_branch,
                        attribute_schema_map=schemas_for_universal_update_map,
                    )

                if not schemas_for_targeted_update_map:
                    continue

                for source_attribute_schema, destination_attribute_schema in schemas_for_targeted_update_map.items():
                    await self._do_one_schema_branch(
                        db=db,
                        branch=branch,
                        schema=node_schema,
                        schema_branch=schema_branch,
                        source_attribute_schema=source_attribute_schema,
                        destination_attribute_schema=destination_attribute_schema,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
