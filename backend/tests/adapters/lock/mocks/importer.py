from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.sync import RepositoryImporter

if TYPE_CHECKING:
    from infrahub.git import InfrahubRepository
    from infrahub.git.repository import PendingObjectImport
    from tests.adapters.lock.timeline import LockTimeline


class RecordingImporter(RepositoryImporter):
    """Records a timeline checkpoint instead of importing, to capture the lock state at the import call."""

    def __init__(self, timeline: LockTimeline) -> None:
        self._timeline = timeline

    async def import_branch(self, repo: InfrahubRepository, pending_import: PendingObjectImport) -> None:
        self._timeline.checkpoint("import")
