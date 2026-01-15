import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock
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
from tests.db_snapshot import DbSnapshot, DbSnapshotter

EDGE_TYPE = "TESTING_EDGE"
VERTEX_LABELS = ["Vertex", "For", "Testing"]


class TestingPatch(PatchQuery):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.vertex_identifier_1 = str(uuid4())
        self.vertex_identifier_2 = str(uuid4())
        self.vertices_to_add = [
            VertexToAdd(
                identifier=self.vertex_identifier_1,
                labels=VERTEX_LABELS,
                after_props={"string": "abc", "int": 1, "bool": True, "null_thing": None},
            ),
            VertexToAdd(
                identifier=self.vertex_identifier_2,
                labels=VERTEX_LABELS,
                after_props={"string": "def", "int": 2, "bool": False, "null_thing": None},
            ),
        ]
        self.vertex_to_update = None
        self.vertices_to_delete = None
        self.edges_to_add = []
        self.edges_to_update = []
        self.edges_to_delete = []

    def set_vertex_to_update(self, v: VertexToUpdate) -> None:
        self.vertex_to_update = v

    def set_vertices_to_delete(self, vertices: list[VertexToDelete]) -> None:
        self.vertices_to_delete = vertices

    def set_edges_to_add(self, vertex_map: dict[str, str]) -> None:
        for source_id, destination_id in vertex_map.items():
            self.edges_to_add.append(
                EdgeToAdd(
                    from_id=source_id,
                    to_id=destination_id,
                    edge_type=EDGE_TYPE,
                    after_props={"from": source_id, "to": destination_id},
                )
            )

    def set_edges_to_update(self, edges: list[EdgeToUpdate]) -> None:
        self.edges_to_update = edges

    def set_edges_to_delete(self, edges: list[EdgeToDelete]) -> None:
        self.edges_to_delete = edges

    async def plan(self) -> PatchPlan:
        return PatchPlan(
            name=self.name,
            vertices_to_add=self.vertices_to_add,
            vertices_to_update=[self.vertex_to_update],
            vertices_to_delete=self.vertices_to_delete,
            edges_to_add=self.edges_to_add,
            edges_to_update=self.edges_to_update,
            edges_to_delete=self.edges_to_delete,
        )

    @property
    def name(self) -> str:
        return "testing-patch"


