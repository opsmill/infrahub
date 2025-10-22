from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, RelationshipDirection
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import AttributeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.types import is_large_attribute_type

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.database import InfrahubDatabase

# TODO: get HFID at same time as display labels
# TODO: set HFID


class DefaultBranchNodeCount(Query):
    name = "get_branch_node_count"
    type = QueryType.READ

    def __init__(self, branch_names: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.branch_names = branch_names

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "branch_names": self.branch_names,
        }
        query = """
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $branch_names
AND e.status = "active"
AND e.to IS NULL
AND NOT exists((n)-[:IS_PART_OF {branch: e.branch, status: "deleted"}]->(:Root))
WITH count(*) AS num_nodes
        """
        self.add_to_query(query)
        self.return_labels = ["num_nodes"]

    def get_num_nodes(self) -> int:
        result = self.get_result()
        if not result:
            return 0
        return result.get_as_type(label="num_nodes", return_type=int)


class GetPathDetailsDefaultBranch(Query):
    name = "get_path_details_default_branch"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self, branch_names: list[str], schema_kind: str, schema_paths: list[SchemaAttributePath], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.branch_names = branch_names
        self.schema_kind = schema_kind
        self.schema_paths = schema_paths
        self.attribute_names = []
        self.bidir_rel_attr_map = {}
        self.outbound_rel_attr_map = {}
        self.inbound_rel_attr_map = {}
        for schema_path in schema_paths:
            if schema_path.is_type_attribute and schema_path.attribute_schema:
                self.attribute_names.append(schema_path.attribute_schema.name)
            elif schema_path.is_type_relationship and schema_path.relationship_schema and schema_path.attribute_schema:
                key = schema_path.relationship_schema.identifier
                value = schema_path.attribute_schema.name
                if schema_path.relationship_schema.direction is RelationshipDirection.BIDIR:
                    self.bidir_rel_attr_map[key] = value
                elif schema_path.relationship_schema.direction is RelationshipDirection.OUTBOUND:
                    self.outbound_rel_attr_map[key] = value
                elif schema_path.relationship_schema.direction is RelationshipDirection.INBOUND:
                    self.inbound_rel_attr_map[key] = value

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "branch_names": self.branch_names,
            "attribute_names": self.attribute_names,
            "outbound_rel_ids": list(self.outbound_rel_attr_map.keys()),
            "inbound_rel_ids": list(self.inbound_rel_attr_map.keys()),
            "bidirectional_rel_ids": list(self.bidir_rel_attr_map.keys()),
            "outbound_rel_attr_map": self.outbound_rel_attr_map,
            "inbound_rel_attr_map": self.inbound_rel_attr_map,
            "bidirectional_rel_attr_map": self.bidir_rel_attr_map,
            "offset": self.offset,
            "limit": self.limit,
        }
        get_details_query = """
MATCH (n:%(schema_kind)s)-[e:IS_PART_OF]->(:Root)
WHERE e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"

WITH DISTINCT n
ORDER BY elementId(n)
SKIP toInteger($offset)
LIMIT toInteger($limit)

OPTIONAL MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name IN $attribute_names
AND e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"
WITH n, attr
OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(attr_val:AttributeValue)
WHERE e.branch IN $branch_names
AND e.to IS NULL
AND e.status = "active"

WITH n, collect([attr.name, attr_val.value]) AS attr_vals_list

OPTIONAL MATCH (n)-[e1:IS_RELATED]-(rel:Relationship)-[e2:IS_RELATED]-(peer:Node)
WHERE rel.name IN $bidirectional_rel_ids + $outbound_rel_ids + $inbound_rel_ids
AND e1.branch IN $branch_names
AND e1.to IS NULL
AND e1.status = "active"
AND e2.branch IN $branch_names
AND e2.to IS NULL
AND e2.status = "active"
AND (
    (startNode(e1) = n AND startNode(e2) = rel AND rel.name IN $outbound_rel_ids)
    OR (startNode(e1) = rel AND startNode(e2) = n AND rel.name IN $inbound_rel_ids)
    OR (startNode(e1) = n AND startNode(e2) = peer AND rel.name IN $bidirectional_rel_ids)
)

WITH DISTINCT n, attr_vals_list, rel.name AS rel_name, peer,  CASE
    WHEN startNode(e1) = n AND startNode(e2) = rel AND rel.name IN $outbound_rel_ids THEN "outbound"
    WHEN startNode(e1) = rel AND startNode(e2) = n AND rel.name IN $inbound_rel_ids THEN "inbound"
    ELSE "bidir"
END AS direction
OPTIONAL MATCH (peer)-[e1:HAS_ATTRIBUTE]->(attr:Attribute)-[e2:HAS_VALUE]->(peer_attr_val:AttributeValue)
WHERE (
    (direction = "outbound" AND attr.name IN $outbound_rel_attr_map[rel_name])
    OR (direction = "inbound" AND attr.name IN $inbound_rel_attr_map[rel_name])
    OR (direction = "bidir" AND attr.name IN $bidirectional_rel_attr_map[rel_name])
)
AND e1.branch IN $branch_names
AND e1.to IS NULL
AND e1.status = "active"
AND e2.branch IN $branch_names
AND e2.to IS NULL
AND e2.status = "active"

WITH DISTINCT n, attr_vals_list, rel_name, peer, direction, attr.name AS peer_attr_name, peer_attr_val.value AS peer_val
WITH n, attr_vals_list, collect([rel_name, direction, peer_attr_name, peer_val]) AS peer_attr_vals_list
        """ % {"schema_kind": self.schema_kind}
        self.add_to_query(get_details_query)
        self.return_labels = ["n.uuid AS n_uuid", "attr_vals_list", "peer_attr_vals_list"]

    def get_result_map(self) -> dict[str, list[str]]:
        schema_path_keys: list[tuple[str, RelationshipDirection, str] | str] = []
        for schema_path in self.schema_paths:
            if schema_path.is_type_attribute and schema_path.attribute_schema:
                schema_path_keys.append(schema_path.attribute_schema.name)
                continue
            relationship_key = (
                schema_path.relationship_schema.identifier,
                schema_path.relationship_schema.direction,
                schema_path.attribute_schema.name,
            )
            schema_path_keys.append(relationship_key)

        result_map: dict[str, list[str]] = {}
        for result in self.get_results():
            node_uuid = result.get_as_type(label="n_uuid", return_type=str)

            schema_path_value_map = {}
            attr_values_tuples: list[tuple[str, Any]] = result.get(label="attr_vals_list")
            for attr_value_tuple in attr_values_tuples:
                attr_name = attr_value_tuple[0]
                attr_value = attr_value_tuple[1]
                schema_path_value_map[attr_name] = attr_value

            relationship_values_tuples: list[tuple[str, str, str, Any]] = result.get(label="peer_attr_vals_list")
            for rel_value_tuple in relationship_values_tuples:
                rel_name = rel_value_tuple[0]
                direction_raw = rel_value_tuple[1]
                direction = RelationshipDirection.BIDIR
                match direction_raw:
                    case "outbound":
                        direction = RelationshipDirection.OUTBOUND
                    case "inbound":
                        direction = RelationshipDirection.INBOUND
                peer_attr_name = rel_value_tuple[2]
                peer_val = rel_value_tuple[3]
                schema_path_value_map[rel_name, direction, peer_attr_name] = peer_val

            schema_path_values = ""
            for schema_path_key in schema_path_keys:
                value = schema_path_value_map.get(schema_path_key)
                schema_path_values += " " + str(value)
            result_map[node_uuid] = schema_path_values
        return result_map


