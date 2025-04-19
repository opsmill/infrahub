import json
from pathlib import Path
from typing import Generator

from .models import EdgeToAdd, EdgeToDelete, EdgeToUpdate, PatchPlan, VertexToAdd, VertexToDelete, VertexToUpdate


class PatchPlanReader:
    def read(self, patch_plan_directory: Path) -> PatchPlan:
        vertices_to_add = self._read_vertices_to_add(patch_plan_directory=patch_plan_directory)
        vertices_to_delete = self._read_vertices_to_delete(patch_plan_directory=patch_plan_directory)
        vertices_to_update = self._read_vertices_to_update(patch_plan_directory=patch_plan_directory)
        edges_to_add = self._read_edges_to_add(patch_plan_directory=patch_plan_directory)
        edges_to_delete = self._read_edges_to_delete(patch_plan_directory=patch_plan_directory)
        edges_to_update = self._read_edges_to_update(patch_plan_directory=patch_plan_directory)
        added_node_db_id_map = self._read_added_node_db_id_map(patch_plan_directory=patch_plan_directory)

        return PatchPlan(
            name="none",
            vertices_to_add=vertices_to_add,
            vertices_to_delete=vertices_to_delete,
            vertices_to_update=vertices_to_update,
            edges_to_add=edges_to_add,
            edges_to_delete=edges_to_delete,
            edges_to_update=edges_to_update,
            added_node_db_id_map=added_node_db_id_map or {},
        )

    def _read_file_lines(self, patch_file: Path) -> Generator[str | None, None, None]:
        if not patch_file.exists():
            return
        with patch_file.open() as f:
            yield from f

    def _read_vertices_to_add(self, patch_plan_directory: Path) -> list[VertexToAdd]:
        file = patch_plan_directory / Path("vertices_to_add.json")
        vertices_to_add: list[VertexToAdd] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                vertices_to_add.append(VertexToAdd(**json.loads(raw_line)))
        return vertices_to_add

    def _read_vertices_to_update(self, patch_plan_directory: Path) -> list[VertexToUpdate]:
        file = patch_plan_directory / Path("vertices_to_update.json")
        vertices_to_update: list[VertexToUpdate] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                vertices_to_update.append(VertexToUpdate(**json.loads(raw_line)))
        return vertices_to_update

    def _read_vertices_to_delete(self, patch_plan_directory: Path) -> list[VertexToDelete]:
        file = patch_plan_directory / Path("vertices_to_delete.json")
        vertices_to_delete: list[VertexToDelete] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                vertices_to_delete.append(VertexToDelete(**json.loads(raw_line)))
        return vertices_to_delete

    def _read_edges_to_add(self, patch_plan_directory: Path) -> list[EdgeToAdd]:
        file = patch_plan_directory / Path("edges_to_add.json")
        edges_to_add: list[EdgeToAdd] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                edges_to_add.append(EdgeToAdd(**json.loads(raw_line)))
        return edges_to_add

    def _read_edges_to_delete(self, patch_plan_directory: Path) -> list[EdgeToDelete]:
        file = patch_plan_directory / Path("edges_to_delete.json")
        edges_to_delete: list[EdgeToDelete] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                edges_to_delete.append(EdgeToDelete(**json.loads(raw_line)))
        return edges_to_delete

    def _read_edges_to_update(self, patch_plan_directory: Path) -> list[EdgeToUpdate]:
        file = patch_plan_directory / Path("edges_to_update.json")
        edges_to_update: list[EdgeToUpdate] = []
        for raw_line in self._read_file_lines(patch_file=file):
            if raw_line:
                edges_to_update.append(EdgeToUpdate(**json.loads(raw_line)))
        return edges_to_update

    def _read_added_node_db_id_map(self, patch_plan_directory: Path) -> dict[str, str] | None:
        file = patch_plan_directory / Path("added_db_ids.json")
        if not file.exists():
            return None
        added_db_id_json = file.read_text()
        return json.loads(added_db_id_json)
