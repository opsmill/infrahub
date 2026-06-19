from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

from infrahub.git.integrator import ObjectImportPlan
from infrahub.git.sync import RepositoryImporter

if TYPE_CHECKING:
    from infrahub.git import InfrahubRepository
    from infrahub.git.repository import PendingObjectImport
    from tests.adapters.lock.timeline import LockTimeline


class RecordingImporter(RepositoryImporter):
    """Records a timeline checkpoint for each import phase, to capture the lock state at each call."""

    def __init__(self, timeline: LockTimeline) -> None:
        self._timeline = timeline

    async def build_branch_import(
        self, repo: InfrahubRepository, pending_import: PendingObjectImport
    ) -> ObjectImportPlan:
        self._timeline.checkpoint("build")
        return ObjectImportPlan(
            infrahub_branch_name=pending_import.infrahub_branch_name,
            commit=pending_import.commit or "",
            config_file=InfrahubRepositoryConfig(),
            query_strings={},
            transform_definitions=[],
            jinja2_definitions={},
            check_definitions=[],
            generator_definitions=[],
            artifact_definitions={},
        )

    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None:
        self._timeline.checkpoint("apply")
