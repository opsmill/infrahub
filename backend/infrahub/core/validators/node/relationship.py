from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import RelationshipSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeRelationshipMissingValidatorQuery(RelationshipSchemaValidatorQuery):
    """Find the active nodes of the kind that have no active edge to a vertex of the relationship.

    Each relationship vertex is resolved on its own because the latest edge across all of them can be a deleted one
    while another peer is still active.
    """

    name: str = "node_relationship_missing_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), is_isolated=self.is_isolated
        )
        self.params.update(branch_params)

        self.params["relationship_id"] = self.relationship_schema.get_identifier()
        arrows = self.get_query_arrows(direction=self.relationship_schema.direction)

        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (:Root)<-[rr:IS_PART_OF]-(n)
            WHERE all(
                r in relationships(path)
                WHERE %(branch_filter)s
            )
            RETURN rr.branch AS root_branch, rr.status AS root_status
            ORDER BY rr.branch_level DESC, rr.from DESC, rr.status ASC
            LIMIT 1
        }
        WITH n, root_branch, root_status
        WHERE root_status = "active"
        CALL (n) {
            MATCH (n)%(lstart)s[:IS_RELATED]%(lend)s(rel:Relationship { name: $relationship_id })
            WITH DISTINCT rel
            CALL (n, rel) {
                MATCH (n)%(lstart)s[r:IS_RELATED]%(lend)s(rel)
                WHERE %(branch_filter)s
                RETURN r.status AS edge_status
                ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
                LIMIT 1
            }
            RETURN count(CASE WHEN edge_status = "active" THEN 1 END) AS nbr_active_edges
        }
        WITH n, root_branch, nbr_active_edges
        WHERE nbr_active_edges = 0
        """ % {
            "branch_filter": branch_filter,
            "node_kind": self.node_schema.kind,
            "lstart": arrows.left.start,
            "lend": arrows.left.end,
        }

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "root_branch"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("root_branch")),
                    path_type=PathType.NODE,
                    node_id=str(result.get("n.uuid")),
                    kind=self.node_schema.kind,
                ),
            )

        return grouped_data_paths


class NodeRelationshipAddChecker(ConstraintCheckerInterface):
    query_classes = [NodeRelationshipMissingValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.relationship.add"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        rel_schema = request.node_schema.get_relationship(name=request.schema_path.field_name)
        if rel_schema.optional is True:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                is_isolated=request.is_isolated,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
