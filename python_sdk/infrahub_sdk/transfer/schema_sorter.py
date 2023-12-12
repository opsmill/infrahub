from collections import defaultdict
from typing import List

import igraph as ig

from infrahub_sdk.schema import GenericSchema, InfrahubSchema

from .exceptions import SchemaImportError


class InfrahubSchemaTopologicalSorter:
    async def get_sorted_node_schema(self, schema: InfrahubSchema, branch: str) -> List[str]:
        node_schema_map = await schema.all(branch=branch)
        vertices = set()
        edges = defaultdict(set)
        for node_schema in node_schema_map.values():
            if isinstance(node_schema, GenericSchema):
                continue
            vertices.add(node_schema.name)
            for relationship_schema in node_schema.relationships:
                edges[node_schema.name].add(relationship_schema.peer)
                vertices.add(relationship_schema.peer)

        graph = ig.Graph(directed=True)
        edge_tuples = [(from_v, to_v) for from_v, to_vs in edges.items() for to_v in to_vs]

        graph.add_vertices(list(vertices))
        graph.add_edges(edge_tuples)
        if not graph.is_dag():
            raise SchemaImportError("Cannot import nodes. There are cycles in the dependency graph.")

        ordered_indices = graph.topological_sorting(mode="in")
        ordered_schema_names = [graph.vs[ind]["name"] for ind in ordered_indices]

        return ordered_schema_names
