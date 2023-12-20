from collections import defaultdict
from typing import Dict, List, Set

from toposort import CircularDependencyError, toposort

from infrahub_sdk.schema import BaseNodeSchema

from .exceptions import SchemaImportError


class InfrahubSchemaTopologicalSorter:
    async def get_sorted_node_schema(
        self, schemas: List[BaseNodeSchema], required_relationships_only: bool = True
    ) -> List[Set[str]]:
        relationship_graph: Dict[str, Set[str]] = defaultdict(set)
        for node_schema in schemas:
            relationship_graph[node_schema.kind]
            for relationship_schema in node_schema.relationships:
                if required_relationships_only and relationship_schema.optional:
                    continue
                relationship_graph[node_schema.kind].add(relationship_schema.peer)

        try:
            return toposort(relationship_graph)
        except CircularDependencyError:
            raise SchemaImportError("Cannot import nodes. There are cycles in the dependency graph.")
