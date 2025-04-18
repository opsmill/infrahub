import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from infrahub.database import InfrahubDatabase
from infrahub.patch.edge_adder import PatchPlanEdgeAdder
from infrahub.patch.edge_deleter import PatchPlanEdgeDeleter
from infrahub.patch.edge_updater import PatchPlanEdgeUpdater
from infrahub.patch.models import (
    EdgeToAdd,
    EdgeToDelete,
    EdgeToUpdate,
    PatchPlan,
    VertexToAdd,
    VertexToDelete,
    VertexToUpdate,
)
from infrahub.patch.plan_reader import PatchPlanReader
from infrahub.patch.plan_writer import PatchPlanWriter
from infrahub.patch.queries.base import PatchQuery
from infrahub.patch.runner import (
    PatchPlanEdgeDbIdTranslator,
    PatchRunner,
)
from infrahub.patch.vertex_adder import PatchPlanVertexAdder
from infrahub.patch.vertex_deleter import PatchPlanVertexDeleter
from infrahub.patch.vertex_updater import PatchPlanVertexUpdater

EDGE_TYPE = "TESTING_EDGE"
VERTEX_LABELS = ["Vertex", "For", "Testing"]


class TestingPatch(PatchQuery):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.vertex_identifier = str(uuid4())
        self.vertex_to_add = VertexToAdd(
            identifier=self.vertex_identifier,
            labels=VERTEX_LABELS,
            after_props={"string": "abc", "int": 1, "bool": True},
        )
        self.vertex_to_update = None
        self.vertex_to_delete = None
        self.edges_to_add = []
        self.edges_to_update = []
        self.edges_to_delete = []

    def set_vertex_to_update(self, v: VertexToUpdate):
        self.vertex_to_update = v

    def set_vertex_to_delete(self, v: VertexToDelete):
        self.vertex_to_delete = v

    def set_edges_to_add(self, vertex_map: dict[str, str]):
        for source_id, destination_id in vertex_map.items():
            self.edges_to_add.append(
                EdgeToAdd(
                    from_id=source_id,
                    to_id=destination_id,
                    edge_type=EDGE_TYPE,
                    after_props={"from": source_id, "to": destination_id},
                )
            )

    def set_edges_to_update(self, edges: list[EdgeToUpdate]):
        self.edges_to_update = edges

    def set_edges_to_delete(self, edges: list[EdgeToDelete]):
        self.edges_to_delete = edges

    async def plan(self) -> PatchPlan:
        return PatchPlan(
            name=self.name,
            vertices_to_add=[self.vertex_to_add],
            vertices_to_update=[self.vertex_to_update],
            vertices_to_delete=[self.vertex_to_delete],
            edges_to_add=self.edges_to_add,
            edges_to_update=self.edges_to_update,
            edges_to_delete=self.edges_to_delete,
        )

    @property
    def name(self) -> str:
        return "testing-patch"


