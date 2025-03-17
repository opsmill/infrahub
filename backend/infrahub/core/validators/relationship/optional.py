from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import (
    RelationshipSchemaValidatorQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class RelationshipOptionalUpdateValidatorQuery(RelationshipSchemaValidatorQuery):
    name = "relationship_constraints_optional_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        self.params["relationship_id"] = self.relationship_schema.identifier

        query = """
        // Query all Active Nodes of type
        // and store their UUID in uuids_active_node
        MATCH (n:%(node_kind)s)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, n
        WHERE rb.status = "active"
        WITH COLLECT(active_node.uuid) AS uuids_active_node
        // identifier all nodes with at least one active member for this relationship
        // and store their UUID in uuids_with_rel
        MATCH (n:%(node_kind)s)
        CALL {
            WITH n, uuids_active_node
            MATCH path = (n)-[r:IS_RELATED]-(:Relationship { name: $relationship_id })
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as node_with_rel, r1 as r, uuids_active_node
        WHERE r.status = "active"
        WITH COLLECT(node_with_rel.uuid) AS uuids_with_rel, uuids_active_node
        MATCH (n:%(node_kind)s)-[r:IS_PART_OF]->(:Root)
        WHERE n.uuid IN uuids_active_node
          AND not n.uuid IN uuids_with_rel
          AND NOT exists((n)-[:IS_RELATED]-(:Relationship { name: $relationship_id }))
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "r as root_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=result.get("root_relationship").get("branch"),
                    path_type=PathType.NODE,
                    node_id=str(result.get("n.uuid")),
                    kind=self.node_schema.kind,
                )
            )

        return grouped_data_paths


class RelationshipOptionalChecker(ConstraintCheckerInterface):
    query_classes = [RelationshipOptionalUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "relationship.optional.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        relationship_schema = request.node_schema.get_relationship(name=request.schema_path.field_name)
        if relationship_schema.optional is True:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
