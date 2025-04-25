from dataclasses import dataclass
from typing import Any

from infrahub.database import InfrahubDatabase


@dataclass
class DbNode:
    db_id: str
    labels: set[str]
    properties: dict[str, Any]

    def __hash__(self) -> int:
        cumulative_hash = hash(frozenset(self.labels))
        for k, v in self.properties.items():
            cumulative_hash += hash(k)
            cumulative_hash += hash(v)
        return hash(cumulative_hash)


@dataclass
class DbEdge:
    db_id: str
    from_db_id: str
    to_db_id: str
    edge_type: str
    properties: dict[str, Any]

    def __hash__(self) -> int:
        labels_hash = hash(self.edge_type)
        cumulative_hash = 0
        for k, v in self.properties.items():
            cumulative_hash += hash(k)
            cumulative_hash += hash(v)
        return hash(f"{labels_hash}:{cumulative_hash}")


@dataclass
class DbSnapshot:
    node_map: dict[int, DbNode]
    edge_map: dict[int, DbEdge]

    def __hash__(self) -> int:
        summed_node_hash = sum(self.node_map.keys())
        summed_edge_hash = sum(self.edge_map.keys())
        return hash(f"{summed_node_hash}:{summed_edge_hash}")


class DbSnapshotter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def snapshot(self) -> DbSnapshot:
        node_query = """MATCH (n) RETURN n"""
        results = await self.db.execute_query(query=node_query)
        node_map = {}
        node_hashes_by_db_id: dict[str, int] = {}
        for result in results:
            n = result.get("n")
            db_node = DbNode(db_id=n.element_id, labels=n.labels, properties=dict(n.items()))
            node_hash = hash(db_node)
            node_map[node_hash] = db_node
            node_hashes_by_db_id[db_node.db_id] = node_hash
        edge_query = """MATCH (a)-[e]->(b) RETURN a, e, b"""
        results = await self.db.execute_query(query=edge_query)
        edge_map = {}
        for result in results:
            from_n = result.get("a")
            from_n_db_id = from_n.element_id
            from_n_hash = node_hashes_by_db_id[from_n_db_id]
            to_n = result.get("b")
            to_n_db_id = to_n.element_id
            to_n_hash = node_hashes_by_db_id[to_n_db_id]
            edge = result.get("e")
            db_edge = DbEdge(
                db_id=edge.element_id,
                from_db_id=from_n_db_id,
                to_db_id=to_n_db_id,
                edge_type=edge.type,
                properties=(dict(edge.items())),
            )
            edge_only_hash = hash(db_edge)
            full_edge_hash = hash(f"{from_n_hash}:{edge_only_hash}:{to_n_hash}")
            edge_map[full_edge_hash] = db_edge
        return DbSnapshot(node_map=node_map, edge_map=edge_map)
