from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from rich.progress import Progress, TaskID

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, NULL_VALUE, BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import MigrationRequiringRebase, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType
from infrahub.types import is_large_attribute_type

from .load_schema_branch import get_or_load_schema_branch
from .m044_backfill_hfid_display_label_in_db import DefaultBranchNodeCount, GetPathDetailsDefaultBranch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


def extract_jinja2_variables_in_order(template_str: str) -> list[str]:
    """Extract Jinja2 variables from a template string in the order they appear.

    I do not like this but, it seems that using Jinja2's built-in functions does not guarantee order.
    It's probably fine though since we know that the template is valid as it has been validated before.
    """
    # We all love regex right? This one should match Jinja2 variable patterns like {{ variable }}
    pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}"
    matches = re.finditer(pattern, template_str)

    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        var_name = match.group(1)
        if var_name not in seen:
            seen.add(var_name)
            result.append(var_name)

    return result


class UpdateAttributeValuesQuery(Query):
    """
    Update the values of the given attribute schema for the input node-id-to-value map.

    This version only expires existing values when they're different from the new value,
    making it safe to run idempotently without clearing correct existing values.

    This code is adapted from m044_backfill_hfid_display_label_in_db.
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
CALL (existing_has_value, existing_av, n) {
    WITH existing_has_value, existing_av, n
    WHERE existing_has_value IS NOT NULL
    AND existing_av.value <> $values_by_id[n.uuid]
    SET existing_has_value.to = $at
}
WITH n, attr, existing_av, value_id_pairs
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
    WITH r, existing_av, n
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
WITH n, attr, existing_av, value_id_pairs
            """ % {"branch_filter": branch_filter}
        self.add_to_query(update_value_query)

        if self.is_large_type_attribute:
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


class GetNodesWithoutDisplayLabelQuery(Query):
    """Get all active nodes that do not have a display_label attribute."""

    name = "get_nodes_without_display_label"
    type = QueryType.READ

    def __init__(self, kinds_to_skip: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.kinds_to_skip = kinds_to_skip or []

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "branch_names": [registry.default_branch, GLOBAL_BRANCH_NAME],
            "kinds_to_skip": self.kinds_to_skip,
            "attribute_name": "display_label",
        }
        query = """
// ------------
// Get all active nodes that don't have a display_label attribute
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE NOT n.kind IN $kinds_to_skip
AND e.branch IN $branch_names
AND e.status = "active"
AND e.to IS NULL
AND NOT exists((n)-[:IS_PART_OF {branch: e.branch, status: "deleted"}]->(:Root))
WITH DISTINCT n, e AS is_part_of_e
OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
WHERE r.branch IN $branch_names
AND r.status = "active"
AND r.to IS NULL
WITH n, is_part_of_e, r AS has_attr_e
WHERE is_part_of_e.status = "active" AND (has_attr_e IS NULL OR has_attr_e.status = "deleted")
WITH n.uuid AS node_uuid
        """
        self.add_to_query(query)
        self.return_labels = ["node_uuid"]

    def get_node_uuids(self) -> list[str]:
        return [result.get_as_type(label="node_uuid", return_type=str) for result in self.get_results()]


class CreateDisplayLabelNullQuery(Query):
    """Create display_label attribute with NULL value for the given nodes."""

    name = "create_display_label_null"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, node_uuids: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_uuids = node_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "node_uuids": self.node_uuids,
            "attribute_name": "display_label",
            "default_branch": registry.default_branch,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "at": self.at.to_string(),
            "null_value": NULL_VALUE,
            "branch_support": "aware",
            "is_protected_default": False,
            "is_visible_default": True,
        }
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_filter_params)

        # Create the NULL AttributeValue and Boolean values first
        create_av_query = """
MERGE (av:AttributeValue&AttributeValueIndexed {is_default: false, value: $null_value})
MERGE (is_protected_value:Boolean { value: $is_protected_default })
MERGE (is_visible_value:Boolean { value: $is_visible_default })
        """
        self.add_to_query(create_av_query)

        if self.branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME]:
            query = """
// ------------
// Create the display_label attribute with NULL value for nodes
// ------------
WITH av, is_protected_value, is_visible_value
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE n.uuid IN $node_uuids
AND e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
CREATE (a:Attribute { name: $attribute_name, branch_support: $branch_support })
CREATE (n)-[:HAS_ATTRIBUTE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(a)
CREATE (a)-[:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
CREATE (a)-[:IS_PROTECTED { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(is_protected_value)
CREATE (a)-[:IS_VISIBLE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(is_visible_value)
            """
        else:
            query = """
// ------------
// Create the display_label attribute with NULL value for nodes
// ------------
WITH av, is_protected_value, is_visible_value
MATCH (n:Node)
WHERE n.uuid IN $node_uuids
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, is_active, av, is_protected_value, is_visible_value
WHERE is_active = TRUE
CREATE (a:Attribute { name: $attribute_name, branch_support: $branch_support })
CREATE (n)-[:HAS_ATTRIBUTE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(a)
CREATE (a)-[:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
CREATE (a)-[:IS_PROTECTED { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(is_protected_value)
CREATE (a)-[:IS_VISIBLE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(is_visible_value)
            """ % {"branch_filter": branch_filter}

        self.add_to_query(query)


