from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import ujson
from rich.progress import Progress, TaskID

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)
from infrahub.core.node.node_property_attribute import DisplayLabel, HumanFriendlyIdentifier
from infrahub.core.query import Query, QueryType
from infrahub.core.query.node import AttributeFromDB
from infrahub.core.schema import GenericSchema, SchemaNotFoundError

from .load_schema_branch import get_or_load_schema_branch
from .m047_backfill_or_null_display_label import UpdateAttributeValuesQuery

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


console = get_migration_console()


@dataclass
class BadNodeInfo:
    node_uuid: str
    node_kind: str
    bad_attrs: list[str] = field(default_factory=list)


class FindNodesWithBadValues(Query):
    """Find nodes where display_label or human_friendly_id attribute values contain 'None' or 'null'.

    Starts from AttributeValue vertices (smaller scan) and traces back to nodes,
    rather than scanning all Node vertices (expensive on large databases).
    """

    name = "find_nodes_with_bad_hfid_display_label"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self, value_branch_names: list[str], structural_branch_names: list[str] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.value_branch_names = value_branch_names
        # For default/global branches, structural edges are on the same branches as values.
        # For user branches, structural edges (HAS_ATTRIBUTE, IS_PART_OF) may be on the default/global branch.
        self.structural_branch_names = structural_branch_names or value_branch_names

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["value_branch_names"] = self.value_branch_names
        self.params["structural_branch_names"] = self.structural_branch_names
        self.return_labels = ["node_uuid", "node_kind", "bad_attrs"]

        query = """
// Find candidate bad values from both indexed and non-indexed attribute values
CALL () {
    // Start with the indexed vertices
    MATCH (av:AttributeValueIndexed)
    WHERE av.value CONTAINS "None" OR av.value CONTAINS "null"
    RETURN av
    UNION
    // There should be fewer non-indexed vertices, so this scan will hopefully not be too big
    MATCH (av:AttributeValue&!AttributeValueIndexed)
    WHERE av.value CONTAINS "None" OR av.value CONTAINS "null"
    RETURN av
}
// Trace back to Attribute and filter by name; HAS_VALUE must be on the target branch
WITH av
MATCH (attr:Attribute)-[hv:HAS_VALUE]->(av)
WHERE attr.name IN ["display_label", "human_friendly_id"]
AND hv.branch IN $value_branch_names
AND hv.to IS NULL
AND hv.status = "active"
WITH attr, av
// Trace back to Node; HAS_ATTRIBUTE may be on a parent branch
MATCH (n:Node)-[ha:HAS_ATTRIBUTE]->(attr)
WHERE ha.branch IN $structural_branch_names
AND ha.to IS NULL
AND ha.status = "active"
WITH DISTINCT n, collect(DISTINCT attr.name) AS bad_attrs
// Verify node is active; IS_PART_OF may be on a parent branch
MATCH (n)-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $structural_branch_names
AND e.to IS NULL
AND e.status = "active"
RETURN n.uuid AS node_uuid, n.kind AS node_kind, bad_attrs
        """
        self.add_to_query(query)

    def get_bad_nodes(self) -> list[BadNodeInfo]:
        """Return list of BadNodeInfo for nodes with bad attribute values."""
        results: list[BadNodeInfo] = []
        for result in self.get_results():
            results.append(
                BadNodeInfo(
                    node_uuid=str(result.get("node_uuid")),
                    node_kind=str(result.get("node_kind")),
                    bad_attrs=[str(a) for a in result.get("bad_attrs")],
                )
            )
        return results


