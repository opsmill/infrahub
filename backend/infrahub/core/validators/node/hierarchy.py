from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import NodeSchema

from ..interface import ConstraintCheckerInterface
from ..shared import SchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeHierarchyUpdateValidatorQuery(SchemaValidatorQuery):
    name = "node_constraints_hierarchy_validator"

    def __init__(
        self,
        check_children: bool = False,
        check_parent: bool = False,
        **kwargs: Any,
    ) -> None:
        self.check_children = check_children
        self.check_parent = check_parent
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        if self.check_children and self.check_parent:
            raise RuntimeError("Cannot check children and parent at same time")
        if self.check_children:
            to_children, to_parent = "<", ""
            peer_kind = getattr(self.node_schema, "children", None)
            if not peer_kind:
                raise RuntimeError(
                    f"Cannot check children for '{self.node_schema.kind}' because no children kind is defined"
                )
        elif self.check_parent:
            to_children, to_parent = "", ">"
            peer_kind = getattr(self.node_schema, "parent", None)
            if not peer_kind:
                raise RuntimeError(
                    f"Cannot check parents for '{self.node_schema.kind}' because no parent kind is defined"
                )

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        if hierarchy := getattr(self.node_schema, "hierarchy", None):
            self.params["hierarchy_kind"] = hierarchy
        else:
            raise RuntimeError(f"No 'hierarchy' defined for {self.node_schema.kind}")
        self.params["peer_kind"] = peer_kind

        # ruff: noqa: E501
        query = """
        MATCH (n:%(node_kind)s)
        CALL {
            WITH n
            MATCH path = (root:Root)<-[rroot:IS_PART_OF]-(n)
            WHERE all(r in relationships(path) WHERE %(branch_filter)s)
            RETURN path as full_path, n as active_node
            ORDER BY rroot.branch_level DESC, rroot.from DESC
            LIMIT 1
        }
        WITH full_path, active_node
        WITH full_path, active_node
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        CALL {
            WITH active_node
            MATCH path = (active_node)%(to_children)s-[hrel1:IS_RELATED]-%(to_parent)s(:Relationship {name: "parent__child"})%(to_children)s-[hrel2:IS_RELATED]-%(to_parent)s(peer:Node)
            WHERE all(
                r in relationships(path)
                WHERE (%(branch_filter)s)
            )
            RETURN
                path as hierarchy_path,
                active_node as start_node,
                peer as peer_node,
                hrel1.branch_level + hrel2.branch_level AS branch_level_sum,
                [hrel1.from, hrel2.from] as from_times,
                // used as tiebreaker for updated relationships that were deleted and added at the same microsecond
                reduce(active_count = 0, r in relationships(path) | active_count + (CASE r.status WHEN "active" THEN 1 ELSE 0 END)) AS active_relationship_count,
                (CASE WHEN hrel1.branch_level > hrel2.branch_level THEN hrel1.branch ELSE hrel2.branch END) as deepest_branch_name
        }
        WITH
            collect([branch_level_sum, from_times, active_relationship_count, hierarchy_path, deepest_branch_name]) as enriched_paths,
            start_node,
            peer_node
        CALL {
            WITH enriched_paths, peer_node
            UNWIND enriched_paths as path_to_check
            RETURN path_to_check[3] as current_path, path_to_check[4] as branch_name, peer_node as current_peer
            ORDER BY
                path_to_check[0] DESC,
                path_to_check[1][1] DESC,
                path_to_check[1][0] DESC,
                path_to_check[2] DESC
            LIMIT 1
        }
        WITH
            start_node,
            current_peer,
            branch_name,
            current_path
        WITH start_node, current_peer, branch_name, current_path
        WHERE all(r in relationships(current_path) WHERE r.status = "active")
        AND (
            any(r in relationships(current_path) WHERE r.hierarchy <> $hierarchy_kind)
            OR NOT ($peer_kind IN labels(current_peer))
        )
        """ % {
            "branch_filter": branch_filter,
            "to_children": to_children,
            "to_parent": to_parent,
            "node_kind": self.node_schema.kind,
        }

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
                    field_name="children" if self.check_children else "parent",
                    peer_id=str(result.get("current_peer.uuid")),
                    kind=self.node_schema.kind,
                )
            )

        return grouped_data_paths


class NodeHierarchyChecker(ConstraintCheckerInterface):
    query_classes = [NodeHierarchyUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.hierarchy.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in ("node.parent.update", "node.children.update")

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []

        if not isinstance(request.node_schema, NodeSchema):
            return grouped_data_paths_list
        if request.constraint_name == "node.parent.update" and not request.node_schema.parent:
            return grouped_data_paths_list
        if request.constraint_name == "node.children.update" and not request.node_schema.children:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                check_children=request.constraint_name == "node.children.update",
                check_parent=request.constraint_name == "node.parent.update",
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
