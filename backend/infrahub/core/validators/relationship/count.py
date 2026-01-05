from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType, RelationshipCardinality
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import (
    RelationshipSchemaValidatorQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class RelationshipCountUpdateValidatorQuery(RelationshipSchemaValidatorQuery):
    name = "relationship_constraints_count_validator"

    def __init__(
        self,
        min_count_override: int | None = None,
        max_count_override: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.min_count_override = min_count_override
        self.max_count_override = max_count_override
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        self.params["relationship_id"] = self.relationship_schema.identifier
        self.params["relationship_direction"] = self.relationship_schema.direction.value
        self.params["min_count"] = (
            self.min_count_override if self.min_count_override is not None else self.relationship_schema.min_count
        )
        max_count: int | None = self.relationship_schema.max_count
        if self.max_count_override:
            max_count = self.max_count_override
        if max_count == 0:
            max_count = None
        self.params["max_count"] = max_count

        # ruff: noqa: E501
        query = """
        // get the nodes on these branches nodes
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (root:Root)<-[rroot:IS_PART_OF]-(n)
            WHERE all(r in relationships(path) WHERE %(branch_filter)s)
            RETURN path as full_path, n as active_node
            ORDER BY rroot.branch_level DESC, rroot.from DESC
            LIMIT 1
        }
        // filter to only the active nodes
        WITH full_path, active_node
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        // get the relationships using the given identifier for each node
        CALL (active_node) {
            MATCH path = (active_node)-[rrel1:IS_RELATED]-(rel:Relationship { name: $relationship_id })-[rrel2:IS_RELATED]-(peer:Node)
            WHERE ($relationship_direction <> "outbound" OR (startNode(rrel1) = active_node AND startNode(rrel2) = rel))
            AND ($relationship_direction <> "inbound" OR (startNode(rrel1) = rel AND startNode(rrel2) = peer))
            AND all(
                r in relationships(path)
                WHERE (%(branch_filter)s)
            )
            RETURN
                path as relationship_path,
                active_node as start_node,
                peer as peer_node,
                rrel1.branch_level + rrel2.branch_level AS branch_level_sum,
                [rrel1.from, rrel2.from] as from_times,
                // used as tiebreaker for updated relationships that were deleted and added at the same microsecond
                reduce(active_count = 0, r in relationships(path) | active_count + (CASE r.status WHEN "active" THEN 1 ELSE 0 END)) AS active_relationship_count,
                rrel1.branch as node_branch_name
        }
        WITH
            collect([branch_level_sum, from_times, active_relationship_count, relationship_path, node_branch_name]) as enriched_paths,
            start_node,
            peer_node
        // make sure to only use the latest version of this particular path
        CALL (enriched_paths, peer_node) {
            UNWIND enriched_paths as path_to_check
            RETURN path_to_check[3] as current_path, path_to_check[4] as branch_name, peer_node as current_peer
            ORDER BY
                path_to_check[0] DESC,
                path_to_check[1][1] DESC,
                path_to_check[1][0] DESC,
                path_to_check[2] DESC
            LIMIT 1
        }
        // filter to only the current active paths
        WITH collect([current_peer, current_path]) as peers_and_paths, start_node, branch_name
        CALL (peers_and_paths) {
            UNWIND peers_and_paths AS peer_and_path
            WITH peer_and_path
            WHERE all(r in relationships(peer_and_path[1]) WHERE r.status = "active")
            RETURN count(peer_and_path[0]) as num_relationships_on_branch
        }
        // sum all the relationships across branches and identify the violators
        WITH collect([branch_name, num_relationships_on_branch]) as branches_and_counts, start_node
        CALL (start_node, branches_and_counts) {
            WITH reduce(rel_total = 0, bnc in branches_and_counts | rel_total + bnc[1]) AS total_relationships_count
            WHERE
                (toInteger($min_count) IS NOT NULL AND total_relationships_count < toInteger($min_count))
                OR (toInteger($max_count) IS NOT NULL AND total_relationships_count > toInteger($max_count))
            RETURN start_node as violation_node, branches_and_counts as violation_branches_and_counts
        }
        // return a row for each node-branch combination with a count for that branch
        UNWIND violation_branches_and_counts as violation_branch_and_count
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = [
            "start_node.uuid as node_uuid",
            "violation_branch_and_count[0] as branch_name",
            "violation_branch_and_count[1] as num_relationships",
        ]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            node_id = str(result.get("node_uuid"))
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("branch_name")),
                    path_type=PathType.NODE,
                    node_id=node_id,
                    field_name=self.relationship_schema.name,
                    kind=self.node_schema.kind,
                    value=result.get("num_relationships"),
                ),
                grouping_key=node_id,
            )

        return grouped_data_paths


class RelationshipCountChecker(ConstraintCheckerInterface):
    query_classes = [RelationshipCountUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "relationship.count.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in (
            "relationship.min_count.update",
            "relationship.max_count.update",
            "relationship.cardinality.update",
        )

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        relationship_schema = request.node_schema.get_relationship(name=request.schema_path.field_name)
        min_count_override, max_count_override = None, None
        if request.constraint_name == "relationship.cardinality.update":
            if relationship_schema.cardinality == RelationshipCardinality.ONE:
                max_count_override = 1
                min_count_override = 0 if relationship_schema.optional else 1
            else:
                return grouped_data_paths_list

        elif not (relationship_schema.min_count or relationship_schema.max_count):
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                min_count_override=min_count_override,
                max_count_override=max_count_override,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
