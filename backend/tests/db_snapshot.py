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
    edge_type: set
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
    node_map: dict[str, DbNode]
    edge_map: dict[str, DbEdge]

    def __hash__(self) -> int:
        summed_node_hash = 0
        node_hashes_by_db_id: dict[str, int] = {}
        for n in self.node_map.values():
            n_hash = hash(n)
            summed_node_hash += n_hash
            node_hashes_by_db_id[n.db_id] = n_hash
        summed_edge_hash = 0
        for edge in self.edge_map.values():
            edge_hash = hash(edge)
            from_node_hash = node_hashes_by_db_id[edge.from_db_id]
            to_node_hash = node_hashes_by_db_id[edge.to_db_id]
            summed_edge_hash += hash(f"{from_node_hash}:{edge_hash}:{to_node_hash}")
        return hash(f"{summed_node_hash}:{summed_edge_hash}")


class DbSnapshotter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def snapshot(self) -> DbSnapshot:
        node_query = """MATCH (n) RETURN n"""
        results = await self.db.execute_query(query=node_query)
        node_map = {}
        for result in results:
            n = result.get("n")
            db_node = DbNode(db_id=n.element_id, labels=n.labels, properties=dict(n.items()))
            node_map[db_node.db_id] = db_node
        edge_query = """MATCH (a)-[e]->(b) RETURN a, e, b"""
        results = await self.db.execute_query(query=edge_query)
        edge_map = {}
        for result in results:
            from_n = result.get("a")
            to_n = result.get("b")
            edge = result.get("e")
            edge_map[edge.element_id] = DbEdge(
                db_id=edge.element_id,
                from_db_id=from_n.element_id,
                to_db_id=to_n.element_id,
                edge_type=edge.type,
                properties=(dict(edge.items())),
            )
        return DbSnapshot(node_map=node_map, edge_map=edge_map)
