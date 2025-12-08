from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.template import Jinja2Template
from rich.progress import Progress, TaskID

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, NULL_VALUE, BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import MigrationRequiringRebase, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType

from .load_schema_branch import get_or_load_schema_branch
from .m044_backfill_hfid_display_label_in_db import (
    DefaultBranchNodeCount,
    GetPathDetailsBranchQuery,
    GetPathDetailsDefaultBranch,
    GetResultMapQuery,
)

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


def _is_jinja2_template(display_label: str) -> bool:
    return any(c in display_label for c in "{}")


def _extract_jinja2_variables(template_str: str) -> list[str]:
    return Jinja2Template(template=template_str).get_variables()


async def _render_display_label(display_label: str, variable_names: list[str], values: list[Any]) -> str | None:
    if not _is_jinja2_template(display_label):
        return values[0] if values and values[0] is not None else None

    variables = dict(zip(variable_names, values, strict=False))
    jinja_template = Jinja2Template(template=display_label)
    return await jinja_template.render(variables=variables)


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
WITH DISTINCT n
MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
WHERE e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
WITH DISTINCT n, attr
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
WITH n, attr, existing_av
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
WITH n, is_active
WHERE is_active = TRUE
WITH DISTINCT n
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE %(branch_filter)s
    RETURN attr, r.status = "active"  AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH DISTINCT n, attr, is_active
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
WITH n, attr, existing_av
            """ % {"branch_filter": branch_filter}
        self.add_to_query(update_value_query)

        set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH n, attr, existing_av, $values_by_id[n.uuid] AS required_value
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
    """Get all active nodes that do not have a display_label attribute on the default branch."""

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
WITH DISTINCT n
CALL (n) {
    OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE r.branch IN $branch_names
    RETURN r AS has_attr_e
    ORDER BY r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, has_attr_e
WHERE (has_attr_e IS NULL OR has_attr_e.status = "deleted")
WITH n.uuid AS node_uuid
        """
        self.add_to_query(query)
        self.return_labels = ["node_uuid"]

    def get_node_uuids(self) -> list[str]:
        return [result.get_as_type(label="node_uuid", return_type=str) for result in self.get_results()]


class GetNodesWithoutDisplayLabelBranchQuery(Query):
    """Get all active nodes that do not have a display_label attribute on a non-default branch."""

    name = "get_nodes_without_display_label_branch"
    type = QueryType.READ

    def __init__(self, kinds_to_skip: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.kinds_to_skip = kinds_to_skip or []

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params = {
            "kinds_to_skip": self.kinds_to_skip,
            "attribute_name": "display_label",
            **branch_filter_params,
        }
        query = """
// ------------
// Get all active nodes that don't have a display_label attribute
// ------------
MATCH (n:Node)
WHERE NOT n.kind IN $kinds_to_skip
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r AS is_part_of_e
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, is_part_of_e
WHERE is_part_of_e.status = "active"
CALL (n) {
    OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE %(branch_filter)s
    RETURN r AS has_attr_e
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, has_attr_e
WHERE (has_attr_e IS NULL OR has_attr_e.status = "deleted")
WITH n.uuid AS node_uuid
        """ % {"branch_filter": branch_filter}
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

        # Create the NULL AttributeValue first
        create_av_query = """
MERGE (av:AttributeValue&AttributeValueIndexed {is_default: true, value: $null_value})
WITH av
LIMIT 1
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
CREATE (a:Attribute { uuid: randomUUID(), name: $attribute_name, branch_support: $branch_support })
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
CREATE (a:Attribute { uuid: randomUUID(), name: $attribute_name, branch_support: $branch_support })
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

        if not _is_jinja2_template(schema.display_label):
            schema_path = schema.parse_schema_path(path=schema.display_label, schema=schema_branch)
            return [schema_path]

        schema_paths = []
        for variable in _extract_jinja2_variables(schema.display_label):
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
        if not schema.display_label:
            return

        schema_paths = self._extract_schema_paths_from_display_label(schema=schema, schema_branch=schema_branch)
        if not schema_paths:
            return

        offset = 0

        # loop until we get no results from the get_details_query
        while True:
            if branch.is_default:
                get_details_query: GetResultMapQuery = await GetPathDetailsDefaultBranch.init(
                    db=db,
                    schema_kind=schema.kind,
                    schema_paths=schema_paths,
                    offset=offset,
                    limit=self.update_batch_size,
                )
            else:
                get_details_query = await GetPathDetailsBranchQuery.init(
                    db=db,
                    branch=branch,
                    schema_kind=schema.kind,
                    schema_paths=schema_paths,
                    updates_only=False,
                    offset=offset,
                    limit=self.update_batch_size,
                )
            await get_details_query.execute(db=db)

            # Get the values for all schema paths
            schema_path_values_map = get_details_query.get_result_map(schema_paths)
            num_updates = len(schema_path_values_map)

            formatted_schema_path_values_map: dict[str, str] = {}
            for k, v in schema_path_values_map.items():
                if not v:
                    continue

                rendered_value = await _render_display_label(
                    display_label=schema.display_label,
                    variable_names=[s.attribute_path_as_str for s in schema_paths],
                    values=v,
                )
                if rendered_value is not None:
                    formatted_schema_path_values_map[k] = rendered_value

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

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        try:
            get_nodes_without_dl_query = await GetNodesWithoutDisplayLabelBranchQuery.init(
                db=db, branch=branch, kinds_to_skip=self.kinds_to_skip
            )
            await get_nodes_without_dl_query.execute(db=db)
            nodes_without_display_label = get_nodes_without_dl_query.get_node_uuids()

            if nodes_without_display_label:
                for offset in range(0, len(nodes_without_display_label), self.update_batch_size):
                    batch_uuids = nodes_without_display_label[offset : offset + self.update_batch_size]
                    if not batch_uuids:
                        break

                    create_display_label_query = await CreateDisplayLabelNullQuery.init(
                        db=db, branch=branch, node_uuids=batch_uuids
                    )
                    await create_display_label_query.execute(db=db)

            for node_schema_name in (
                schema_branch.node_names + schema_branch.profile_names + schema_branch.template_names
            ):
                if node_schema_name in self.kinds_to_skip:
                    continue

                node_schema = schema_branch.get(name=node_schema_name, duplicate=False)
                if node_schema.branch != BranchSupportType.AWARE or not node_schema.display_label:
                    continue

                await self._do_one_schema_all(
                    db=db,
                    branch=branch,
                    schema=node_schema,
                    schema_branch=schema_branch,
                    attribute_schema=display_label_attribute_schema,
                )

        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
