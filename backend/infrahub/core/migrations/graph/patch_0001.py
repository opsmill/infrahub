import json

# consolidate duplicated nodes
from abc import ABC, abstractmethod
from asyncio import run as aiorun
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infrahub import config
from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase, get_db

query = """
MATCH (n:Node)
WITH n.uuid AS node_uuid, count(*) as num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
WITH DISTINCT node_uuid
MATCH (n:Node {uuid: node_uuid})
CALL {
    WITH n
    WITH labels(n) AS n_labels
    UNWIND n_labels AS n_label
    WITH n_label
    ORDER BY n_label ASC
    RETURN collect(n_label) AS sorted_labels
}
WITH n.uuid AS n_uuid, sorted_labels, collect(n) AS duplicate_nodes
WHERE size(duplicate_nodes) > 1
WITH n_uuid, head(duplicate_nodes) AS node_to_keep, tail(duplicate_nodes) AS nodes_to_delete
UNWIND nodes_to_delete AS node_to_delete
//------------
// Repeat for both directions of IS_RELATED
//------------
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_move:HAS_ATTRIBUTE]->(peer)
    CREATE (node_to_keep)-[new_edge:HAS_ATTRIBUTE]->(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_move:IS_RELATED]->(peer)
    CREATE (node_to_keep)-[new_edge:IS_RELATED]->(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)<-[edge_to_move:IS_RELATED]-(peer)
    CREATE (node_to_keep)<-[new_edge:IS_RELATED]-(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
DETACH DELETE node_to_delete
"""

# deduplicate edges
query = """
MATCH (node_with_dup_edges:Node)-[edge]-(peer)
WITH node_with_dup_edges, type(edge) AS edge_type, edge.status AS edge_status, edge.branch AS edge_branch, peer, count(*) AS num_dup_edges
WHERE num_dup_edges > 1
WITH DISTINCT node_with_dup_edges, edge_type, edge_branch, peer
CALL {
    WITH node_with_dup_edges, edge_type, edge_branch, peer
    MATCH (node_with_dup_edges)-[active_edge {branch: edge_branch, status: "active"}]-(peer)
    WHERE type(active_edge) = edge_type
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_edge
    ORDER BY active_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, head(collect(active_edge.from)) AS active_from
    OPTIONAL MATCH (node_with_dup_edges)-[deleted_edge {branch: edge_branch, status: "deleted"}]->(peer)
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_edge
    ORDER BY deleted_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, head(collect(deleted_edge.from)) AS deleted_from
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from
        MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from, active_e
        ORDER BY elementId(active_e)
        LIMIT 1
        SET active_e.from = active_from
        SET active_e.to = deleted_from
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH active_e
        ORDER BY elementId(active_e)
        SKIP 1
        DELETE active_e
    }
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from
        MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from, deleted_e
        ORDER BY elementId(deleted_e)
        LIMIT 1
        SET deleted_e.from = deleted_from
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH deleted_e
        ORDER BY elementId(deleted_e)
        SKIP 1
        DELETE deleted_e
    }
}
"""

# add missing IS_PART_OF edges

query = """
// nodes missing IS_PART_OF edges
MATCH (n:Node)
WHERE NOT exists((n)-[:IS_PART_OF]->(:Root))
CALL {
    WITH n
    // get each branch this node has edges on
    MATCH (n)-[e {status: "active"}]-()
    // for each branch, return the earliest active edge
    WITH DISTINCT n, active_e.branch AS branch
    MATCH (n)-[active_e {status: "active", branch: branch}]-()
    ORDER BY active_e.from ASC
    RETURN head(collect(active_e)) AS earliest_active, branch
}
CALL {
    WITH n
    // get each branch this node has edges on
    MATCH (n)-[attr_edge:HAS_ATTRIBUTE]->()
    WITH DISTINCT n, attr_edge.branch AS branch


}
"""


@dataclass
class VertexToAdd:
    identifier: str
    labels: list[str]
    after_props: dict[str, str | int | bool]


@dataclass
class VertexToUpdate:
    db_id: str
    before_props: dict[str, str | int | bool]
    after_props: dict[str, str | int | bool]


@dataclass
class VertexToDelete:
    db_id: str
    labels: str
    before_props: dict[str, str | int | bool]


@dataclass
class EdgeToAdd:
    from_id: str
    to_id: str
    edge_type: str
    after_props: dict[str, str | int | bool]


@dataclass
class EdgeToUpdate:
    db_id: str
    before_props: dict[str, str | int | bool]
    after_props: dict[str, str | int | bool]


