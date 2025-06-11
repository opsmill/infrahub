from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import PathType, RelationshipKind
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import GenericSchema

from ..interface import ConstraintCheckerInterface
from ..shared import RelationshipSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class RelationshipPeerUpdateValidatorQuery(RelationshipSchemaValidatorQuery):
    name = "relationship_constraints_peer_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        peer_schema = db.schema.get(name=self.relationship_schema.peer, branch=self.branch)
        allowed_peer_kinds = [peer_schema.kind]
        if isinstance(peer_schema, GenericSchema):
            allowed_peer_kinds += peer_schema.used_by

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        self.params["relationship_id"] = self.relationship_schema.identifier
        self.params["allowed_peer_kinds"] = allowed_peer_kinds

        # ruff: noqa: E501
        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (root:Root)<-[rroot:IS_PART_OF]-(n)
            WHERE all(r in relationships(path) WHERE %(branch_filter)s)
            RETURN path as full_path, n as active_node
            ORDER BY rroot.branch_level DESC, rroot.from DESC
            LIMIT 1
        }
        WITH full_path, active_node
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        CALL (active_node) {
            MATCH path = (active_node)-[rrel1:IS_RELATED]-(rel:Relationship { name: $relationship_id })-[rrel2:IS_RELATED]-(peer:Node)
            WHERE all(
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
                (CASE WHEN rrel1.branch_level > rrel2.branch_level THEN rrel1.branch ELSE rrel2.branch END) as deepest_branch_name
        }
        WITH
            collect([branch_level_sum, from_times, active_relationship_count, relationship_path, deepest_branch_name]) as enriched_paths,
            start_node,
            peer_node
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
        WITH start_node, current_peer, branch_name, current_path
        WHERE all(r in relationships(current_path) WHERE r.status = "active")
        AND NOT any(label IN LABELS(current_peer) WHERE label IN $allowed_peer_kinds)
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["start_node.uuid", "branch_name", "current_peer.uuid"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("branch_name")),
                    path_type=PathType.NODE,
                    node_id=str(result.get("start_node.uuid")),
                    field_name=self.relationship_schema.name,
                    peer_id=str(result.get("current_peer.uuid")),
                    kind=self.node_schema.kind,
                )
            )

        return grouped_data_paths


class RelationshipPeerChecker(ConstraintCheckerInterface):
    query_classes = [RelationshipPeerUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "relationship.peer.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list


class RelationshipPeerParentValidatorQuery(RelationshipSchemaValidatorQuery):
    name = "relationship_constraints_peer_parent_validator"

    def __init__(
        self,
        relationship: RelationshipSchema,
        parent_relationship: RelationshipSchema,
        peer_parent_relationship: RelationshipSchema,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)

        self.relationship = relationship
        self.parent_relationship = parent_relationship
        self.peer_parent_relationship = peer_parent_relationship

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        self.params["peer_relationship_id"] = self.relationship.identifier
        self.params["parent_relationship_id"] = self.parent_relationship.identifier
        self.params["peer_parent_relationship_id"] = self.peer_parent_relationship.identifier

        parent_arrows = self.parent_relationship.get_query_arrows()
        parent_match = (
            "MATCH (active_node)%(lstart)s[r1:IS_RELATED]%(lend)s"
            "(rel:Relationship { name: $parent_relationship_id })%(rstart)s[r2:IS_RELATED]%(rend)s(parent:Node)"
        ) % {
            "lstart": parent_arrows.left.start,
            "lend": parent_arrows.left.end,
            "rstart": parent_arrows.right.start,
            "rend": parent_arrows.right.end,
        }

        peer_parent_arrows = self.relationship.get_query_arrows()
        peer_match = (
            "MATCH (active_node)%(lstart)s[r1:IS_RELATED]%(lend)s"
            "(r:Relationship {name: $peer_relationship_id })%(rstart)s[r2:IS_RELATED]%(rend)s(peer:Node)"
        ) % {
            "lstart": peer_parent_arrows.left.start,
            "lend": peer_parent_arrows.left.end,
            "rstart": peer_parent_arrows.right.start,
            "rend": peer_parent_arrows.right.end,
        }

        peer_parent_arrows = self.peer_parent_relationship.get_query_arrows()
        peer_parent_match = (
            "MATCH (peer:Node)%(lstart)s[r1:IS_RELATED]%(lend)s"
            "(r:Relationship {name: $peer_parent_relationship_id})%(rstart)s[r2:IS_RELATED]%(rend)s(peer_parent:Node)"
        ) % {
            "lstart": peer_parent_arrows.left.start,
            "lend": peer_parent_arrows.left.end,
            "rstart": peer_parent_arrows.right.start,
            "rend": peer_parent_arrows.right.end,
        }

        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN n as active_node, r.status = "active" AS is_active
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, is_active
        WHERE is_active = TRUE
        %(parent_match)s
        WHERE all(r in [r1, r2] WHERE %(branch_filter)s AND r.status = "active")
        CALL (active_node) {
            %(peer_match)s
            WITH DISTINCT active_node, peer
            %(peer_match)s
            WHERE all(r in [r1, r2] WHERE %(branch_filter)s)
            WITH peer, r1.status = "active" AND r2.status = "active" AS is_active
            ORDER BY peer.uuid, r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC, is_active DESC
            WITH peer, head(collect(is_active)) AS is_active
            WHERE is_active = TRUE
            RETURN peer
        }
        CALL (peer) {
            %(peer_parent_match)s
            WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
            WITH peer_parent, r1, r2, r1.status = "active" AND r2.status = "active" AS is_active
            WITH peer_parent, r1.branch AS branch_name, is_active
            ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC, is_active DESC
            LIMIT 1
            WITH peer_parent, branch_name
            WHERE is_active = TRUE
            RETURN peer_parent, branch_name
        }
        WITH DISTINCT active_node, parent, peer, peer_parent, branch_name
        WHERE parent.uuid <> peer_parent.uuid
        """ % {
            "branch_filter": branch_filter,
            "node_kind": self.node_schema.kind,
            "parent_match": parent_match,
            "peer_match": peer_match,
            "peer_parent_match": peer_parent_match,
        }

        self.add_to_query(query)
        self.return_labels = ["active_node.uuid", "parent.uuid", "peer.uuid", "peer_parent.uuid", "branch_name"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()

        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("branch_name")),
                    path_type=PathType.RELATIONSHIP_ONE,
                    node_id=str(result.get("peer.uuid")),
                    field_name=self.peer_parent_relationship.name,
                    peer_id=str(result.get("peer_parent.uuid")),
                    kind=self.relationship.peer,
                )
            )

        return grouped_data_paths


class RelationshipPeerParentChecker(ConstraintCheckerInterface):
    query_classes = [RelationshipPeerParentValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "relationship.common_parent.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name and config.SETTINGS.main.schema_strict_mode

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []

        if not request.schema_path.field_name:
            return grouped_data_paths_list

        relationship = request.node_schema.get_relationship(name=request.schema_path.field_name)
        if not relationship.common_parent:
            # Should not happen if schema validation was done properly
            return grouped_data_paths_list

        parent_relationship = next(
            iter(request.node_schema.get_relationships_of_kind(relationship_kinds=[RelationshipKind.PARENT]))
        )
        peer_parent_relationship = request.schema_branch.get(name=relationship.peer, duplicate=False).get_relationship(
            name=relationship.common_parent
        )

        for query_class in self.query_classes:
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                relationship=relationship,
                parent_relationship=parent_relationship,
                peer_parent_relationship=peer_parent_relationship,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())

        return grouped_data_paths_list
