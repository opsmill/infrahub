from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Any

import ujson
from rich.progress import Progress, TaskID

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.query.path_details import (
    SCHEMA_KINDS_TO_SKIP,
    DefaultBranchNodeCount,
    GetPathDetailsBranchQuery,
    GetPathDetailsDefaultBranch,
    GetResultMapQuery,
)
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import SchemaNotFoundError
from infrahub.types import is_large_attribute_type

from ..shared import MigrationRequiringRebase
from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class UpdateAttributeValuesQuery(Query):
    """Update the values of the given attribute schema for the input Node-id-to-value map.

    Includes special handling for updating large-type attributes b/c they are not indexed and will be slow to update
    on large data sets.

    """

    name = "update_attribute_values"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, attribute_schema: AttributeSchema, values_by_id_map: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attribute_name = attribute_schema.name
        self.is_large_type_attribute = is_large_attribute_type(attribute_schema.kind)
        self.is_branch_agnostic = attribute_schema.get_branch() is BranchSupportType.AGNOSTIC
        self.values_by_id_map = values_by_id_map

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "node_uuids": list(self.values_by_id_map.keys()),
            "attribute_name": self.attribute_name,
            "values_by_id": self.values_by_id_map,
            "default_branch": registry.default_branch,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch": GLOBAL_BRANCH_NAME if self.is_branch_agnostic else self.branch.name,
            "branch_level": 1 if self.is_branch_agnostic else self.branch.hierarchy_level,
            "at": self.at.to_string(),
        }
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_filter_params)

        if self.is_large_type_attribute:
            # we make our own index of value to database ID, creating any vertices that are missing
            # the mapping is a list of tuples instead of an actual mapping b/c creating an actual map is not possible
            # without apoc functions
            all_distinct_values = list(set(self.values_by_id_map.values()))
            diy_index_query = """
MATCH (av:AttributeValue&!AttributeValueIndexed {is_default: false})
WHERE av.value IN $all_distinct_values
WITH collect([av.value, elementId(av)]) AS value_id_pairs, collect(av.value) AS found_values
WITH value_id_pairs, found_values,
    reduce(
        missing_distinct_values = [], value IN $all_distinct_values |
            CASE
                WHEN value IN found_values THEN missing_distinct_values
                ELSE missing_distinct_values + [value]
            END
    ) AS missing_distinct_values
CALL (missing_distinct_values) {
    UNWIND missing_distinct_values AS missing_value
    CREATE (av:AttributeValue {is_default: false, value: missing_value})
    RETURN collect([av.value, elementId(av)]) AS created_value_id_pairs
}
WITH value_id_pairs + created_value_id_pairs AS value_id_pairs
            """
            self.params["all_distinct_values"] = all_distinct_values
        else:
            # if this is not a large-type attribute, then just set the map to be empty
            diy_index_query = """WITH [] AS value_id_pairs"""

        self.add_to_query(diy_index_query)

        if self.branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME]:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE n.uuid IN $node_uuids
AND e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
WITH DISTINCT n, value_id_pairs
MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
WHERE e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
WITH DISTINCT n, attr, value_id_pairs
CALL (attr) {
    OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(existing_av)
    WHERE e.branch IN [$default_branch, $global_branch]
    AND e.to IS NULL
    AND e.status = "active"
    RETURN existing_av, e AS existing_has_value
}
CALL (existing_has_value) {
    WITH existing_has_value
    WHERE existing_has_value IS NOT NULL
    SET existing_has_value.to = $at
}
            """
        else:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)
WHERE n.uuid IN $node_uuids
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, value_id_pairs, is_active
WHERE is_active = TRUE
WITH DISTINCT n, value_id_pairs
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE %(branch_filter)s
    RETURN attr, r.status = "active"  AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH DISTINCT n, attr, value_id_pairs, is_active
WHERE is_active = TRUE
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
CALL (n, attr) {
    OPTIONAL MATCH (attr)-[r:HAS_VALUE]->(existing_av)
    WHERE %(branch_filter)s
    WITH r, existing_av
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH CASE
        WHEN existing_av.value <> $values_by_id[n.uuid]
        AND r.status = "active"
        AND r.branch = $branch
        THEN [r, existing_av]
        ELSE [NULL, NULL]
    END AS existing_details
    RETURN existing_details[0] AS existing_has_value, existing_details[1] AS existing_av
}
CALL (existing_has_value) {
    WITH existing_has_value
    WHERE existing_has_value IS NOT NULL
    SET existing_has_value.to = $at
}
            """ % {"branch_filter": branch_filter}
        self.add_to_query(update_value_query)

        if self.is_large_type_attribute:
            # use the index we created at the start to get the database ID of the AttributeValue vertex
            # and then link the Attribute to the AttributeValue
            set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH attr, existing_av, value_id_pairs, $values_by_id[n.uuid] AS required_value
WHERE existing_av.value <> required_value
OR existing_av IS NULL
WITH attr, value_id_pairs, required_value,
    reduce(av_vertex_id = NULL, pair IN value_id_pairs |
        CASE
            WHEN av_vertex_id IS NOT NULL THEN av_vertex_id
            WHEN pair[0] = required_value THEN pair[1]
            ELSE av_vertex_id
        END
    ) AS av_vertex_id
