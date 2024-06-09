from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from .model.path import ParentGraphNode, RootPath

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Path as Neo4jPath
    from neo4j.graph import Relationship as Neo4jRelationship

    from infrahub.core.query.diff import DiffAllPathsQuery


class DiffQueryParser:
    """Parses Cypher paths into Python objects that represent a diff"""

    def __init__(self, diff_query: DiffAllPathsQuery) -> None:
        self.diff_query = diff_query
        self._root_map: dict[Neo4jNode, RootPath] = {}
        self._node_to_graph_node: dict[Neo4jNode, ParentGraphNode] = {}

    def _get_root_path(self, graph_path: Neo4jPath) -> RootPath:
        root_node: Optional[Neo4jNode] = None
        for node in graph_path.nodes:
            if "Root" in node.labels:
                root_node = node
                break
        if root_node is None:
            raise RuntimeError("cannot identify Root node in path")
        if root_node not in self._root_map:
            self._root_map[root_node] = RootPath(node=root_node)
        return self._root_map[root_node]

    def _parse_path(self, graph_path: Neo4jPath) -> None:
        graph_node_paths: ParentGraphNode = self._get_root_path(graph_path=graph_path)

        relationship_map: dict[Neo4jNode, set[Neo4jRelationship]] = defaultdict(set)
        for edge in graph_path.relationships:
            if edge.start_node is None or edge.end_node is None:
                continue
            relationship_map[edge.start_node].add(edge)
            relationship_map[edge.end_node].add(edge)

        remaining_nodes = {n for n in graph_path.nodes if n is not graph_node_paths.node}
        while remaining_nodes:
            next_edge: Optional[Neo4jRelationship] = None
            next_node: Optional[Neo4jNode] = None
            for edge in relationship_map[graph_node_paths.node]:
                if edge.start_node in remaining_nodes:
                    next_edge = edge
                    next_node = edge.start_node
                elif edge.end_node in remaining_nodes:
                    next_edge = edge
                    next_node = edge.end_node
                if next_edge and next_node:
                    break
            if not (next_edge and next_node):
                break
            remaining_nodes.remove(next_node)
            if next_node in self._node_to_graph_node:
                graph_node_paths = self._node_to_graph_node[next_node]
                continue
            graph_node_paths = graph_node_paths.add_edge(edge=next_edge, other_node=next_node)
            self._node_to_graph_node[next_node] = graph_node_paths

    def parse(self) -> None:
        if not self.diff_query.has_been_executed:
            raise RuntimeError("query must be executed before indexing")

        for query_result in self.diff_query.get_results():
            paths = query_result.get_paths(label="full_diff_paths")
            for path in paths:
                self._parse_path(path)

    def get_all_root_paths(self) -> list[RootPath]:
        return list(self._root_map.values())
