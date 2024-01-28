import asyncio
from itertools import chain
from typing import Iterable, List, Union

from build import PathType

from infrahub.core import registry
from infrahub.core.branch import ObjectConflict
from infrahub.core.query.constraints.node_unique_attributes import NodeUniqueAttributeConstraintQuery
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.database import InfrahubDatabase

from .model import NonUniqueNodeAttribute


class UniquenessChecker:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def get_conflicts(
        self,
        schemas: Iterable[Union[NodeSchema, GenericSchema]],
        source_branch_name: str,
    ) -> List[ObjectConflict]:
        non_unique_nodes_lists = await asyncio.gather(
            *[self.check_one_schema(schema, source_branch_name) for schema in schemas]
        )

        conflicts = []
        for non_unique_nodes in chain(*non_unique_nodes_lists):
            conflicts.extend(self.generate_object_conflict(non_unique_nodes))
        return conflicts

    async def check_one_schema(
        self,
        schema: Union[NodeSchema, GenericSchema],
        source_branch_name: str,
    ) -> List[NonUniqueNodeAttribute]:
        branch = await registry.get_branch(db=self.db, branch=source_branch_name)
        query = NodeUniqueAttributeConstraintQuery.init(db=self.db, branch=branch, schema=schema)

        query_results = await query.execute(db=self.db)

        return [
            NonUniqueNodeAttribute(
                schema=schema,
                node_ids=result.data["node_ids"],
                attr_name=result.data["attr_name"],
                attr_value=result.data["attr_value"],
            )
            for result in query_results
        ]

    def generate_object_conflict(self, non_unique_nodes: NonUniqueNodeAttribute) -> List[ObjectConflict]:
        return [
            ObjectConflict(
                name=f"{non_unique_nodes.schema}/{non_unique_nodes.attribute_name}",
                type="non-unique",
                kind=non_unique_nodes.schema,
                id=node_id,
                conflict_path=f"{non_unique_nodes.schema}/{non_unique_nodes.attribute_name}",
                path="path",
                path_type=PathType.NODE,
                change_type="change_type",
            )
            for node_id in non_unique_nodes.node_ids
        ]