class Migration047(MigrationRequiringRebase):
    """
    Backfill `display_label` attributes for all nodes:
    - If schema does not define display_label OR attribute doesn't exist: insert NULL value
    - If schema defines display_label: compute and store the value, invalidate NULL value if exists
    """

    name: str = "047_backfill_or_null_display_label"
    minimum_version: int = 46
    update_batch_size: int = 1000
    # skip these b/c the attributes on these schema-related nodes are used to define the values included in
    # the display_label attributes on instances of these schema, so should not be updated
    kinds_to_skip: list[str] = ["SchemaNode", "SchemaAttribute", "SchemaRelationship", "SchemaGeneric"]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    def _extract_schema_paths_from_display_label(
        self, schema: MainSchemaTypes, schema_branch: SchemaBranch
    ) -> list[SchemaAttributePath]:
        """Extract schema paths from display_label, handling both simple paths and Jinja2 templates.

        This follows the same logic as _validate_display_label in schema_branch.py.
        """
        if not schema.display_label:
            return []

        if not any(c in schema.display_label for c in "{}"):
            schema_path = schema.parse_schema_path(path=schema.display_label, schema=schema_branch)
            return [schema_path]

        schema_paths = []
        for variable in extract_jinja2_variables_in_order(schema.display_label):
            schema_path = schema.parse_schema_path(path=variable, schema=schema_branch)
            schema_paths.append(schema_path)

        return schema_paths

    async def _do_one_schema_all(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: MainSchemaTypes,
        schema_branch: SchemaBranch,
        attribute_schema: AttributeSchema,
        progress: Progress | None = None,
        update_task: TaskID | None = None,
    ) -> None:
        schema_paths = self._extract_schema_paths_from_display_label(schema=schema, schema_branch=schema_branch)
        if not schema_paths:
            return

        offset = 0

        # loop until we get no results from the get_details_query
        while True:
            get_details_query = await GetPathDetailsDefaultBranch.init(
                db=db, schema_kind=schema.kind, schema_paths=schema_paths, offset=offset, limit=self.update_batch_size
            )
            await get_details_query.execute(db=db)

            # Get the values for all schema paths
            schema_path_values_map = get_details_query.get_result_map(schema_paths)
            num_updates = len(schema_path_values_map)

            # Format the values (join multiple values with space for display_label)
            # NOTE: this may not result in what the user defined,
            formatted_schema_path_values_map = {}
            for k, v in schema_path_values_map.items():
                if not v:
                    continue
                # NOTE: this may not be what the user defined, we should render the Jinja2 template
                formatted_schema_path_values_map[k] = " ".join(item for item in v if item is not None)

            if formatted_schema_path_values_map:
                update_display_label_query = await UpdateAttributeValuesQuery.init(
                    db=db,
                    branch=branch,
                    attribute_schema=attribute_schema,
                    values_by_id_map=formatted_schema_path_values_map,
                )
                await update_display_label_query.execute(db=db)

            if progress is not None and update_task is not None:
                progress.update(update_task, advance=num_updates)

            if num_updates == 0:
                break

            offset += self.update_batch_size

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        main_schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        # Get nodes without display_label in the database
        get_nodes_without_dl_query = await GetNodesWithoutDisplayLabelQuery.init(
            db=db, kinds_to_skip=self.kinds_to_skip
        )
        await get_nodes_without_dl_query.execute(db=db)
        nodes_without_display_label = get_nodes_without_dl_query.get_node_uuids()

        # Count nodes that will get computed values
        kinds_to_backfill: list[str] = []
        for node_schema_name in (
            main_schema_branch.node_names + main_schema_branch.profile_names + main_schema_branch.template_names
        ):
            if node_schema_name in self.kinds_to_skip:
                continue

            node_schema = main_schema_branch.get(name=node_schema_name, duplicate=False)
            if node_schema.branch != BranchSupportType.AWARE or not node_schema.display_label:
                continue

            kinds_to_backfill.append(node_schema.kind)

        backfill_count = 0
        if kinds_to_backfill:
            count_query = await DefaultBranchNodeCount.init(
                db=db, kinds_to_skip=self.kinds_to_skip, kinds_to_include=kinds_to_backfill
            )
            await count_query.execute(db=db)
            backfill_count = count_query.get_num_nodes()

        try:
            with Progress(console=console) as progress:
                # Create NULL display_label
                if nodes_without_display_label:
                    null_task = progress.add_task(
                        f"Creating NULL display_label for {len(nodes_without_display_label)} nodes",
                        total=len(nodes_without_display_label),
                    )

                    for offset in range(0, len(nodes_without_display_label), self.update_batch_size):
                        batch_uuids = nodes_without_display_label[offset : offset + self.update_batch_size]
                        if not batch_uuids:
                            break

                        create_display_label_query = await CreateDisplayLabelNullQuery.init(
                            db=db, branch=default_branch, node_uuids=batch_uuids
                        )
                        await create_display_label_query.execute(db=db)

                        progress.update(null_task, advance=len(batch_uuids))

                # Backfill computed display_label values
                if backfill_count > 0:
                    backfill_task = progress.add_task(
                        f"Backfilling computed display_label for {backfill_count} nodes",
                        total=backfill_count,
                    )

                    for node_schema_name in kinds_to_backfill:
                        await self._do_one_schema_all(
                            db=db,
                            branch=default_branch,
                            schema=main_schema_branch.get(name=node_schema_name, duplicate=False),
                            schema_branch=main_schema_branch,
                            attribute_schema=display_label_attribute_schema,
                            progress=progress,
                            update_task=backfill_task,
                        )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:  # noqa: ARG002
        # FIXME
        return MigrationResult()
