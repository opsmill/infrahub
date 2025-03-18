from __future__ import annotations

from typing import TYPE_CHECKING

from ..interface import ConstraintCheckerInterface
from ..query import NodeNotPresentValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.path import GroupedDataPaths
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeAttributeAddChecker(ConstraintCheckerInterface):
    query_classes = [NodeNotPresentValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.attribute.add"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.optional is True or attribute_schema.default_value is not None:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
