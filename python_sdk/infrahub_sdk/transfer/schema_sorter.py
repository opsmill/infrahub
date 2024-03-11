from typing import Dict, List, Optional, Sequence, Set

from infrahub_sdk.schema import BaseNodeSchema

from ..topological_sort import DependencyCycleExistsError, topological_sort
from .exceptions import SchemaImportError


class InfrahubSchemaTopologicalSorter:
    def get_sorted_node_schema(
        self,
        schemas: Sequence[BaseNodeSchema],
        required_relationships_only: bool = True,
        include: Optional[List[str]] = None,
    ) -> List[Set[str]]:
        relationship_graph: Dict[str, Set[str]] = {}
        for node_schema in schemas:
            if include and node_schema.kind not in include:
                continue
            relationship_graph[node_schema.kind] = set()
            for relationship_schema in node_schema.relationships:
                if required_relationships_only and relationship_schema.optional:
                    continue
                relationship_graph[node_schema.kind].add(relationship_schema.peer)

        try:
            return topological_sort(relationship_graph)
        except DependencyCycleExistsError:
            raise SchemaImportError(
                "Cannot import nodes. There are cycles in the dependency graph."
            ) from DependencyCycleExistsError