class TestPatchRunner:
    @pytest.fixture(scope="class")
    async def initial_data(self, db: InfrahubDatabase) -> dict[str, str]:
        delete_all_query = """MATCH (v) DETACH DELETE v"""
        await db.execute_query(query=delete_all_query)
        create_query = """
CREATE (v1:%(v_labels)s {value: 1})
CREATE (v2:%(v_labels)s {value: 2})
CREATE (v3:%(v_labels)s {value: 3})
CREATE (v4:%(v_labels)s {value: 4})
CREATE (v5:%(v_labels)s {value: 5})
CREATE (v1)-[e1:%(edge_type)s]->(v2)
SET e1 =  {from: v1.value, to: v2.value}
CREATE (v2)-[e2:%(edge_type)s]->(v3)
SET e2 = {from: v2.value, to: v3.value}
CREATE (v3)-[e3:%(edge_type)s]->(v4)
SET e3 = {from: v3.value, to: v4.value}
RETURN v1, v2, v3, v4, v5, e1, e2, e3
        """ % {"edge_type": EDGE_TYPE, "v_labels": ":".join(VERTEX_LABELS)}
        results = await db.execute_query(query=create_query)
        result = results[0]
        return {v_name: result.get(v_name).element_id for v_name in ["v1", "v2", "v3", "v4", "v5", "e1", "e2", "e3"]}

    def get_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        plan_writer = PatchPlanWriter()
        plan_reader = PatchPlanReader()
        return PatchRunner(
            plan_writer=plan_writer,
            plan_reader=plan_reader,
            edge_db_id_translator=PatchPlanEdgeDbIdTranslator(),
            vertex_adder=PatchPlanVertexAdder(db=db),
            vertex_deleter=PatchPlanVertexDeleter(db=db),
            vertex_updater=PatchPlanVertexUpdater(db=db),
            edge_adder=PatchPlanEdgeAdder(db=db),
            edge_deleter=PatchPlanEdgeDeleter(db=db),
            edge_updater=PatchPlanEdgeUpdater(db=db),
        )

    async def _get_testing_vertices(self, db: InfrahubDatabase):
        query = """MATCH (v:%(labels)s) RETURN v""" % {"labels": "|".join(VERTEX_LABELS)}
        results = await db.execute_query(query=query)
        return [r.get("v") for r in results]

    async def _get_testing_vertex_by_id(self, db: InfrahubDatabase, db_id: str):
        query = """MATCH (v) WHERE elementId(v) = $db_id RETURN v"""
        results = await db.execute_query(query=query, params={"db_id": db_id})
        if not results:
            return None
        return results[0].get("v")

    async def _get_testing_edges(self, db: InfrahubDatabase, from_id: str, to_id: str):
        query = """
MATCH (a) WHERE elementId(a) = $from_id
MATCH (b) WHERE elementId(b) = $to_id
MATCH (a)-[e]-(b)
RETURN e
        """
        results = await db.execute_query(query=query, params={"from_id": from_id, "to_id": to_id})
        return [r.get("e") for r in results]

    async def test_apply_patch(self, db: InfrahubDatabase, initial_data: dict[str, str]) -> None:
        testing_patch = TestingPatch(db=db)
        testing_patch.set_vertex_to_update(
            VertexToUpdate(db_id=initial_data["v4"], before_props={"value": 4}, after_props={"after_value": "4"})
        )
        testing_patch.set_vertex_to_delete(
            VertexToDelete(db_id=initial_data["v5"], labels=VERTEX_LABELS, before_props={"value": 5})
        )
        testing_patch.set_edges_to_add(
            {
                initial_data.get(s_name, s_name): initial_data.get(d_name, d_name)
                for s_name, d_name in (("v1", "v3"), ("v2", "v3"), ("v3", testing_patch.vertex_identifier))
            }
        )
        testing_patch.set_edges_to_update(
            [
                EdgeToUpdate(
                    db_id=initial_data["e1"], before_props={"from": 1, "to": 2}, after_props={"something": "new"}
                ),
                EdgeToUpdate(
                    db_id=initial_data["e2"], before_props={"from": 2, "to": 3}, after_props={"something": "else"}
                ),
            ]
        )
        testing_patch.set_edges_to_delete(
            [
                EdgeToDelete(
                    db_id=initial_data["e3"],
                    from_id=initial_data["v3"],
                    to_id=initial_data["v4"],
                    edge_type=EDGE_TYPE,
                    before_props={"from": 3, "to": 4},
                )
            ]
        )
        patch_runner = self.get_patch_runner(db=db)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            patch_plan_dir = await patch_runner.prepare_plan(patch_query=testing_patch, directory=temp_dir_path)
            await patch_runner.apply(patch_plan_directory=patch_plan_dir)
            # twice to test idempotence
            patch_plan = await patch_runner.apply(patch_plan_directory=patch_plan_dir)

        # test vertex added
        vertices = await self._get_testing_vertices(db=db)
        assert len(vertices) == 5
        count_matches = 0
        for vertex in vertices:
            is_match = 1
            if set(vertex.labels) != set(testing_patch.vertex_to_add.labels):
                break
            for k, v in testing_patch.vertex_to_add.after_props.items():
                if vertex.get(k) != v:
                    is_match = 0
                    break
            count_matches += is_match
        assert count_matches == 1

        # test vertex updated
        updated_v4 = await self._get_testing_vertex_by_id(db=db, db_id=initial_data["v4"])
        assert set(updated_v4.labels) == set(VERTEX_LABELS)
        assert dict(updated_v4.items()) == testing_patch.vertex_to_update.after_props

        # test vertex deleted
        deleted_v5 = await self._get_testing_vertex_by_id(db=db, db_id=initial_data["v5"])
        assert deleted_v5 is None

        # test edges added/updated
        v1_db_id = initial_data["v1"]
        v2_db_id = initial_data["v2"]
        v3_db_id = initial_data["v3"]
        v4_db_id = initial_data["v4"]
        v_new_db_id = patch_plan.added_node_db_id_map[testing_patch.vertex_identifier]
        v1_v2_edges = await self._get_testing_edges(db=db, from_id=v1_db_id, to_id=v2_db_id)
        assert len(v1_v2_edges) == 1
        assert v1_v2_edges[0].type == EDGE_TYPE
        assert dict(v1_v2_edges[0].items()) == {"something": "new"}
        v1_v3_edges = await self._get_testing_edges(db=db, from_id=v1_db_id, to_id=v3_db_id)
        assert len(v1_v3_edges) == 1
        assert v1_v3_edges[0].type == EDGE_TYPE
        assert dict(v1_v3_edges[0].items()) == {"from": v1_db_id, "to": v3_db_id}
        v2_v3_edges = await self._get_testing_edges(db=db, from_id=v2_db_id, to_id=v3_db_id)
        assert len(v2_v3_edges) == 2
        has_match = False
        for edge in v2_v3_edges:
            has_match |= dict(edge.items()) == {"from": v2_db_id, "to": v3_db_id} and edge.type == EDGE_TYPE
        assert has_match
        has_match = False
        for edge in v2_v3_edges:
            has_match |= dict(edge.items()) == {"something": "else"} and edge.type == EDGE_TYPE
        assert has_match
        v3_vnew_edges = await self._get_testing_edges(db=db, from_id=v3_db_id, to_id=v_new_db_id)
        assert len(v3_vnew_edges) == 1
        assert dict(v3_vnew_edges[0].items()) == {"from": v3_db_id, "to": testing_patch.vertex_identifier}
        assert v3_vnew_edges[0].type == EDGE_TYPE

        # test edge deleted
        v3_v4_edges = await self._get_testing_edges(db=db, from_id=v3_db_id, to_id=v4_db_id)
        assert len(v3_v4_edges) == 0
