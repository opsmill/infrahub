import asyncio
from collections import defaultdict
from itertools import chain
from typing import Iterable, List, Optional

from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase

from .model import NonUniqueNodeAttribute, SchemaUniquenessCheckRequest


class UniquenessChecker:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def get_conflicts(
        self,
        schemas: Iterable[SchemaUniquenessCheckRequest],
        source_branch_name: str,
        dest_branch_name: str,
        ids_to_ignore: Optional[Iterable[str]] = None,
    ) -> List[NonUniqueNodeAttribute]:
        non_unique_nodes_lists = await asyncio.gather(
            *[self.check_one_schema(schema, source_branch_name, dest_branch_name, ids_to_ignore) for schema in schemas]
        )
        return chain(*non_unique_nodes_lists)

    async def check_one_schema(
        self,
        schema_to_validate: SchemaUniquenessCheckRequest,
        source_branch_name: str,
        dest_branch_name: str,
        ids_to_ignore: Optional[Iterable[str]] = None,
    ) -> List[NonUniqueNodeAttribute]:
        unique_attribute_names = {attr.name for attr in schema_to_validate.schema.unique_attributes}
        if schema_to_validate.attributes:
            fields_to_validate = set(schema_to_validate.attributes) & unique_attribute_names
        else:
            fields_to_validate = unique_attribute_names
        source_nodes = await NodeManager.query(
            db=self.db,
            schema=schema_to_validate.schema,
            fields={name: None for name in fields_to_validate},
            branch=source_branch_name,
        )
        dest_nodes = await NodeManager.query(
            db=self.db,
            schema=schema_to_validate.schema,
            fields={name: None for name in fields_to_validate},
            branch=dest_branch_name,
        )
        if ids_to_ignore:
            dest_nodes = [node for node in dest_nodes if node.id not in ids_to_ignore]

        all_attribute_value_maps = {attribute_name: defaultdict(list) for attribute_name in fields_to_validate}
        for node in source_nodes + dest_nodes:
            for attribute_name in fields_to_validate:
                attribute_value = getattr(node, attribute_name, None)
                if attribute_value:
                    all_attribute_value_maps[attribute_name][attribute_value.value].append(node)

        non_unique_nodes = []
        for attribute_name, attribute_value_map in all_attribute_value_maps.items():
            for attribute_value, nodes in attribute_value_map.items():
                if len(nodes) <= 1:
                    continue
                non_unique_nodes.append(
                    NonUniqueNodeAttribute(nodes=nodes, attribute_name=attribute_name, attribute_value=attribute_value)
                )
        return non_unique_nodes
