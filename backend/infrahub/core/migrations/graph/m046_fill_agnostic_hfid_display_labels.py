from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Any

import ujson
from rich.progress import Progress, TaskID

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, SchemaPathType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.graph.m044_backfill_hfid_display_label_in_db import (
    DefaultBranchNodeCount,
    GetPathDetailsDefaultBranch,
    GetResultMapQuery,
    UpdateAttributeValuesQuery,
)
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationResult, get_migration_console
from infrahub.core.path import SchemaPath
from infrahub.core.query import Query, QueryType

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes, NodeSchema, SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class DeleteBranchAwareAttrsForBranchAgnosticNodesQuery(Query):
    name = "delete_branch_aware_attrs_for_branch_agnostic_nodes_query"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (n:Node {branch_support: "agnostic"})
MATCH (n)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name IN ["human_friendly_id", "display_label"]
WITH DISTINCT attr
CALL (attr) {
    DETACH DELETE attr
} IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration046(ArbitraryMigration):
    """
    Delete any branch-aware human_friendly_id and display_label attributes added to branch-agnostic nodes
    Add human_friendly_id and display_label attributes to branch-agnostic nodes
    Set human_friendly_id and display_label attributes for branch-agnostic nodes on global branch

    Uses and duplicates code from Migration044
    """

    name: str = "046_fill_agnostic_hfid_display_labels"
    minimum_version: int = 45
    update_batch_size: int = 1000

    async def _do_one_schema_all(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: MainSchemaTypes,
        schema_branch: SchemaBranch,
        attribute_schema_map: dict[AttributeSchema, AttributeSchema],
        progress: Progress | None = None,
        update_task: TaskID | None = None,
    ) -> None:
        print(f"Processing {schema.kind}...", end="")

        schema_paths_by_name: dict[str, list[SchemaAttributePath]] = {}
        for source_attribute_schema in attribute_schema_map.keys():
            node_schema_property = getattr(schema, source_attribute_schema.name)
            if not node_schema_property:
                continue
            if isinstance(node_schema_property, list):
                schema_paths_by_name[source_attribute_schema.name] = [
                    schema.parse_schema_path(path=str(path), schema=schema_branch) for path in node_schema_property
                ]
            else:
                schema_paths_by_name[source_attribute_schema.name] = [
                    schema.parse_schema_path(path=str(node_schema_property), schema=schema_branch)
                ]
        all_schema_paths = list(chain(*schema_paths_by_name.values()))
        offset = 0

        # loop until we get no results from the get_details_query
        while True:
            get_details_query: GetResultMapQuery = await GetPathDetailsDefaultBranch.init(
                db=db,
                schema_kind=schema.kind,
                schema_paths=all_schema_paths,
                offset=offset,
                limit=self.update_batch_size,
            )
            await get_details_query.execute(db=db)

            num_updates = 0
            for source_attribute_schema, destination_attribute_schema in attribute_schema_map.items():
                schema_paths = schema_paths_by_name[source_attribute_schema.name]
                schema_path_values_map = get_details_query.get_result_map(schema_paths)
                num_updates = max(num_updates, len(schema_path_values_map))
                formatted_schema_path_values_map = {}
                for k, v in schema_path_values_map.items():
                    if not v:
                        continue
                    if destination_attribute_schema.kind == "List":
                        formatted_schema_path_values_map[k] = ujson.dumps(v)
                    else:
                        formatted_schema_path_values_map[k] = " ".join(item for item in v if item is not None)

                if not formatted_schema_path_values_map:
                    continue

                update_display_label_query = await UpdateAttributeValuesQuery.init(
                    db=db,
                    branch=branch,
                    attribute_schema=destination_attribute_schema,
                    values_by_id_map=formatted_schema_path_values_map,
                )
                await update_display_label_query.execute(db=db)

            if progress is not None and update_task is not None:
                progress.update(update_task, advance=num_updates)

            if num_updates == 0:
                break

            offset += self.update_batch_size

        print("done")

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        try:
            return await self._do_execute(db=db)
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])

    async def _do_execute(self, db: InfrahubDatabase) -> MigrationResult:
        console = get_migration_console()
        result = MigrationResult()

        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        console.print("Deleting branch-aware attributes for branch-agnostic nodes...", end="")
        delete_query = await DeleteBranchAwareAttrsForBranchAgnosticNodesQuery.init(db=db)
        await delete_query.execute(db=db)
        console.print("done")

        branch_agnostic_schemas: list[NodeSchema] = []
        migrations = []
        for node_schema_kind in main_schema_branch.node_names:
            schema = main_schema_branch.get_node(name=node_schema_kind, duplicate=False)
            if schema.branch is not BranchSupportType.AGNOSTIC:
                continue
            branch_agnostic_schemas.append(schema)
            migrations.extend(
                [
                    NodeAttributeAddMigration(
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
                        ),
                    ),
                    NodeAttributeAddMigration(
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                        ),
                    ),
                ]
            )

        global_branch = await Branch.get_by_name(db=db, name=GLOBAL_BRANCH_NAME)
        with Progress(console=console) as progress:
            update_task = progress.add_task(
                "Adding HFID and display label attributes to branch-agnostic nodes", total=len(migrations)
            )

            for migration in migrations:
                try:
                    execution_result = await migration.execute(db=db, branch=global_branch)
                    result.errors.extend(execution_result.errors)
                    progress.update(update_task, advance=1)
                except Exception as exc:
                    result.errors.append(str(exc))
                    return result

        total_nodes_query = await DefaultBranchNodeCount.init(
            db=db, kinds_to_include=[sch.kind for sch in branch_agnostic_schemas]
        )
        await total_nodes_query.execute(db=db)
        total_nodes_count = total_nodes_query.get_num_nodes()

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        with Progress(console=console) as progress:
            update_task = progress.add_task(
                f"Set display_label and human_friendly_id for {total_nodes_count} branch-agnostic nodes on global branch",
                total=total_nodes_count,
            )
            for branch_agnostic_schema in branch_agnostic_schemas:
                attribute_schema_map = {}
                if branch_agnostic_schema.display_labels:
                    attribute_schema_map[display_labels_attribute_schema] = display_label_attribute_schema
                if branch_agnostic_schema.human_friendly_id:
                    attribute_schema_map[hfid_attribute_schema] = hfid_attribute_schema
                if not attribute_schema_map:
                    continue

                await self._do_one_schema_all(
                    db=db,
                    branch=global_branch,
                    schema=branch_agnostic_schema,
                    schema_branch=main_schema_branch,
                    attribute_schema_map=attribute_schema_map,
                    progress=progress,
                    update_task=update_task,
                )

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
