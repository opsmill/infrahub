from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.sync import RepositorySyncer
from tests.adapters.lock import LockTimeline, RecordingImporter, RecordingLockRegistry


async def test_repository_lock_released_before_import(
    prefect_test_fixture: None, git_repo_04: InfrahubRepository
) -> None:
    """The object import must not run while the repository lock is held.

    The lock serializes mutations of the repository's on-disk git state. The import reads file
    content from the per-commit worktree pinned earlier in the sync, so it stays outside that
    critical section.
    """
    branch = Branch(name="branch01", uuid=uuid4())
    registry.branch[branch.name] = branch

    timeline = LockTimeline()
    syncer = RepositorySyncer(
        lock_registry=RecordingLockRegistry(timeline=timeline), importer=RecordingImporter(timeline)
    )

    await syncer.sync(git_repo_04)

    timeline.assert_not_held_at_checkpoint(f"repository.{git_repo_04.name}", "import")
