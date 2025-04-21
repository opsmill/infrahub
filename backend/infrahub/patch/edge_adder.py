from collections import defaultdict
from dataclasses import asdict

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import EdgeToAdd


class PatchPlanEdgeAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, edge_type: str, edges_to_add: list[EdgeToAdd]) -> dict[str, str]:
        all_prop_keys: set[str] = set()
        for e_to_add in edges_to_add:
            all_prop_keys |= set(e_to_add.after_props.keys())

        cypher_variable_map = "{" + ",".join([f"{p}: edge_to_add.after_props.{p}" for p in all_prop_keys]) + "}"
        query = """
UNWIND $edges_to_add AS edge_to_add
MATCH (a) WHERE %(id_func_name)s(a) = edge_to_add.from_id
MATCH (b) WHERE %(id_func_name)s(b) = edge_to_add.to_id
MERGE (a)-[e:%(edge_type)s %(cypher_variable_map)s]->(b)
RETURN edge_to_add.identifier AS abstract_id, %(id_func_name)s(e) AS db_id
        """ % {
            "edge_type": edge_type,
            "cypher_variable_map": cypher_variable_map,
            "id_func_name": self.db.get_id_function_name(),
        }
        edges_to_add_dicts = [asdict(v) for v in edges_to_add]
        results, _ = await self.db.execute_query_with_metadata(
            query=query, params={"edges_to_add": edges_to_add_dicts}, type=QueryType.WRITE
        )
        abstract_to_concrete_id_map: dict[str, str] = {}
        for result in results:
            abstract_id = result.get("abstract_id")
            concrete_id = result.get("db_id")
            abstract_to_concrete_id_map[abstract_id] = concrete_id
        return abstract_to_concrete_id_map

    async def execute(
        self,
        edges_to_add: list[EdgeToAdd],
    ) -> dict[str, str]:
        edges_map_queue: dict[str, list[EdgeToAdd]] = defaultdict(list)
        abstract_to_concrete_id_map: dict[str, str] = {}
        for edge_to_add in edges_to_add:
            edges_map_queue[edge_to_add.edge_type].append(edge_to_add)
            if len(edges_map_queue[edge_to_add.edge_type]) > self.batch_size_limit:
                abstract_to_concrete_id_map.update(
                    await self._run_add_query(
                        edge_type=edge_to_add.edge_type,
                        edges_to_add=edges_map_queue[edge_to_add.edge_type],
                    )
                )
                edges_map_queue[edge_to_add.edge_type] = []

        for edge_type, edges_group in edges_map_queue.items():
            abstract_to_concrete_id_map.update(await self._run_add_query(edge_type=edge_type, edges_to_add=edges_group))
        return abstract_to_concrete_id_map
