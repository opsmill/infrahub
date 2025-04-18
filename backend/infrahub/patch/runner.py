from pathlib import Path

from .edge_adder import PatchPlanEdgeAdder
from .edge_deleter import PatchPlanEdgeDeleter
from .edge_updater import PatchPlanEdgeUpdater
from .models import EdgeToAdd, PatchPlan
from .plan_reader import PatchPlanReader
from .plan_writer import PatchPlanWriter
from .queries.base import PatchQuery
from .vertex_adder import PatchPlanVertexAdder
from .vertex_deleter import PatchPlanVertexDeleter
from .vertex_updater import PatchPlanVertexUpdater


class PatchPlanEdgeDbIdTranslator:
    def translate_to_db_ids(self, edges_to_add: list[EdgeToAdd], db_id_map: dict[str, str]) -> None:
        for edge_to_add in edges_to_add:
            if edge_to_add.from_id in db_id_map:
                edge_to_add.from_id = db_id_map[edge_to_add.from_id]
            if edge_to_add.to_id in db_id_map:
                edge_to_add.to_id = db_id_map[edge_to_add.to_id]


class PatchRunner:
    def __init__(
        self,
        plan_writer: PatchPlanWriter,
        plan_reader: PatchPlanReader,
        edge_db_id_translator: PatchPlanEdgeDbIdTranslator,
        vertex_adder: PatchPlanVertexAdder,
        vertex_updater: PatchPlanVertexUpdater,
        vertex_deleter: PatchPlanVertexDeleter,
        edge_adder: PatchPlanEdgeAdder,
        edge_updater: PatchPlanEdgeUpdater,
        edge_deleter: PatchPlanEdgeDeleter,
    ) -> None:
        self.plan_writer = plan_writer
        self.plan_reader = plan_reader
        self.edge_db_id_translator = edge_db_id_translator
        self.vertex_adder = vertex_adder
        self.vertex_updater = vertex_updater
        self.vertex_deleter = vertex_deleter
        self.edge_adder = edge_adder
        self.edge_updater = edge_updater
        self.edge_deleter = edge_deleter

    async def prepare_plan(self, patch_query: PatchQuery, directory: Path) -> Path:
        patch_plan = await patch_query.plan()
        return self.plan_writer.write(patches_directory=directory, patch_plan=patch_plan)

    async def apply(self, patch_plan_directory: Path) -> PatchPlan:
        patch_plan = self.plan_reader.read(patch_plan_directory)
        added_node_db_id_map: dict[str, str] = {}
        if patch_plan.vertices_to_add:
            added_node_db_id_map = await self.vertex_adder.execute(vertices_to_add=patch_plan.vertices_to_add)
            self.plan_writer.write_added_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=added_node_db_id_map
            )
            patch_plan.added_node_db_id_map = added_node_db_id_map
        if patch_plan.vertices_to_update:
            await self.vertex_updater.execute(vertices_to_update=patch_plan.vertices_to_update)
        if patch_plan.vertices_to_delete:
            await self.vertex_deleter.execute(vertices_to_delete=patch_plan.vertices_to_delete)
        if patch_plan.edges_to_add:
            self.edge_db_id_translator.translate_to_db_ids(
                edges_to_add=patch_plan.edges_to_add, db_id_map=added_node_db_id_map
            )
            await self.edge_adder.execute(edges_to_add=patch_plan.edges_to_add)
        if patch_plan.edges_to_update:
            await self.edge_updater.execute(edges_to_update=patch_plan.edges_to_update)
        if patch_plan.edges_to_delete:
            await self.edge_deleter.execute(edges_to_delete=patch_plan.edges_to_delete)
        return patch_plan

    async def revert(self, patch_plan_directory: Path) -> None: ...
