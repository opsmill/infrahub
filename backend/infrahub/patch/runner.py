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
        await self._apply_vertices_to_add(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        await self._apply_edges_to_add(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        if patch_plan.vertices_to_update:
            await self.vertex_updater.execute(vertices_to_update=patch_plan.vertices_to_update)
        await self._apply_edges_to_delete(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        await self._apply_vertices_to_delete(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        if patch_plan.edges_to_update:
            await self.edge_updater.execute(edges_to_update=patch_plan.edges_to_update)
        return patch_plan

    async def _apply_vertices_to_add(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        if not patch_plan.vertices_to_add:
            return
        unadded_vertices = [
            v for v in patch_plan.vertices_to_add if not patch_plan.has_element_been_added(v.identifier)
        ]
        try:
            async for added_element_id_map in self.vertex_adder.execute(vertices_to_add=unadded_vertices):
                patch_plan.added_element_db_id_map.update(added_element_id_map)
        finally:
            # record the added elements so that we do not double-add them if the patch is run again
            self.plan_writer.write_added_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.added_element_db_id_map
            )

    async def _apply_edges_to_add(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        if not patch_plan.edges_to_add:
            return
        self.edge_db_id_translator.translate_to_db_ids(patch_plan=patch_plan)
        unadded_edges = [e for e in patch_plan.edges_to_add if not patch_plan.has_element_been_added(e.identifier)]
        try:
            async for added_element_id_map in self.edge_adder.execute(edges_to_add=unadded_edges):
                patch_plan.added_element_db_id_map.update(added_element_id_map)
        finally:
            # record the added elements so that we do not double-add them if the patch is run again
            self.plan_writer.write_added_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.added_element_db_id_map
            )

    async def _apply_vertices_to_delete(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        if not patch_plan.vertices_to_delete:
            return
        try:
            async for deleted_ids in self.vertex_deleter.execute(vertices_to_delete=patch_plan.vertices_to_delete):
                patch_plan.deleted_db_ids |= deleted_ids
        finally:
            # record the deleted elements so that we know what to add if the patch is reverted
            self.plan_writer.write_deleted_db_ids(
                patch_plan_directory=patch_plan_directory, deleted_ids=patch_plan.deleted_db_ids
            )

    async def _apply_edges_to_delete(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        if not patch_plan.edges_to_delete:
            return
        try:
            async for deleted_ids in self.edge_deleter.execute(edges_to_delete=patch_plan.edges_to_delete):
                patch_plan.deleted_db_ids |= deleted_ids
        finally:
            # record the deleted elements so that we know what to add if the patch is reverted
            self.plan_writer.write_deleted_db_ids(
                patch_plan_directory=patch_plan_directory, deleted_ids=patch_plan.deleted_db_ids
            )

    async def revert(self, patch_plan_directory: Path) -> PatchPlan:
        """Invert the PatchPlan to create the complement of every added/updated/deleted element and undo them"""
        patch_plan = self.plan_reader.read(patch_plan_directory)
        await self._revert_deleted_vertices(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        await self._revert_deleted_edges(
            patch_plan=patch_plan,
            patch_plan_directory=patch_plan_directory,
        )
        await self._revert_added_edges(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        await self._revert_added_vertices(patch_plan=patch_plan, patch_plan_directory=patch_plan_directory)
        vertices_to_update = [
            VertexToUpdate(
                db_id=vertex_update_to_revert.db_id,
                before_props=vertex_update_to_revert.after_props,
                after_props=vertex_update_to_revert.before_props,
            )
            for vertex_update_to_revert in patch_plan.vertices_to_update
        ]
        if vertices_to_update:
            await self.vertex_updater.execute(vertices_to_update=vertices_to_update)

        edges_to_update = [
            EdgeToUpdate(
                db_id=edge_update_to_revert.db_id,
                before_props=edge_update_to_revert.after_props,
                after_props=edge_update_to_revert.before_props,
            )
            for edge_update_to_revert in patch_plan.edges_to_update
        ]
        if edges_to_update:
            await self.edge_updater.execute(edges_to_update=edges_to_update)
        if patch_plan.reverted_deleted_db_id_map:
            patch_plan.reverted_deleted_db_id_map = {}
            self.plan_writer.write_reverted_deleted_db_id_map(
                patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.reverted_deleted_db_id_map
            )
        return patch_plan

    async def _revert_added_vertices(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        vertices_to_delete = [
            VertexToDelete(
                db_id=patch_plan.get_database_id_for_added_element(abstract_id=vertex_add_to_revert.identifier),
                labels=vertex_add_to_revert.labels,
                before_props=vertex_add_to_revert.after_props,
            )
            for vertex_add_to_revert in patch_plan.added_vertices
        ]
        if not vertices_to_delete:
            return
        all_deleted_ids: set[str] = set()
        try:
            async for deleted_ids in self.vertex_deleter.execute(vertices_to_delete=vertices_to_delete):
                all_deleted_ids |= deleted_ids
        finally:
            if all_deleted_ids:
                patch_plan.drop_added_db_ids(db_ids_to_drop=all_deleted_ids)
                self.plan_writer.write_added_db_id_map(
                    patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.added_element_db_id_map
                )

    async def _revert_deleted_vertices(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        vertices_to_add = [
            VertexToAdd(
                labels=vertex_delete_to_revert.labels,
                after_props=vertex_delete_to_revert.before_props,
                identifier=vertex_delete_to_revert.db_id,
            )
            for vertex_delete_to_revert in patch_plan.deleted_vertices
        ]
        if not vertices_to_add:
            return

        deleted_to_undeleted_db_id_map: dict[str, str] = {}
        try:
            async for added_db_id_map in self.vertex_adder.execute(vertices_to_add=vertices_to_add):
                deleted_to_undeleted_db_id_map.update(added_db_id_map)
        finally:
            if deleted_to_undeleted_db_id_map:
                patch_plan.drop_deleted_db_ids(db_ids_to_drop=set(deleted_to_undeleted_db_id_map.keys()))
                self.plan_writer.write_deleted_db_ids(
                    patch_plan_directory=patch_plan_directory, deleted_ids=patch_plan.deleted_db_ids
                )
                patch_plan.reverted_deleted_db_id_map.update(deleted_to_undeleted_db_id_map)
                self.plan_writer.write_reverted_deleted_db_id_map(
                    patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.reverted_deleted_db_id_map
                )

    async def _revert_added_edges(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        edges_to_delete = [
            EdgeToDelete(
                db_id=patch_plan.get_database_id_for_added_element(abstract_id=edge_add_to_revert.identifier),
                from_id=edge_add_to_revert.from_id,
                to_id=edge_add_to_revert.to_id,
                edge_type=edge_add_to_revert.edge_type,
                before_props=edge_add_to_revert.after_props,
            )
            for edge_add_to_revert in patch_plan.added_edges
        ]
        if not edges_to_delete:
            return
        all_deleted_ids: set[str] = set()
        try:
            async for deleted_ids in self.edge_deleter.execute(edges_to_delete=edges_to_delete):
                all_deleted_ids |= deleted_ids
        finally:
            if all_deleted_ids:
                patch_plan.drop_added_db_ids(db_ids_to_drop=all_deleted_ids)
                self.plan_writer.write_added_db_id_map(
                    patch_plan_directory=patch_plan_directory, db_id_map=patch_plan.added_element_db_id_map
                )

    async def _revert_deleted_edges(self, patch_plan: PatchPlan, patch_plan_directory: Path) -> None:
        edges_to_add = [
            EdgeToAdd(
                identifier=edge_delete_to_revert.db_id,
                from_id=patch_plan.reverted_deleted_db_id_map.get(
                    edge_delete_to_revert.from_id, edge_delete_to_revert.from_id
                ),
                to_id=patch_plan.reverted_deleted_db_id_map.get(
                    edge_delete_to_revert.to_id, edge_delete_to_revert.to_id
                ),
                edge_type=edge_delete_to_revert.edge_type,
                after_props=edge_delete_to_revert.before_props,
            )
            for edge_delete_to_revert in patch_plan.deleted_edges
        ]
        if not edges_to_add:
            return

        undeleted_ids: set[str] = set()
        try:
            async for added_db_id_map in self.edge_adder.execute(edges_to_add=edges_to_add):
                undeleted_ids |= set(added_db_id_map.keys())
        finally:
            if undeleted_ids:
                patch_plan.drop_deleted_db_ids(db_ids_to_drop=undeleted_ids)
                self.plan_writer.write_deleted_db_ids(
                    patch_plan_directory=patch_plan_directory, deleted_ids=patch_plan.deleted_db_ids
                )