@dataclass
class EdgeToDelete:
    db_id: str
    from_id: str
    to_id: str
    edge_type: str
    before_props: dict[str, str | int | bool]


@dataclass
class PatchPlan:
    name: str
    vertices_to_add: list[VertexToAdd] = field(default_factory=list)
    vertices_to_update: list[VertexToUpdate] = field(default_factory=list)
    vertices_to_delete: list[VertexToDelete] = field(default_factory=list)
    edges_to_add: list[EdgeToAdd] = field(default_factory=list)
    edges_to_update: list[EdgeToUpdate] = field(default_factory=list)
    edges_to_delete: list[EdgeToDelete] = field(default_factory=list)
    added_node_db_id_map: dict[str, str] = field(default_factory=dict)


class PatchQuery(ABC):
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    @abstractmethod
    async def plan(self) -> PatchPlan: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class DepduplicatePatchQuery(PatchQuery):
    @property
    def name(self) -> str:
        return "consolidate-duplicated-nodes"

    async def plan(self) -> PatchPlan:
        query = """
MATCH (n:Node)
WITH n.uuid AS node_uuid, count(*) as num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
WITH DISTINCT node_uuid
MATCH (n:Node {uuid: node_uuid})
CALL {
    WITH n
    WITH labels(n) AS n_labels
    UNWIND n_labels AS n_label
    WITH n_label
    ORDER BY n_label ASC
    RETURN collect(n_label) AS sorted_labels
}
WITH n.uuid AS n_uuid, sorted_labels, collect(n) AS duplicate_nodes
WHERE size(duplicate_nodes) > 1
WITH n_uuid, head(duplicate_nodes) AS node_to_keep, tail(duplicate_nodes) AS nodes_to_delete
UNWIND nodes_to_delete AS node_to_delete
//------------
// Repeat for both directions of IS_RELATED
//------------
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_delete]->(peer)
    RETURN {
        from_id: elementId(node_to_keep),
        to_id: elementId(peer),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
    UNION
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)<-[edge_to_delete]-(peer)
    RETURN {
        from_id: elementId(peer),
        to_id: elementId(node_to_keep),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
}
WITH node_to_delete, collect(edge_to_create) AS edges_to_create
CALL {
    WITH node_to_delete
    MATCH (node_to_delete)-[e]->(peer)
    RETURN {
        db_id: elementId(e),
        from_id: elementId(node_to_delete),
        to_id: elementId(peer),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
    UNION
    WITH node_to_delete
    MATCH (node_to_delete)<-[e]-(peer)
    RETURN {
        db_id: elementId(e),
        from_id: elementId(peer),
        to_id: elementId(node_to_delete),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
}
WITH node_to_delete, edges_to_create, collect(edge_to_delete) AS edges_to_delete
RETURN
    {db_id: elementId(node_to_delete), labels: labels(node_to_delete), before_props: properties(node_to_delete)} AS vertex_to_delete,
    edges_to_create,
    edges_to_delete
        """
        results = await self.db.execute_query(query=query)
        vertices_to_delete: list[VertexToDelete] = []
        edges_to_delete: list[EdgeToDelete] = []
        edges_to_add: list[EdgeToAdd] = []
        for result in results:
            serial_vertex_to_delete = result.get("vertex_to_delete")
            if serial_vertex_to_delete:
                vertex_to_delete = VertexToDelete(**serial_vertex_to_delete)
                vertices_to_delete.append(vertex_to_delete)
            for serial_edge_to_delete in result.get("edges_to_delete"):
                edge_to_delete = EdgeToDelete(**serial_edge_to_delete)
                edges_to_delete.append(edge_to_delete)
            for serial_edge_to_create in result.get("edges_to_create"):
                edges_to_add.append(EdgeToAdd(**serial_edge_to_create))
        return PatchPlan(
            name=self.name,
            vertices_to_delete=vertices_to_delete,
            edges_to_add=edges_to_add,
            edges_to_delete=edges_to_delete,
        )


class PatchPlanVertexAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, labels: list[str], vertices_to_add: list[VertexToAdd]) -> dict[str, str]:
        labels_str = "|".join(labels)
        query = """
UNWIND $vertices_to_add AS vertex_to_add
MERGE (v:%(labels)s vertex_to_add.after_props)
RETURN vertex_to_add.identifier AS abstract_id, elementId(v) AS db_id
        """ % {"labels": labels_str}
        results = await self.db.execute_query(
            query=query, params={"vertices_to_add": [asdict(v) for v in vertices_to_add]}
        )
        abstract_to_concrete_id_map: dict[str, str] = {}
        for result in results:
            abstract_id = result.get("abstract_id")
            concrete_id = result.get("db_id")
            abstract_to_concrete_id_map[abstract_id] = concrete_id
        return abstract_to_concrete_id_map

    async def execute(self, vertices_to_add: list[VertexToAdd]) -> dict[str, str]:
        vertices_map_queue: dict[frozenset[str], list[VertexToAdd]] = defaultdict(list)
        abstract_to_concrete_id_map: dict[str, str] = {}
        for vertex_to_add in vertices_to_add:
            frozen_labels = frozenset(vertex_to_add.labels)
            vertices_map_queue[frozen_labels].append(vertex_to_add)
            if len(vertices_map_queue[frozen_labels]) > self.batch_size_limit:
                abstract_to_concrete_id_map.update(
                    await self._run_add_query(
                        labels=list(frozen_labels), vertices_to_add=vertices_map_queue[frozen_labels]
                    )
                )
                vertices_map_queue[frozen_labels] = []

        for frozen_labels, vertices_group in vertices_map_queue.items():
            abstract_to_concrete_id_map.update(
                await self._run_add_query(labels=list(frozen_labels), vertices_to_add=vertices_group)
            )
        return abstract_to_concrete_id_map


class PatchPlanVertexDeleter:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_delete_query(self, ids_to_delete: list[str]) -> None:
        query = """
MATCH (n)
WHERE elementId(n) IN $ids_to_delete
DETACH DELETE n
        """
        await self.db.execute_query(query=query, params={"ids_to_delete": ids_to_delete})

    async def execute(self, vertices_to_delete: list[VertexToDelete]) -> None:
        for i in range(0, len(vertices_to_delete), self.batch_size_limit):
            vertices_slice = vertices_to_delete[i : i + self.batch_size_limit]
            ids_to_delete = [v.db_id for v in vertices_slice]
            await self._run_delete_query(ids_to_delete=ids_to_delete)


class PatchPlanEdgeAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, edge_type: str, edges_to_add: list[EdgeToAdd]) -> None:
        query = """
UNWIND $edges_to_add AS edge_to_add
MATCH (a) WHERE elementId(a) = edge_to_add.from_id
MATCH (b) WHERE elementId(b) = edge_to_add.to_id
CALL {
    WITH a, b, edge_to_add
    OPTIONAL MATCH (a)-[e:%(edge_type)s]->(b)
    RETURN (e IS NOT NULL AND properties(e) = edge_to_add.after_props) AS edge_exists
    ORDER BY edge_exists DESC
    LIMIT 1
}
WITH a, b, edge_to_add, edge_exists
WHERE NOT edge_exists
CREATE (a)-[new_edge:%(edge_type)s]->(b)
SET new_edge = edge_to_add.after_props
RETURN new_edge
        """ % {"edge_type": edge_type}
        edges_to_add_dicts = [asdict(v) for v in edges_to_add]

        if edge_type == "HAS_ATTRIBUTE" and any(e.to_id == "4:670dd538-711a-4602-8fac-13cf2d88711b:12463" for e in edges_to_add):
            breakpoint()

        results = await self.db.execute_query(query=query, params={"edges_to_add": edges_to_add_dicts}, type=QueryType.WRITE)
        for r in results:
            try:
                start = r.get("new_edge").end_node.element_id
            except:
                ...



    async def execute(
        self,
        edges_to_add: list[EdgeToAdd],
    ) -> None:
        edges_map_queue: dict[str, list[EdgeToAdd]] = defaultdict(list)
        for edge_to_add in edges_to_add:
            edges_map_queue[edge_to_add.edge_type].append(edge_to_add)
            if len(edges_map_queue[edge_to_add.edge_type]) > self.batch_size_limit:
                await self._run_add_query(
                    edge_type=edge_to_add.edge_type, edges_to_add=edges_map_queue[edge_to_add.edge_type]
                )
                edges_map_queue[edge_to_add.edge_type] = []

        for edge_type, edges_group in edges_map_queue.items():
            await self._run_add_query(edge_type=edge_type, edges_to_add=edges_group)


class PatchPlanEdgeDeleter:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int =1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_delete_query(self, ids_to_delete: list[str]) -> None:
        query = """
MATCH ()-[e]-()
WHERE elementId(e) IN $ids_to_delete
DELETE e
        """
        await self.db.execute_query(query=query, params={"ids_to_delete": ids_to_delete})

    async def execute(self, edges_to_delete: list[EdgeToDelete]) -> None:
        for i in range(0, len(edges_to_delete), self.batch_size_limit):
            edges_slice = edges_to_delete[i : i + self.batch_size_limit]
            ids_to_delete = [e.db_id for e in edges_slice]
            await self._run_delete_query(ids_to_delete=ids_to_delete)


