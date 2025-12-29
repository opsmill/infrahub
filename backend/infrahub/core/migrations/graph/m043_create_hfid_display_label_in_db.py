from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import MigrationRequiringRebase, MigrationResult, get_migration_console
from infrahub.core.path import SchemaPath
from infrahub.core.query import Query, QueryType

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class GetAddedNodesByKindForBranchQuery(Query):
    name = "get_added_nodes_by_kind_for_branch_query"
    type = QueryType.READ
    insert_return = True

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["branch"] = self.branch.name
        query = """
MATCH (n:Node)-[e:IS_PART_OF {branch: $branch, status: "active"}]->(:Root)
WHERE e.to IS NULL
AND NOT exists((n)-[:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root))
WITH n.kind AS kind, collect(n.uuid) AS node_ids
        """
        self.return_labels = ["kind", "node_ids"]
        self.add_to_query(query)

    def get_node_ids_by_kind(self) -> dict[str, list[str]]:
        node_ids_by_kind: dict[str, list[str]] = {}
        for result in self.get_results():
            kind = result.get_as_type(label="kind", return_type=str)
            node_ids: list[str] = result.get_as_type(label="node_ids", return_type=list)
            node_ids_by_kind[kind] = node_ids
        return node_ids_by_kind


class Migration043(MigrationRequiringRebase):
    name: str = "043_create_hfid_display_label_in_db"
    minimum_version: int = 42

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        schema_node = main_schema_branch.get_node(name="SchemaNode")
        schema_generic = main_schema_branch.get_node(name="SchemaGeneric")

        migrations = [
            # HFID is not needed, it was introduced at graph v8
            NodeAttributeAddMigration(
                new_node_schema=schema_node,
                previous_node_schema=schema_node,
                schema_path=SchemaPath(
                    schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                ),
            ),
            NodeAttributeAddMigration(
                new_node_schema=schema_generic,
                previous_node_schema=schema_generic,
                schema_path=SchemaPath(
                    schema_kind="SchemaGeneric", path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                ),
            ),
        ]

        for node_schema_kind in main_schema_branch.node_names:
            schema = main_schema_branch.get(name=node_schema_kind, duplicate=False)
            if schema.branch is not BranchSupportType.AWARE:
                continue
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

        with Progress(console=get_migration_console()) as progress:
            update_task = progress.add_task("Adding HFID and display label to nodes", total=len(migrations))

            for migration in migrations:
                try:
                    execution_result = await migration.execute(db=db, branch=default_branch)
                    result.errors.extend(execution_result.errors)
                    progress.update(update_task, advance=1)
                except Exception as exc:
                    result.errors.append(str(exc))
                    return result

        return result

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        result = MigrationResult()

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)

        migrations = []
        get_added_nodes_by_kind_for_branch_query = await GetAddedNodesByKindForBranchQuery.init(db=db, branch=branch)
        await get_added_nodes_by_kind_for_branch_query.execute(db=db)
        node_ids_by_kind = get_added_nodes_by_kind_for_branch_query.get_node_ids_by_kind()

        for node_kind, node_ids in node_ids_by_kind.items():
            schema = schema_branch.get(name=node_kind, duplicate=False)
            if schema.branch not in (BranchSupportType.AWARE, BranchSupportType.LOCAL):
                continue
            migrations.extend(
                [
                    NodeAttributeAddMigration(
                        uuids=node_ids,
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
                        ),
                    ),
                    NodeAttributeAddMigration(
                        uuids=node_ids,
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                        ),
                    ),
                ]
            )

        with Progress(console=get_migration_console()) as progress:
            update_task = progress.add_task(
                f"Adding HFID and display label to nodes on branch {branch.name}", total=len(migrations)
            )

            for migration in migrations:
                try:
                    execution_result = await migration.execute(db=db, branch=branch)
                    result.errors.extend(execution_result.errors)
                    progress.update(update_task, advance=1)
                except Exception as exc:
                    result.errors.append(str(exc))
                    return result

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
