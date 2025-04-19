from pathlib import Path

from .edge_adder import PatchPlanEdgeAdder
from .edge_deleter import PatchPlanEdgeDeleter
from .edge_updater import PatchPlanEdgeUpdater
from .models import EdgeToAdd, EdgeToDelete, EdgeToUpdate, PatchPlan, VertexToAdd, VertexToDelete, VertexToUpdate
from .plan_reader import PatchPlanReader
from .plan_writer import PatchPlanWriter
from .queries.base import PatchQuery
from .vertex_adder import PatchPlanVertexAdder
from .vertex_deleter import PatchPlanVertexDeleter
from .vertex_updater import PatchPlanVertexUpdater


class PatchPlanEdgeDbIdTranslator:
    def translate_to_db_ids(self, patch_plan: PatchPlan) -> None:
        for edge_to_add in patch_plan.edges_to_add:
            translated_from_id = patch_plan.get_database_id_for_added_element(abstract_id=edge_to_add.from_id)
            edge_to_add.from_id = translated_from_id
            translated_to_id = patch_plan.get_database_id_for_added_element(abstract_id=edge_to_add.to_id)
            edge_to_add.to_id = translated_to_id


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
        updated_db_id_map = False
        if patch_plan.vertices_to_add:
            patch_plan.added_node_db_id_map.update(
                await self.vertex_adder.execute(vertices_to_add=patch_plan.vertices_to_add)
            )
            updated_db_id_map = True
        if patch_plan.vertices_to_update:
            await self.vertex_updater.execute(vertices_to_update=patch_plan.vertices_to_update)
        if patch_plan.vertices_to_delete:
            await self.vertex_deleter.execute(vertices_to_delete=patch_plan.vertices_to_delete)
        if patch_plan.edges_to_add:
            self.edge_db_id_translator.translate_to_db_ids(patch_plan=patch_plan)
            patch_plan.added_node_db_id_map.update(await self.edge_adder.execute(edges_to_add=patch_plan.edges_to_add))
            updated_db_id_map = True
        if patch_plan.edges_to_update:
            await self.edge_updater.execute(edges_to_update=patch_plan.edges_to_update)
        if patch_plan.edges_to_delete:
            await self.edge_deleter.execute(edges_to_delete=patch_plan.edges_to_delete)
        if updated_db_id_map:
            self.plan_writer.write_added_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.added_node_db_id_map
            )
        return patch_plan

    async def revert(self, patch_plan_directory: Path) -> None:
        patch_plan = self.plan_reader.read(patch_plan_directory)
        vertices_to_delete = []
        for vertex_add_to_revert in patch_plan.vertices_to_add:
            vertices_to_delete.append(
                VertexToDelete(
                    db_id=patch_plan.get_database_id_for_added_element(abstract_id=vertex_add_to_revert.identifier),
                    labels=vertex_add_to_revert.labels,
                    before_props=vertex_add_to_revert.after_props,
                )
            )
        if vertices_to_delete:
            await self.vertex_deleter.execute(vertices_to_delete=vertices_to_delete)

        vertices_to_update = []
        for vertex_update_to_revert in patch_plan.vertices_to_update:
            vertices_to_update.append(
                VertexToUpdate(
                    db_id=vertex_update_to_revert.db_id,
                    before_props=vertex_update_to_revert.after_props,
                    after_props=vertex_update_to_revert.before_props,
                )
            )
        if vertices_to_update:
            await self.vertex_updater.execute(vertices_to_update=vertices_to_update)

        vertices_to_add = []
        for vertex_delete_to_revert in patch_plan.vertices_to_delete:
            vertices_to_add.append(
                VertexToAdd(labels=vertex_delete_to_revert.labels, after_props=vertex_delete_to_revert.before_props)
            )
        if vertices_to_add:
            await self.vertex_adder.execute(vertices_to_add=vertices_to_add)

        edges_to_delete = []
        for edge_add_to_revert in patch_plan.edges_to_add:
            edges_to_delete.append(
                EdgeToDelete(
                    db_id=patch_plan.get_database_id_for_added_element(abstract_id=edge_add_to_revert.identifier),
                    from_id=edge_add_to_revert.from_id,
                    to_id=edge_add_to_revert.to_id,
                    edge_type=edge_add_to_revert.edge_type,
                    before_props=edge_add_to_revert.after_props,
                )
            )
        if edges_to_delete:
            await self.edge_deleter.execute(edges_to_delete=edges_to_delete)

        edges_to_update = []
        for edge_update_to_revert in patch_plan.edges_to_update:
            edges_to_update.append(
                EdgeToUpdate(
                    db_id=edge_update_to_revert.db_id,
                    before_props=edge_update_to_revert.after_props,
                    after_props=edge_update_to_revert.before_props,
                )
            )
        if edges_to_update:
            await self.edge_updater.execute(edges_to_update=edges_to_update)

        edges_to_add = []
        for edge_delete_to_revert in patch_plan.edges_to_delete:
            edges_to_add.append(
                EdgeToAdd(
                    from_id=edge_delete_to_revert.from_id,
                    to_id=edge_delete_to_revert.to_id,
                    edge_type=edge_delete_to_revert.edge_type,
                    after_props=edge_delete_to_revert.before_props,
                )
            )
        if edges_to_add:
            await self.edge_adder.execute(edges_to_add=edges_to_add)