class Migration059(MigrationRequiringRebase):
    """Fix display_label and human_friendly_id attributes that contain 'None' or 'null' string values.

    These bad values were introduced by earlier migrations (m044-m047) when relationship peers
    were missing and the path value was stringified as 'None'.
    """

    name: str = "059_fix_hfid_display_label_nulls"
    minimum_version: int = 58
    update_batch_size: int = 100

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _find_bad_nodes(
        self,
        db: InfrahubDatabase,
        value_branch_names: list[str],
        structural_branch_names: list[str] | None = None,
    ) -> list[BadNodeInfo]:
        find_query = await FindNodesWithBadValues.init(
            db=db, value_branch_names=value_branch_names, structural_branch_names=structural_branch_names
        )
        await find_query.execute(db=db)
        return find_query.get_bad_nodes()

    async def _compute_display_label(
        self,
        db: InfrahubDatabase,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        node: Node,
    ) -> str | None:
        """Compute the correct display_label value for a node."""
        if schema.display_label:
            dl = DisplayLabel(node_schema=schema, template=schema.display_label)
            await dl.compute(db=db, node=node)
            # NodePropertyAttribute doesn't expose a public getter that avoids needing a Node+Timestamp,
            # so accessing _value directly is the pragmatic choice in migration context.
            value = dl._value
            if value is not None:
                return value.value if isinstance(value, AttributeFromDB) else value
        # display_labels (plural) is deprecated but existing schemas in production may still use it
        elif schema.display_labels:
            parts = []
            for path in schema.display_labels:
                path_value = await node.get_path_value(db=db, path=path)
                if path_value is not None:
                    parts.append(str(path_value))
            if parts:
                return " ".join(parts)
        return None

    async def _compute_hfid(
        self,
        db: InfrahubDatabase,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        node: Node,
    ) -> str | None:
        """Compute the correct human_friendly_id value for a node, JSON-encoded."""
        if not schema.human_friendly_id:
            return None
        hfid = HumanFriendlyIdentifier(node_schema=schema, template=schema.human_friendly_id)
        await hfid.compute(db=db, node=node)
        hfid_value = hfid._value
        if hfid_value is not None:
            raw_list = hfid_value.value if isinstance(hfid_value, AttributeFromDB) else hfid_value
            return ujson.dumps(raw_list)
        return None

    async def _compute_values_for_batch(
        self,
        db: InfrahubDatabase,
        load_branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        batch: list[BadNodeInfo],
        errors: list[str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Load nodes and compute corrected display_label/HFID values for a batch.

        Returns (dl_values, hfid_values) dicts mapping node UUID to corrected value.
        """
        kind = schema.kind
        batch_uuids = [info.node_uuid for info in batch]
        bad_attrs_by_uuid = {info.node_uuid: info.bad_attrs for info in batch}

        loaded_nodes = await NodeManager.get_many(db=db, ids=batch_uuids, branch=load_branch)

        dl_values: dict[str, str] = {}
        hfid_values: dict[str, str] = {}

        for node_uuid, node in loaded_nodes.items():
            bad_attrs = bad_attrs_by_uuid.get(node_uuid, [])

            if "display_label" in bad_attrs and (schema.display_label or schema.display_labels):
                try:
                    value = await self._compute_display_label(db=db, schema=schema, node=node)
                    if value is not None:
                        dl_values[node_uuid] = value
                except Exception as exc:
                    console.print(f"  Skipping display_label for {node_uuid} ({kind}): {exc}")
                    errors.append(f"display_label compute failed for {node_uuid} ({kind}): {exc}")

            if "human_friendly_id" in bad_attrs and schema.human_friendly_id:
                try:
                    value = await self._compute_hfid(db=db, schema=schema, node=node)
                    if value is not None:
                        hfid_values[node_uuid] = value
                except Exception as exc:
                    console.print(f"  Skipping human_friendly_id for {node_uuid} ({kind}): {exc}")
                    errors.append(f"human_friendly_id compute failed for {node_uuid} ({kind}): {exc}")

        return dl_values, hfid_values

    async def _recompute_and_update(
        self,
        db: InfrahubDatabase,
        write_branch: Branch,
        load_branch: Branch,
        schema_branch: SchemaBranch,
        bad_nodes: list[BadNodeInfo],
        at: Timestamp,
        progress: Progress | None = None,
        progress_task: TaskID | None = None,
    ) -> MigrationResult:
        errors: list[str] = []

        # Group by kind for schema lookup and batching
        nodes_by_kind: dict[str, list[BadNodeInfo]] = defaultdict(list)
        for bad_node in bad_nodes:
            nodes_by_kind[bad_node.node_kind].append(bad_node)

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        display_label_attr_schema = base_node_schema.get_attribute("display_label")
        hfid_attr_schema = base_node_schema.get_attribute("human_friendly_id")

        processed = 0
        for kind, nodes in nodes_by_kind.items():
            try:
                schema = schema_branch.get(name=kind, duplicate=False)
            except SchemaNotFoundError:
                console.print(f"  Schema not found for kind {kind}, skipping {len(nodes)} nodes")
                processed += len(nodes)
                continue

            if isinstance(schema, GenericSchema):
                console.print(f"  Skipping GenericSchema kind {kind}")
                processed += len(nodes)
                continue

            for batch_start in range(0, len(nodes), self.update_batch_size):
                batch = nodes[batch_start : batch_start + self.update_batch_size]

                dl_values, hfid_values = await self._compute_values_for_batch(
                    db=db, load_branch=load_branch, schema=schema, batch=batch, errors=errors
                )

                if dl_values:
                    update_query = await UpdateAttributeValuesQuery.init(
                        db=db,
                        branch=write_branch,
                        attribute_schema=display_label_attr_schema,
                        values_by_id_map=dl_values,
                        at=at,
                    )
                    await update_query.execute(db=db)

                if hfid_values:
                    update_query = await UpdateAttributeValuesQuery.init(
                        db=db,
                        branch=write_branch,
                        attribute_schema=hfid_attr_schema,
                        values_by_id_map=hfid_values,
                        at=at,
                    )
                    await update_query.execute(db=db)

                processed += len(batch)
                if progress and progress_task is not None:
                    progress.update(progress_task, completed=processed)

        return MigrationResult(errors=errors)

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        result = MigrationResult()

        try:
            with Progress(console=console) as progress:
                # Fix bad values on default branch (branch-aware nodes)
                bad_nodes_default = await self._find_bad_nodes(db=db, value_branch_names=[default_branch_name])
                if bad_nodes_default:
                    task = progress.add_task(
                        f"Fixing {len(bad_nodes_default)} nodes with bad display_label/HFID on default branch",
                        total=len(bad_nodes_default),
                    )
                    default_result = await self._recompute_and_update(
                        db=db,
                        write_branch=default_branch,
                        load_branch=default_branch,
                        schema_branch=schema_branch,
                        bad_nodes=bad_nodes_default,
                        at=at,
                        progress=progress,
                        progress_task=task,
                    )
                    result.errors.extend(default_result.errors)
                else:
                    console.print("No nodes with bad values found on default branch")

                # Fix bad values on global branch (branch-agnostic nodes)
                global_branch = await Branch.get_by_name(db=db, name=GLOBAL_BRANCH_NAME)
                bad_nodes_global = await self._find_bad_nodes(db=db, value_branch_names=[GLOBAL_BRANCH_NAME])
                if bad_nodes_global:
                    task = progress.add_task(
                        f"Fixing {len(bad_nodes_global)} nodes with bad display_label/HFID on global branch",
                        total=len(bad_nodes_global),
                    )
                    global_result = await self._recompute_and_update(
                        db=db,
                        write_branch=global_branch,
                        load_branch=default_branch,
                        schema_branch=schema_branch,
                        bad_nodes=bad_nodes_global,
                        at=at,
                        progress=progress,
                        progress_task=task,
                    )
                    result.errors.extend(global_result.errors)
                else:
                    console.print("No nodes with bad values found on global branch")

        except Exception as exc:
            result.errors.append(str(exc))

        return result

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        # For user branches, bad HAS_VALUE edges are on this branch, but structural edges
        # (HAS_ATTRIBUTE, IS_PART_OF) may be on the default or global branch.
        root_node = await get_root_node(db=db, initialize=False)
        structural_branches = [branch.name, root_node.default_branch, GLOBAL_BRANCH_NAME]
        bad_nodes = await self._find_bad_nodes(
            db=db, value_branch_names=[branch.name], structural_branch_names=structural_branches
        )
        if not bad_nodes:
            console.print(f"No nodes with bad values found on branch {branch.name}")
            return MigrationResult()

        try:
            with Progress(console=console) as progress:
                task = progress.add_task(
                    f"Fixing {len(bad_nodes)} nodes with bad display_label/HFID on branch {branch.name}",
                    total=len(bad_nodes),
                )
                return await self._recompute_and_update(
                    db=db,
                    write_branch=branch,
                    load_branch=branch,
                    schema_branch=schema_branch,
                    bad_nodes=bad_nodes,
                    at=at,
                    progress=progress,
                    progress_task=task,
                )
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
