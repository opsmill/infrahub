from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress, TaskID

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.query.update_attribute_values import UpdateAttributeValuesQuery
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)
from infrahub.core.query import Query, QueryType
from infrahub.core.schema.definitions.core.permission import core_global_permission, core_object_permission

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


class GetPermissionAttributesQuery(Query):
    """Get permission nodes with their attribute values for computing display_label."""

    name = "get_permission_attributes"
    type = QueryType.READ
    insert_return = False

    def __init__(self, permission_kind: str, is_branch_agnostic: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.permission_kind = permission_kind
        self.is_branch_agnostic = is_branch_agnostic

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "permission_kind": self.permission_kind,
            "branch_names": [GLOBAL_BRANCH_NAME] if self.is_branch_agnostic else [registry.default_branch],
        }

        if self.is_branch_agnostic:
            query = """
MATCH (n:Node {kind: $permission_kind})-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $branch_names
AND e.status = "active"
AND e.to IS NULL
WITH DISTINCT n
// Get action attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(action_attr:Attribute {name: "action"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (action_attr)-[hv:HAS_VALUE]->(action_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN action_val.value AS action_value
}
// Get decision attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(decision_attr:Attribute {name: "decision"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (decision_attr)-[hv:HAS_VALUE]->(decision_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN decision_val.value AS decision_value
}
RETURN n.uuid AS node_uuid, action_value, decision_value
            """
        else:
            query = """
MATCH (n:Node {kind: $permission_kind})-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $branch_names
AND e.status = "active"
AND e.to IS NULL
WITH DISTINCT n
// Get namespace attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(ns_attr:Attribute {name: "namespace"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (ns_attr)-[hv:HAS_VALUE]->(ns_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN ns_val.value AS namespace_value
}
// Get name attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(name_attr:Attribute {name: "name"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (name_attr)-[hv:HAS_VALUE]->(name_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN name_val.value AS name_value
}
// Get action attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(action_attr:Attribute {name: "action"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (action_attr)-[hv:HAS_VALUE]->(action_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN action_val.value AS action_value
}
// Get decision attribute value
CALL (n) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(decision_attr:Attribute {name: "decision"})
    WHERE ha.branch IN $branch_names AND ha.status = "active" AND ha.to IS NULL
    MATCH (decision_attr)-[hv:HAS_VALUE]->(decision_val:AttributeValue)
    WHERE hv.branch IN $branch_names AND hv.status = "active" AND hv.to IS NULL
    RETURN decision_val.value AS decision_value
}
RETURN n.uuid AS node_uuid, namespace_value, name_value, action_value, decision_value
            """

        self.add_to_query(query)
        if self.is_branch_agnostic:
            self.return_labels = ["node_uuid", "action_value", "decision_value"]
        else:
            self.return_labels = ["node_uuid", "namespace_value", "name_value", "action_value", "decision_value"]

    def get_results_as_dicts(self) -> list[dict[str, Any]]:
        return [{label: result.get(label) for label in self.return_labels} for result in self.get_results()]


