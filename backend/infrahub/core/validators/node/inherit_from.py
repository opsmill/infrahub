from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub_sdk.utils import compare_lists

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import NodeSchema

from ..interface import ConstraintCheckerInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeInheritFromChecker(ConstraintCheckerInterface):
    def __init__(self, db: InfrahubDatabase, branch: Optional[Branch] = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.inherit_from.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        group_data_path = GroupedDataPaths()

        current_schema = self.db.schema.get_node_schema(
            name=request.node_schema.kind, branch=request.branch, duplicate=False
        )

        if not isinstance(request.node_schema, NodeSchema):
            return grouped_data_paths_list

        _, removed, _ = compare_lists(list1=current_schema.inherit_from, list2=request.node_schema.inherit_from)

        if removed:
            group_data_path.add_data_path(
                DataPath(
                    branch=str(request.branch.name),
                    path_type=PathType.NODE,
                    node_id=str(request.node_schema.id),
                    field_name="inherit_from",
                    kind="SchemaNode",
                    value=removed,
                )
            )

            grouped_data_paths_list.append(group_data_path)

        return grouped_data_paths_list
