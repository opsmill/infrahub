from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.utils import compare_lists

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import MainSchemaTypes, NodeSchema
from infrahub.exceptions import SchemaNotFoundError

from ..interface import ConstraintCheckerInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeInheritFromChecker(ConstraintCheckerInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
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
        current_inherit_from_ids = {
            g.id: g.kind
            for g in [
                self.db.schema.get(name=n, branch=request.branch, duplicate=False) for n in current_schema.inherit_from
            ]
        }

        # Gather IDs for each inherited node in use for candidate schema
        request_inherited: list[MainSchemaTypes] = []
        for n in request.node_schema.inherit_from:
            try:
                schema = request.schema_branch.get(name=n, duplicate=False)
            except SchemaNotFoundError:
                schema = self.db.schema.get(name=n, branch=request.branch, duplicate=False)
            request_inherited.append(schema)
        request_inherit_from_ids = {g.id: g.kind for g in request_inherited}

        # Compare IDs to find out if some inherited nodes were removed
        # Comparing IDs helps us in understanding if a node was renamed or really removed
        _, removed_ids, _ = compare_lists(
            list1=list(current_inherit_from_ids.keys()), list2=list(request_inherit_from_ids.keys())
        )
        if removed := [current_inherit_from_ids[k] for k in removed_ids]:
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
