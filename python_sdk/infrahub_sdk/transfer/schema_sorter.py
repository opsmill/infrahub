from collections import defaultdict
from typing import Dict, List, Sequence, Set

from infrahub_sdk.schema import BaseNodeSchema

from ..topological_sort import DependencyCycleExists, topological_sort
from .exceptions import SchemaImportError


class InfrahubSchemaTopologicalSorter:
    async def get_sorted_node_schema(
        self, schemas: Sequence[BaseNodeSchema], required_relationships_only: bool = True
    ) -> List[Set[str]]:
        relationship_graph: Dict[str, Set[str]] = defaultdict(set)
        for node_schema in schemas:
            for relationship_schema in node_schema.relationships:
                if required_relationships_only and relationship_schema.optional:
                    continue
                relationship_graph[node_schema.kind].add(relationship_schema.peer)

        try:
            return topological_sort(relationship_graph)
        except DependencyCycleExists:
            raise SchemaImportError(
                "Cannot import nodes. There are cycles in the dependency graph."
            ) from DependencyCycleExists