MATCH (av:AttributeValue)
WHERE elementId(av) = av_vertex_id
CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
            """
        else:
            # if not a large-type attribute, then we can just use the regular MERGE clause
            # that makes use of the index on AttributeValueIndexed
            set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH n, attr, existing_av, value_id_pairs, $values_by_id[n.uuid] AS required_value
WHERE existing_av.value <> required_value
OR existing_av IS NULL
CALL (n, attr) {
    MERGE (av:AttributeValue&AttributeValueIndexed {is_default: false, value: $values_by_id[n.uuid]} )
    WITH av, attr
    LIMIT 1
    CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
}
            """
        self.add_to_query(set_value_query)


class Migration044(MigrationRequiringRebase):
    """Backfill `human_friendly_id` and `display_label` attributes for nodes with schemas that define them."""

    name: str = "044_backfill_hfid_display_label_in_db"
    description: str = "N/A"
    minimum_version: int = 43
    update_batch_size: int = 1000
    # skip these b/c the attributes on these schema-related nodes are used to define the values included in
    # the human_friendly_id and display_label attributes on instances of these schema, so should not be updated
    kinds_to_skip: list[str] = SCHEMA_KINDS_TO_SKIP

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _do_one_schema_all(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        schema_branch: SchemaBranch,
        attribute_schema_map: dict[AttributeSchema, AttributeSchema],
        at: Timestamp,
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
            if branch.is_default:
                get_details_query: GetResultMapQuery = await GetPathDetailsDefaultBranch.init(
                    db=db,
                    schema_kind=schema.kind,
                    schema_paths=all_schema_paths,
                    offset=offset,
                    limit=self.update_batch_size,
                )
            else:
                get_details_query = await GetPathDetailsBranchQuery.init(
                    db=db,
                    branch=branch,
                    schema_kind=schema.kind,
                    schema_paths=all_schema_paths,
                    updates_only=False,
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
                    at=at,
                )
                await update_display_label_query.execute(db=db)

            if progress is not None and update_task is not None:
                progress.update(update_task, advance=num_updates)

            if num_updates == 0:
                break

            offset += self.update_batch_size

        print("done")

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        total_nodes_query = await DefaultBranchNodeCount.init(db=db, kinds_to_skip=self.kinds_to_skip)
        await total_nodes_query.execute(db=db)
        total_nodes_count = total_nodes_query.get_num_nodes()

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            with Progress(console=migration_input.console) as progress:
                update_task = progress.add_task(
                    f"Set display_label and human_friendly_id for {total_nodes_count} nodes on default branch",
                    total=total_nodes_count,
                )
                for node_schema_name in main_schema_branch.node_names:
                    if node_schema_name in self.kinds_to_skip:
                        continue

                    node_schema = main_schema_branch.get_node(name=node_schema_name, duplicate=False)

                    if node_schema.branch is not BranchSupportType.AWARE:
                        continue

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
                        at=at,
                        progress=progress,
                        update_task=update_task,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()

    async def _do_one_schema_branch(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        schema_branch: SchemaBranch,
        source_attribute_schema: AttributeSchema,
        destination_attribute_schema: AttributeSchema,
        at: Timestamp,
    ) -> None:
        print(f"Processing {schema.kind}.{destination_attribute_schema.name} for {branch.name}...", end="")

        schema_property = getattr(schema, source_attribute_schema.name)
        if isinstance(schema_property, list):
            schema_paths = [
                schema.parse_schema_path(path=str(path_part), schema=schema_branch) for path_part in schema_property
            ]
        else:
            schema_paths = [schema.parse_schema_path(path=str(schema_property), schema=schema_branch)]

        offset = 0

        while True:
            # loop until we get no results from the get_details_query
            get_details_query = await GetPathDetailsBranchQuery.init(
                db=db,
                branch=branch,
                schema_kind=schema.kind,
                schema_paths=schema_paths,
                offset=offset,
                limit=self.update_batch_size,
            )
            await get_details_query.execute(db=db)

            schema_path_values_map = get_details_query.get_result_map(schema_paths)
            if not schema_path_values_map:
                print("done")
                break
            formatted_schema_path_values_map = {}
            for k, v in schema_path_values_map.items():
                if not v:
                    continue
                if destination_attribute_schema.kind == "List":
                    formatted_v = ujson.dumps(v)
                else:
                    formatted_v = " ".join(item for item in v if item is not None)
                formatted_schema_path_values_map[k] = formatted_v

            update_attr_values_query = await UpdateAttributeValuesQuery.init(
                db=db,
                branch=branch,
                attribute_schema=destination_attribute_schema,
                values_by_id_map=formatted_schema_path_values_map,
                at=at,
            )
            await update_attr_values_query.execute(db=db)

            offset += self.update_batch_size

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        default_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")
        display_labels_attribute_schema = base_node_schema.get_attribute("display_labels")
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")

        try:
            for node_schema_name in schema_branch.node_names:
                if node_schema_name in self.kinds_to_skip:
                    continue

                node_schema = schema_branch.get_node(name=node_schema_name, duplicate=False)
                if node_schema.branch not in (BranchSupportType.AWARE, BranchSupportType.LOCAL):
                    continue
                try:
                    default_node_schema = main_schema_branch.get_node(name=node_schema_name, duplicate=False)
                except SchemaNotFoundError:
                    default_node_schema = None
                schemas_for_universal_update_map = {}
                schemas_for_targeted_update_map = {}
                if node_schema.display_label:
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
                        at=at,
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
                        at=at,
                    )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
