from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import (
    SchemaValidatorQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeGenerateProfileValidatorQuery(SchemaValidatorQuery):
    name = "node_constraints_generate_profile_validator"

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.profile_kind = f"Profile{self.node_schema.kind}"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)

        query = """
            MATCH (n:%(profile_kind)s)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            WITH n, r
            ORDER BY n.uuid, r.branch_level DESC, r.from DESC
            WITH n, head(collect(r)) AS latest_r
            WHERE latest_r.status = "active"
        """ % {"profile_kind": self.profile_kind, "branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["latest_r.branch AS branch_name", "n.uuid AS node_uuid"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("branch_name")),
                    path_type=PathType.NODE,
                    node_id=str(result.get("node_uuid")),
                    kind=self.profile_kind,
                )
            )

        return grouped_data_paths


class NodeGenerateProfileChecker(ConstraintCheckerInterface):
    query_classes = [NodeGenerateProfileValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.generate_profile.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []

        if getattr(request.node_schema, "generate_profile", False) is True:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
