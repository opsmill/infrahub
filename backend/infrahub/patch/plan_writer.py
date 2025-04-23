import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import PatchPlanFilename
from .models import EdgeToAdd, EdgeToDelete, EdgeToUpdate, PatchPlan, VertexToAdd, VertexToDelete, VertexToUpdate


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
        if patch_plan.vertices_to_update:
            self._write_vertices_to_update(
                patch_plan_directory=patch_plan_directory, vertices_to_update=patch_plan.vertices_to_update
            )
        if patch_plan.edges_to_add:
            self._write_edges_to_add(patch_plan_directory=patch_plan_directory, edges_to_add=patch_plan.edges_to_add)
        if patch_plan.edges_to_delete:
            self._write_edges_to_delete(
                patch_plan_directory=patch_plan_directory, edges_to_delete=patch_plan.edges_to_delete
            )
        if patch_plan.edges_to_update:
            self._write_edges_to_update(
                patch_plan_directory=patch_plan_directory, edges_to_update=patch_plan.edges_to_update
            )

        return patch_plan_directory

    def write_added_db_id_map(self, patch_plan_directory: Path, db_id_map: dict[str, str]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.ADDED_DB_IDS.value)
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            f.write(json.dumps(db_id_map) + "\n")

    def write_deleted_db_ids(self, patch_plan_directory: Path, deleted_ids: set[str]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.DELETED_DB_IDS.value)
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            f.write(json.dumps(list(deleted_ids)) + "\n")

    def write_reverted_deleted_db_id_map(self, patch_plan_directory: Path, db_id_map: dict[str, str]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.REVERTED_DELETED_DB_IDS.value)
        file.touch(exist_ok=True)
        with file.open(mode="w") as f:
            f.write(json.dumps(db_id_map) + "\n")

    def _dataclass_to_json_line(self, dataclass_instance: Any) -> str:
        return json.dumps(asdict(dataclass_instance)) + "\n"

    def _write_to_file(self, file_path: Path, objects: list[Any]) -> None:
        file_path.touch(exist_ok=True)
        with file_path.open(mode="w") as f:
            for obj in objects:
                f.write(self._dataclass_to_json_line(obj))

    def _write_vertices_to_add(self, patch_plan_directory: Path, vertices_to_add: list[VertexToAdd]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.VERTICES_TO_ADD.value)
        self._write_to_file(file_path=file, objects=vertices_to_add)

    def _write_vertices_to_delete(self, patch_plan_directory: Path, vertices_to_delete: list[VertexToDelete]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.VERTICES_TO_DELETE.value)
        self._write_to_file(file_path=file, objects=vertices_to_delete)

    def _write_vertices_to_update(self, patch_plan_directory: Path, vertices_to_update: list[VertexToUpdate]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.VERTICES_TO_UPDATE.value)
        self._write_to_file(file_path=file, objects=vertices_to_update)

    def _write_edges_to_add(self, patch_plan_directory: Path, edges_to_add: list[EdgeToAdd]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.EDGES_TO_ADD.value)
        self._write_to_file(file_path=file, objects=edges_to_add)

    def _write_edges_to_delete(self, patch_plan_directory: Path, edges_to_delete: list[EdgeToDelete]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.EDGES_TO_DELETE.value)
        self._write_to_file(file_path=file, objects=edges_to_delete)

    def _write_edges_to_update(self, patch_plan_directory: Path, edges_to_update: list[EdgeToUpdate]) -> None:
        file = patch_plan_directory / Path(PatchPlanFilename.EDGES_TO_UPDATE.value)
        self._write_to_file(file_path=file, objects=edges_to_update)