class PatchPlanEdgeDbIdTranslator:
    def translate_to_db_ids(self, edges_to_add: list[EdgeToAdd], db_id_map: dict[str, str]) -> None:
        for edge_to_add in edges_to_add:
            if edge_to_add.from_id in db_id_map:
                edge_to_add.from_id = db_id_map[edge_to_add.from_id]
            if edge_to_add.to_id in db_id_map:
                edge_to_add.to_id = db_id_map[edge_to_add.to_id]


class PatchPlanWriter:
    def write(self, patches_directory: Path, patch_plan: PatchPlan) -> Path:
        timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        patch_name = f"patch-{patch_plan.name}-{timestamp_str}"
        patch_plan_directory = patches_directory / Path(patch_name)
        if not patch_plan_directory.exists():
            patch_plan_directory.mkdir(parents=True)
        if patch_plan.vertices_to_add:
            self._write_vertices_to_add(
                patch_plan_directory=patch_plan_directory, vertices_to_add=patch_plan.vertices_to_add
            )
        if patch_plan.vertices_to_delete:
            self._write_vertices_to_delete(
                patch_plan_directory=patch_plan_directory, vertices_to_delete=patch_plan.vertices_to_delete
            )
        if patch_plan.edges_to_add:
            self._write_edges_to_add(patch_plan_directory=patch_plan_directory, edges_to_add=patch_plan.edges_to_add)
        if patch_plan.edges_to_delete:
            self._write_edges_to_delete(
                patch_plan_directory=patch_plan_directory, edges_to_delete=patch_plan.edges_to_delete
            )

        return patch_plan_directory

    def write_added_db_id_map(self, patch_plan_directory: Path, db_id_map: dict[str, str]) -> None:
        file = patch_plan_directory / Path("added_db_ids.json")
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            f.write(self._to_json_line(db_id_map))

    def _to_json_line(self, obj: Any) -> str:
        return json.dumps(asdict(obj)) + "\n"

    def _write_vertices_to_add(self, patch_plan_directory: Path, vertices_to_add: list[VertexToAdd]) -> None:
        file = patch_plan_directory / Path("vertices_to_add.json")
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            for vertex_to_add in vertices_to_add:
                f.write(self._to_json_line(vertex_to_add))

    def _write_vertices_to_delete(self, patch_plan_directory: Path, vertices_to_delete: list[VertexToDelete]) -> None:
        file = patch_plan_directory / Path("vertices_to_delete.json")
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            for vertex_to_delete in vertices_to_delete:
                f.write(self._to_json_line(vertex_to_delete))

    def _write_edges_to_add(self, patch_plan_directory: Path, edges_to_add: list[EdgeToAdd]) -> None:
        file = patch_plan_directory / Path("edges_to_add.json")
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            for edge_to_add in edges_to_add:
                f.write(self._to_json_line(edge_to_add))

    def _write_edges_to_delete(self, patch_plan_directory: Path, edges_to_delete: list[EdgeToDelete]) -> None:
        file = patch_plan_directory / Path("edges_to_delete.json")
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            for edge_to_delete in edges_to_delete:
                f.write(self._to_json_line(edge_to_delete))


