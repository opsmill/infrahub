from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from .shared import SchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class NodeNotPresentValidatorQuery(SchemaValidatorQuery):
    name: str = "node_not_present_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (root:Root)<-[rr:IS_PART_OF]-(n)
            WHERE all(
                r in relationships(path)
                WHERE %(branch_filter)s
            )
            RETURN path as full_path, n as node, rr as root_relationship
            ORDER BY rr.branch_level DESC, rr.from DESC
            LIMIT 1
        }
        WITH full_path, node, root_relationship
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "root_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("root_relationship").get("branch")),
                    path_type=PathType.NODE,
                    node_id=str(result.get("node.uuid")),
                    kind=self.node_schema.kind,
                ),
            )

        return grouped_data_paths
