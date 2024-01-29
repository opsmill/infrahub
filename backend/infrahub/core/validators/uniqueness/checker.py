import asyncio
from itertools import chain
from typing import Iterable, List, Union

from infrahub.core import registry
from infrahub.core.branch import Branch, ObjectConflict
from infrahub.core.constants import PathType
from infrahub.core.query.constraints.node_unique_attributes import NodeUniqueAttributeConstraintQuery
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.database import InfrahubDatabase

from .model import NonUniqueNodeAttribute


class UniquenessChecker:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def get_conflicts(
        self,
        schemas: Iterable[Union[NodeSchema, GenericSchema, str]],
        source_branch: Union[str, Branch],
    ) -> List[ObjectConflict]:
        if isinstance(source_branch, str):
            source_branch = await registry.get_branch(db=self.db, branch=source_branch)
        schema_objects = [
            schema
            if isinstance(schema, (NodeSchema, GenericSchema))
            else registry.get_schema(schema, branch=source_branch)
            for schema in schemas
        ]

        non_unique_nodes_lists = await asyncio.gather(
            *[self.check_one_schema(schema, source_branch) for schema in schema_objects]
        )

        conflicts = []
        for non_unique_nodes in chain(*non_unique_nodes_lists):
            conflicts.extend(self.generate_object_conflict(non_unique_nodes))
        return conflicts

    async def check_one_schema(
        self,
        schema: Union[NodeSchema, GenericSchema],
        branch: Branch,
    ) -> List[NonUniqueNodeAttribute]:
        query = await NodeUniqueAttributeConstraintQuery.init(db=self.db, branch=branch, schema=schema)

        query_results = await query.execute(db=self.db)

        return [
            NonUniqueNodeAttribute(
                node_schema=schema,
                node_ids=[str(n_id) for n_id in result.get("node_ids")],
                attribute_name=str(result.get("attr_name")),
                attribute_value=str(result.get("attr_value")),
            )
            for result in query_results.get_results()
        ]

    def generate_object_conflict(self, non_unique_nodes: NonUniqueNodeAttribute) -> List[ObjectConflict]:
        return [
            # TODO: I am not super sure this is right
            ObjectConflict(
                name=f"{non_unique_nodes.node_schema.kind}/{non_unique_nodes.attribute_name}",
                type="uniqueness-violation",
                kind=non_unique_nodes.node_schema.kind,
                id=node_id,
                conflict_path=f"{non_unique_nodes.node_schema.kind}/{non_unique_nodes.attribute_name}",
                path="path",
                path_type=PathType.ATTRIBUTE,
                change_type="attribute_value",
                value=non_unique_nodes.attribute_value,
            )
            for node_id in non_unique_nodes.node_ids
        ]