class TestPatchRunner:
    @pytest.fixture(scope="class")
    def temporary_directory_path(self) -> Generator[Path, None, None]:
        temporary_directory = tempfile.TemporaryDirectory()
        yield Path(temporary_directory.name)
        temporary_directory.cleanup()

    @pytest.fixture
    async def initial_data(self, db: InfrahubDatabase) -> dict[str, str]:
        delete_all_query = """MATCH (v) DETACH DELETE v"""
        await db.execute_query(query=delete_all_query)
        create_query = """
CREATE (v1:%(v_labels)s {value: 1})
CREATE (v2:%(v_labels)s {value: 2})
CREATE (v3:%(v_labels)s {value: 3})
CREATE (v4:%(v_labels)s {value: 4})
CREATE (v5:%(v_labels)s {value: 5})
CREATE (v6:%(v_labels)s {value: 6})
CREATE (v1)-[e1:%(edge_type)s]->(v2)
SET e1 =  {from: v1.value, to: v2.value}
CREATE (v2)-[e2:%(edge_type)s]->(v3)
SET e2 = {from: v2.value, to: v3.value}
CREATE (v3)-[e3:%(edge_type)s]->(v4)
SET e3 = {from: v3.value, to: v4.value}
CREATE (v4)-[e4:%(edge_type)s]->(v5)
SET e4 = {from: v4.value, to: v5.value}
RETURN v1, v2, v3, v4, v5, v6, e1, e2, e3, e4
        """ % {"edge_type": EDGE_TYPE, "v_labels": ":".join(VERTEX_LABELS)}
        results = await db.execute_query(query=create_query)
        result = results[0]
        return {
            v_name: result.get(v_name).element_id
            for v_name in ["v1", "v2", "v3", "v4", "v5", "v6", "e1", "e2", "e3", "e4"]
        }

    @pytest.fixture
    def testing_patch(self, db: InfrahubDatabase, initial_data: dict[str]) -> TestingPatch:
        # create the testing patch
        testing_patch = TestingPatch(db=db)
        testing_patch.set_vertex_to_update(
            VertexToUpdate(db_id=initial_data["v4"], before_props={"value": 4}, after_props={"after_value": "4"})
        )
        testing_patch.set_vertices_to_delete(
            [
                VertexToDelete(db_id=initial_data["v5"], labels=VERTEX_LABELS, before_props={"value": 5}),
                VertexToDelete(db_id=initial_data["v6"], labels=VERTEX_LABELS, before_props={"value": 6}),
            ]
        )
        testing_patch.set_edges_to_add(
            {
                initial_data.get(s_name, s_name): initial_data.get(d_name, d_name)
                for s_name, d_name in (("v1", "v3"), ("v2", "v3"), ("v3", testing_patch.vertex_identifier_1))
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
                ),
                EdgeToDelete(
                    db_id=initial_data["e4"],
                    from_id=initial_data["v4"],
                    to_id=initial_data["v5"],
                    edge_type=EDGE_TYPE,
                    before_props={"from": 4, "to": 5},
                ),
            ]
        )
        return testing_patch

    @pytest.fixture
    def patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        return self.get_patch_runner(db=db)

    @pytest.fixture
    def broken_vertex_adder_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        # mock vertex adder to fail after making actual db changes
        broken_patch_runner = self.get_patch_runner(db=db)
        real_vertex_adder = PatchPlanVertexAdder(db=db)
        mock_vertex_adder = AsyncMock(spec=PatchPlanVertexAdder)

        async def mock_vertex_adder_execute(*args, **kwargs):
            async for result in real_vertex_adder.execute(*args, **kwargs):
                yield result
                raise ValueError("this is expected")

        mock_vertex_adder.execute = mock_vertex_adder_execute
        broken_patch_runner.vertex_adder = mock_vertex_adder
        return broken_patch_runner

    @pytest.fixture
    def broken_edge_adder_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        # mock edge adder to fail after making actual db changes
        broken_patch_runner = self.get_patch_runner(db=db)
        real_edge_adder = PatchPlanEdgeAdder(db=db)
        mock_edge_adder = AsyncMock(spec=PatchPlanEdgeAdder)

        async def mock_edge_adder_execute(*args, **kwargs):
            async for result in real_edge_adder.execute(*args, **kwargs):
                yield result
                raise ValueError("this is expected")

        mock_edge_adder.execute = mock_edge_adder_execute
        broken_patch_runner.edge_adder = mock_edge_adder
        return broken_patch_runner

    @pytest.fixture
    def broken_vertex_deleter_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        # mock vertex deleter to fail after making actual db changes
        broken_patch_runner = self.get_patch_runner(db=db)
        real_vertex_deleter = PatchPlanVertexDeleter(db=db)
        mock_vertex_deleter = AsyncMock(spec=PatchPlanVertexDeleter)

        async def mock_vertex_deleter_execute(*args, **kwargs):
            async for result in real_vertex_deleter.execute(*args, **kwargs):
                yield result
                raise ValueError("this is expected")

        mock_vertex_deleter.execute = mock_vertex_deleter_execute
        broken_patch_runner.vertex_deleter = mock_vertex_deleter
        return broken_patch_runner

    @pytest.fixture
    def broken_edge_deleter_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        # mock edge deleter to fail after making actual db changes
        broken_patch_runner = self.get_patch_runner(db=db)
        real_edge_deleter = PatchPlanEdgeDeleter(db=db)
        mock_edge_deleter = AsyncMock(spec=PatchPlanEdgeDeleter)

        async def mock_edge_deleter_execute(*args, **kwargs):
            async for result in real_edge_deleter.execute(*args, **kwargs):
                yield result
                raise ValueError("this is expected")

        mock_edge_deleter.execute = mock_edge_deleter_execute
        broken_patch_runner.edge_deleter = mock_edge_deleter
        return broken_patch_runner

    @pytest.fixture(params=["vertex_add", "vertex_delete", "edge_add", "edge_delete"])
    async def broken_patch_runner(
        self,
        request,
        broken_vertex_adder_patch_runner: PatchRunner,
        broken_vertex_deleter_patch_runner: PatchRunner,
        broken_edge_adder_patch_runner: PatchRunner,
        broken_edge_deleter_patch_runner: PatchRunner,
    ) -> PatchRunner:
        if request.param == "vertex_add":
            return broken_vertex_adder_patch_runner
        if request.param == "vertex_delete":
            return broken_vertex_deleter_patch_runner
        if request.param == "edge_add":
            return broken_edge_adder_patch_runner
        if request.param == "edge_delete":
            return broken_edge_deleter_patch_runner

        pytest.fail(reason="Valid patch runner missing")

    def get_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        return PatchRunner(
            plan_writer=PatchPlanWriter(),
            plan_reader=PatchPlanReader(),
            edge_db_id_translator=PatchPlanEdgeDbIdTranslator(),
            vertex_adder=PatchPlanVertexAdder(db=db, batch_size_limit=1),
            vertex_deleter=PatchPlanVertexDeleter(db=db, batch_size_limit=1),
            vertex_updater=PatchPlanVertexUpdater(db=db, batch_size_limit=1),
            edge_adder=PatchPlanEdgeAdder(db=db, batch_size_limit=1),
            edge_deleter=PatchPlanEdgeDeleter(db=db, batch_size_limit=1),
            edge_updater=PatchPlanEdgeUpdater(db=db, batch_size_limit=1),
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

    async def _take_snapshot(self, db: InfrahubDatabase) -> DbSnapshot:
        snapshotter = DbSnapshotter(db=db)
        return await snapshotter.snapshot()

    async def test_apply_and_revert(
        self,
        db: InfrahubDatabase,
        initial_data: dict[str, str],
        temporary_directory_path: Path,
        testing_patch: TestingPatch,
        patch_runner: PatchRunner,
    ) -> None:
        # take a snapshot of the database before applying the patch
        before_snapshot = await self._take_snapshot(db=db)

        temp_dir_path = temporary_directory_path
        patch_plan_dir = await patch_runner.prepare_plan(patch_query=testing_patch, directory=temp_dir_path)
        await patch_runner.apply(patch_plan_directory=patch_plan_dir)
        # twice to test idempotence
        patch_plan = await patch_runner.apply(patch_plan_directory=patch_plan_dir)

        # test vertices added
        vertices = await self._get_testing_vertices(db=db)
        assert len(vertices) == 6
        count_matches_for_each = [0] * len(testing_patch.vertices_to_add)
        for vertex in vertices:
            is_match = [1] * len(testing_patch.vertices_to_add)
            for index, v_to_add in enumerate(testing_patch.vertices_to_add):
                if set(vertex.labels) != set(v_to_add.labels):
                    is_match[index] = 0
                    break
                for k, v in v_to_add.after_props.items():
                    if vertex.get(k) != v:
                        is_match[index] = 0
                        break
            count_matches_for_each = [x + y for (x, y) in zip(count_matches_for_each, is_match, strict=False)]
        # each added vertex has 1 and only 1 match
        assert count_matches_for_each == [1] * len(testing_patch.vertices_to_add)

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
        v_new_db_id = patch_plan.added_element_db_id_map[testing_patch.vertex_identifier_1]
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
        assert dict(v3_vnew_edges[0].items()) == {"from": v3_db_id, "to": testing_patch.vertex_identifier_1}
        assert v3_vnew_edges[0].type == EDGE_TYPE

        # test edge deleted
        v3_v4_edges = await self._get_testing_edges(db=db, from_id=v3_db_id, to_id=v4_db_id)
        assert len(v3_v4_edges) == 0

        # test reverting the patch
        reverted_patch_plan = await patch_runner.revert(patch_plan_directory=patch_plan_dir)
        # ensure the successful revert accurately tracked its progress when deleting the added elements
        assert not reverted_patch_plan.added_element_db_id_map
        assert not reverted_patch_plan.deleted_db_ids
        assert not reverted_patch_plan.reverted_deleted_db_id_map
        # twice to test idempotence
        await patch_runner.revert(patch_plan_directory=patch_plan_dir)

        # take a new snapshot
        reverted_snapshot = await self._take_snapshot(db=db)

        # compare to old snapshot
        assert hash(before_snapshot) == hash(reverted_snapshot)

    async def test_patch_runner_apply_crash_and_revert(
        self,
        db: InfrahubDatabase,
        initial_data: dict[str, str],
        temporary_directory_path: Path,
        testing_patch: TestingPatch,
        patch_runner: PatchRunner,
        broken_patch_runner: PatchRunner,
    ) -> None:
        # take a snapshot of the database before applying the patch
        before_snapshot = await self._take_snapshot(db=db)

        temp_dir_path = temporary_directory_path
        patch_plan_dir = await patch_runner.prepare_plan(patch_query=testing_patch, directory=temp_dir_path)

        with pytest.raises(ValueError, match="this is expected"):
            await broken_patch_runner.apply(patch_plan_directory=patch_plan_dir)

        # apply again and complete
        await patch_runner.apply(patch_plan_directory=patch_plan_dir)

        # test reverting the patch
        await patch_runner.revert(patch_plan_directory=patch_plan_dir)
        # twice to test idempotence
        await patch_runner.revert(patch_plan_directory=patch_plan_dir)

        # take a new snapshot
        reverted_snapshot = await self._take_snapshot(db=db)

        # compare to old snapshot
        assert hash(before_snapshot) == hash(reverted_snapshot)

    async def test_patch_runner_crash_during_revert(
        self,
        db: InfrahubDatabase,
        initial_data: dict[str, str],
        temporary_directory_path: Path,
        testing_patch: TestingPatch,
        patch_runner: PatchRunner,
        broken_patch_runner: PatchRunner,
    ) -> None:
        # take a snapshot of the database before applying the patch
        before_snapshot = await self._take_snapshot(db=db)

        temp_dir_path = temporary_directory_path
        patch_plan_dir = await patch_runner.prepare_plan(patch_query=testing_patch, directory=temp_dir_path)

        # apply the patch and succeed
        await patch_runner.apply(patch_plan_directory=patch_plan_dir)

        # fail while reverting the patch
        with pytest.raises(ValueError, match="this is expected"):
            await broken_patch_runner.revert(patch_plan_directory=patch_plan_dir)
        # try revert again and succeed
        await patch_runner.revert(patch_plan_directory=patch_plan_dir)

        # take a new snapshot
        reverted_snapshot = await self._take_snapshot(db=db)

        # compare to old snapshot
        assert hash(before_snapshot) == hash(reverted_snapshot)