class GetPermissionAttributesBranchQuery(Query):
    """Get permission nodes with their attribute values on a non-default branch."""

    name = "get_permission_attributes_branch"
    type = QueryType.READ
    insert_return = False

    def __init__(self, permission_kind: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.permission_kind = permission_kind

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter_r, branch_filter_params_r = self.branch.get_query_filter_path(
            at=self.at, variable_name="r", params_prefix="r_"
        )
        branch_filter_r2, branch_filter_params_r2 = self.branch.get_query_filter_path(
            at=self.at, variable_name="r2", params_prefix="r2_"
        )
        self.params = {"permission_kind": self.permission_kind, **branch_filter_params_r, **branch_filter_params_r2}

        query = """
MATCH (n:Node {kind: $permission_kind})
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter_r)s
    RETURN r AS is_part_of_e
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, is_part_of_e
WHERE is_part_of_e.status = "active"
// Get namespace attribute value
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(ns_attr:Attribute {name: "namespace"})
    WHERE %(branch_filter_r)s
    WITH ns_attr, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH ns_attr, r
    WHERE r.status = "active"
    MATCH (ns_attr)-[r2:HAS_VALUE]->(ns_val:AttributeValue)
    WHERE %(branch_filter_r2)s
    WITH ns_val, r2
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
    WITH ns_val, r2
    WHERE r2.status = "active"
    RETURN ns_val.value AS namespace_value
}
// Get name attribute value
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(name_attr:Attribute {name: "name"})
    WHERE %(branch_filter_r)s
    WITH name_attr, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH name_attr, r
    WHERE r.status = "active"
    MATCH (name_attr)-[r2:HAS_VALUE]->(name_val:AttributeValue)
    WHERE %(branch_filter_r2)s
    WITH name_val, r2
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
    WITH name_val, r2
    WHERE r2.status = "active"
    RETURN name_val.value AS name_value
}
// Get action attribute value
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(action_attr:Attribute {name: "action"})
    WHERE %(branch_filter_r)s
    WITH action_attr, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH action_attr, r
    WHERE r.status = "active"
    MATCH (action_attr)-[r2:HAS_VALUE]->(action_val:AttributeValue)
    WHERE %(branch_filter_r2)s
    WITH action_val, r2
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
    WITH action_val, r2
    WHERE r2.status = "active"
    RETURN action_val.value AS action_value
}
// Get decision attribute value
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(decision_attr:Attribute {name: "decision"})
    WHERE %(branch_filter_r)s
    WITH decision_attr, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH decision_attr, r
    WHERE r.status = "active"
    MATCH (decision_attr)-[r2:HAS_VALUE]->(decision_val:AttributeValue)
    WHERE %(branch_filter_r2)s
    WITH decision_val, r2
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
    WITH decision_val, r2
    WHERE r2.status = "active"
    RETURN decision_val.value AS decision_value
}
RETURN n.uuid AS node_uuid, namespace_value, name_value, action_value, decision_value
        """ % {"branch_filter_r": branch_filter_r, "branch_filter_r2": branch_filter_r2}

        self.add_to_query(query)
        self.return_labels = ["node_uuid", "namespace_value", "name_value", "action_value", "decision_value"]

    def get_results_as_dicts(self) -> list[dict[str, Any]]:
        return [{label: result.get(label) for label in self.return_labels} for result in self.get_results()]


class Migration059(MigrationRequiringRebase):
    """Recompute display_label for all permission nodes (CoreObjectPermission and CoreGlobalPermission)."""

    name: str = "059_recompute_permission_display_labels"
    minimum_version: int = 58
    update_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _compute_object_permission_display_labels(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        attribute_schema: AttributeSchema,
        progress: Progress | None = None,
        update_task: TaskID | None = None,
    ) -> None:
        """Compute and update display_label for ObjectPermission nodes."""
        if not core_object_permission.display_label:
            return

        query: GetPermissionAttributesQuery | GetPermissionAttributesBranchQuery
        if branch.is_default:
            query = await GetPermissionAttributesQuery.init(
                db=db, permission_kind=InfrahubKind.OBJECTPERMISSION, is_branch_agnostic=False
            )
        else:
            query = await GetPermissionAttributesBranchQuery.init(
                db=db, branch=branch, permission_kind=InfrahubKind.OBJECTPERMISSION
            )
        await query.execute(db=db)
        results = query.get_results_as_dicts()

        if not results:
            return

        values_by_id: dict[str, str] = {}

        for row in results:
            node_uuid = row["node_uuid"]
            variables = {
                "namespace__value": row.get("namespace_value"),
                "name__value": row.get("name_value"),
                "action__value": row.get("action_value"),
                "decision__value": row.get("decision_value"),
            }

            if any(v is None for v in variables.values()):
                continue

            jinja_template = InfrahubJinja2Template(template=core_object_permission.display_label)
            rendered = await jinja_template.render(variables=variables)
            if rendered is not None:
                values_by_id[node_uuid] = rendered

        if values_by_id:
            for offset in range(0, len(values_by_id), self.update_batch_size):
                batch_ids = list(values_by_id.keys())[offset : offset + self.update_batch_size]
                batch_map = {k: values_by_id[k] for k in batch_ids}

                update_query = await UpdateAttributeValuesQuery.init(
                    db=db, branch=branch, attribute_schema=attribute_schema, values_by_id_map=batch_map
                )
                await update_query.execute(db=db)

                if progress is not None and update_task is not None:
                    progress.update(update_task, advance=len(batch_ids))

    async def _compute_global_permission_display_labels(
        self,
        db: InfrahubDatabase,
        attribute_schema: AttributeSchema,
        progress: Progress | None = None,
        update_task: TaskID | None = None,
    ) -> None:
        """Compute and update display_label for GlobalPermission nodes (branch-agnostic)."""
        if not core_global_permission.display_label:
            return

        query = await GetPermissionAttributesQuery.init(
            db=db, permission_kind=InfrahubKind.GLOBALPERMISSION, is_branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_results_as_dicts()

        if not results:
            return

        values_by_id: dict[str, str] = {}

        for row in results:
            node_uuid = row["node_uuid"]
            variables = {"action__value": row.get("action_value"), "decision__value": row.get("decision_value")}

            if any(v is None for v in variables.values()):
                continue

            jinja_template = InfrahubJinja2Template(template=core_global_permission.display_label)
            rendered = await jinja_template.render(variables=variables)
            if rendered is not None:
                values_by_id[node_uuid] = rendered

        if values_by_id:
            for offset in range(0, len(values_by_id), self.update_batch_size):
                batch_ids = list(values_by_id.keys())[offset : offset + self.update_batch_size]
                batch_map = {k: values_by_id[k] for k in batch_ids}

                global_branch = await Branch.get_by_name(db=db, name=GLOBAL_BRANCH_NAME)
                update_query = await UpdateAttributeValuesQuery.init(
                    db=db, branch=global_branch, attribute_schema=attribute_schema, values_by_id_map=batch_map
                )
                await update_query.execute(db=db)

                if progress is not None and update_task is not None:
                    progress.update(update_task, advance=len(batch_ids))

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db

        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)

        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        obj_count_query = await GetPermissionAttributesQuery.init(
            db=db, permission_kind=InfrahubKind.OBJECTPERMISSION, is_branch_agnostic=False
        )
        await obj_count_query.execute(db=db)
        obj_permission_count = len(obj_count_query.get_results_as_dicts())

        global_count_query = await GetPermissionAttributesQuery.init(
            db=db, permission_kind=InfrahubKind.GLOBALPERMISSION, is_branch_agnostic=True
        )
        await global_count_query.execute(db=db)
        global_permission_count = len(global_count_query.get_results_as_dicts())

        total_count = obj_permission_count + global_permission_count

        try:
            with Progress(console=console) as progress:
                if total_count > 0:
                    update_task = progress.add_task(
                        f"Recomputing display_label for {total_count} permissions", total=total_count
                    )

                    await self._compute_object_permission_display_labels(
                        db=db,
                        branch=default_branch,
                        attribute_schema=display_label_attribute_schema,
                        progress=progress,
                        update_task=update_task,
                    )
                    await self._compute_global_permission_display_labels(
                        db=db,
                        attribute_schema=display_label_attribute_schema,
                        progress=progress,
                        update_task=update_task,
                    )

        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
            return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        """Execute migration on non-default branches (only ObjectPermission, GlobalPermission is branch-agnostic)."""
        db = migration_input.db

        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)
        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        try:
            await self._compute_object_permission_display_labels(
                db=db, branch=branch, attribute_schema=display_label_attribute_schema
            )
        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
            return MigrationResult(errors=[error_msg])

        return MigrationResult()