class UpdateAttributeValuesQuery(Query):
    name = "update_attribute_values"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, attribute_schema: AttributeSchema, values_by_id_map: dict[str, Any], **kwargs) -> None:
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
            "branch": GLOBAL_BRANCH_NAME if self.is_branch_agnostic else registry.default_branch,
            "branch_level": 1,
            "at": self.at.to_string(),
        }

        update_value_query = """
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

WITH DISTINCT n, attr
CALL (attr) {
    OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(existing_av)
    WHERE e.branch IN [$default_branch, $global_branch]
    AND e.to IS NULL
    AND e.status = "active"
    SET e.to = $at
}

CALL (n, attr) {
    MERGE (av:%(attribute_value_type)s {is_default: false, value: $values_by_id[n.uuid]} )
    WITH av, attr
    LIMIT 1
    CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
}
        """ % {"attribute_value_type": "AttributeValue" if self.is_large_type_attribute else "AttributeValueIndexed"}
        self.add_to_query(update_value_query)


class Migration043(ArbitraryMigration):
    """
    Backfill `human_friendly_id` and `display_label` attributes for nodes with schemas that define them.
    """

    name: str = "043_backfill_hfid_display_label_in_db"
    minimum_version: int = 42
    display_label_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        # result = MigrationResult()
        root_node = await get_root_node(db=db, initialize=False)
        default_branch = root_node.default_branch
        schema_manager = SchemaManager()
        internal_schema_root = SchemaRoot(**internal_schema)
        schema_manager.register_schema(schema=internal_schema_root)
        registry.schema = schema_manager
        main_schema_branch = await schema_manager.load_schema_from_db(db=db, branch=default_branch)

        total_nodes_query = await DefaultBranchNodeCount.init(db=db, branch_names=[default_branch, GLOBAL_BRANCH_NAME])
        await total_nodes_query.execute(db=db)
        total_nodes_count = total_nodes_query.get_num_nodes()

        base_node_schema = main_schema_branch.get("SchemaNode", duplicate=False)
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        with Progress() as progress:
            update_task = progress.add_task(
                f"Set display_label for {total_nodes_count} nodes on default branch", total=total_nodes_count
            )
            for node_schema_name in main_schema_branch.node_names:
                schema = main_schema_branch.get_node(name=node_schema_name)

                if not schema.display_labels:
                    continue

                display_labels_schema_paths = [
                    schema.parse_schema_path(path=display_label, schema=main_schema_branch)
                    for display_label in schema.display_labels
                ]
                offset = 0

                while True:
                    get_details_query = await GetPathDetailsDefaultBranch.init(
                        db=db,
                        branch_names=[default_branch, GLOBAL_BRANCH_NAME],
                        schema_kind=node_schema_name,
                        schema_paths=display_labels_schema_paths,
                        offset=offset,
                        limit=self.display_label_batch_size,
                    )
                    await get_details_query.execute(db=db)
                    schema_path_values_map = get_details_query.get_result_map()

                    if not schema_path_values_map:
                        break

                    for k, v in schema_path_values_map.items():
                        print(node_schema_name, schema.display_labels, k, v)

                    update_attribute_values_query = await UpdateAttributeValuesQuery.init(
                        db=db, attribute_schema=display_label_attribute_schema, values_by_id_map=schema_path_values_map
                    )
                    await update_attribute_values_query.execute(db=db)

                    offset += self.display_label_batch_size

                    progress.update(update_task, advance=len(schema_path_values_map))

        return MigrationResult(errors=["this is a pretend error"])


params = {
    "branch": "branch1",
}
identify_changed_nodes_query = """
MATCH (n:%(schema_kind)s)-[e:IS_PART_OF]->(:Root)
WHERE e.branch = $branch
AND e.status = "active"
AND e.to IS NULL
AND NOT exists((n)-[:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root))

MATCH
"""