class PatchPlanReader:
    def read(self, patch_plan_directory: Path) -> PatchPlan:
        vertices_to_add = self._read_vertices_to_add(patch_plan_directory=patch_plan_directory)
        vertices_to_delete = self._read_vertices_to_delete(patch_plan_directory=patch_plan_directory)
        edges_to_add = self._read_edges_to_add(patch_plan_directory=patch_plan_directory)
        edges_to_delete = self._read_edges_to_delete(patch_plan_directory=patch_plan_directory)

        return PatchPlan(
            name="none",
            vertices_to_add=vertices_to_add,
            vertices_to_delete=vertices_to_delete,
            edges_to_add=edges_to_add,
            edges_to_delete=edges_to_delete,
        )

    def _read_vertices_to_add(self, patch_plan_directory: Path) -> list[VertexToAdd]:
        file = patch_plan_directory / Path("vertices_to_add.json")
        if not file.exists():
            return []
        vertices_to_add: list[VertexToAdd] = []
        with file.open() as f:
            for vertex_line in f:
                vertices_to_add.append(VertexToAdd(**json.loads(vertex_line)))
        return vertices_to_add

    def _read_vertices_to_delete(self, patch_plan_directory: Path) -> list[VertexToDelete]:
        file = patch_plan_directory / Path("vertices_to_delete.json")
        if not file.exists():
            return []
        vertices_to_delete: list[VertexToDelete] = []
        with file.open() as f:
            for vertex_line in f:
                vertices_to_delete.append(VertexToDelete(**json.loads(vertex_line)))
        return vertices_to_delete

    def _read_edges_to_add(self, patch_plan_directory: Path) -> list[EdgeToAdd]:
        file = patch_plan_directory / Path("edges_to_add.json")
        if not file.exists():
            return []
        edges_to_add: list[EdgeToAdd] = []
        with file.open() as f:
            for edge_line in f:
                edges_to_add.append(EdgeToAdd(**json.loads(edge_line)))
        return edges_to_add

    def _read_edges_to_delete(self, patch_plan_directory: Path) -> list[EdgeToDelete]:
        file = patch_plan_directory / Path("edges_to_delete.json")
        if not file.exists():
            return []
        edges_to_delete: list[EdgeToDelete] = []
        with file.open() as f:
            for edge_line in f:
                edges_to_delete.append(EdgeToDelete(**json.loads(edge_line)))
        return edges_to_delete


class PatchRunner:
    def __init__(
        self,
        plan_writer: PatchPlanWriter,
        plan_reader: PatchPlanReader,
        edge_db_id_translator: PatchPlanEdgeDbIdTranslator,
        vertex_adder: PatchPlanVertexAdder,
        vertex_deleter: PatchPlanVertexDeleter,
        edge_adder: PatchPlanEdgeAdder,
        edge_deleter: PatchPlanEdgeDeleter,
    ) -> None:
        self.plan_writer = plan_writer
        self.plan_reader = plan_reader
        self.edge_db_id_translator = edge_db_id_translator
        self.vertex_adder = vertex_adder
        self.vertex_deleter = vertex_deleter
        self.edge_adder = edge_adder
        self.edge_deleter = edge_deleter

    async def prepare_plan(self, patch_query: PatchQuery, directory: Path) -> Path:
        patch_plan = await patch_query.plan()
        return self.plan_writer.write(patches_directory=directory, patch_plan=patch_plan)

    async def apply(self, patch_plan_directory: Path) -> None:
        patch_plan = self.plan_reader.read(patch_plan_directory)
        added_node_db_id_map: dict[str, str] = {}
        if patch_plan.vertices_to_add:
            added_node_db_id_map = await self.vertex_adder.execute(vertices_to_add=patch_plan.vertices_to_add)
            self.plan_writer.write_added_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=added_node_db_id_map
            )
        if patch_plan.vertices_to_delete:
            await self.vertex_deleter.execute(vertices_to_delete=patch_plan.vertices_to_delete)
        if patch_plan.edges_to_add:
            self.edge_db_id_translator.translate_to_db_ids(edges_to_add=patch_plan.edges_to_add, db_id_map=added_node_db_id_map)
            await self.edge_adder.execute(edges_to_add=patch_plan.edges_to_add)
        if patch_plan.edges_to_delete:
            await self.edge_deleter.execute(edges_to_delete=patch_plan.edges_to_delete)

    async def revert(self, patch_plan_directory: Path) -> None: ...


async def test_run() -> None:
    config.load_and_exit(config_file_name="infrahub.toml")
    db = InfrahubDatabase(driver=await get_db(retry=1))
    plan_writer = PatchPlanWriter()
    plan_reader = PatchPlanReader()
    patch_runner = PatchRunner(
        plan_writer=plan_writer,
        plan_reader=plan_reader,
        edge_db_id_translator=PatchPlanEdgeDbIdTranslator(),
        vertex_adder=PatchPlanVertexAdder(db=db),
        vertex_deleter=PatchPlanVertexDeleter(db=db),
        edge_adder=PatchPlanEdgeAdder(db=db),
        edge_deleter=PatchPlanEdgeDeleter(db=db)
    )
    # patch_plan_dir = await patch_runner.prepare_plan(DepduplicatePatchQuery(db=db), directory=Path("infrahub_patches"))
    patch_plan_dir = Path("infrahub_patches/patch-consolidate-duplicated-nodes-20250417-024317")
    patch_plan = plan_reader.read(patch_plan_directory=patch_plan_dir)
    assert patch_plan

    breakpoint()

    await patch_runner.apply(patch_plan_directory=patch_plan_dir)


if __name__ == "__main__":
    aiorun(test_run())
