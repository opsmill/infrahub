from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.sync import RepositorySyncer
from tests.adapters.lock import LockTimeline, RecordingImporter, RecordingLockRegistry


async def test_repository_lock_scopes_import_build_and_apply(
    prefect_test_fixture: None, git_repo_04: InfrahubRepository
) -> None:
    """The build phase of an import must run outside the lock and the apply phase inside it.

    The build phase reads file content from the per-commit worktree pinned earlier in the sync, so it
    stays outside the critical section. The apply phase mutates the graph and must be serialized
    against concurrent imports of the same repository.
    """
    branch = Branch(name="branch01", uuid=uuid4())
    registry.branch[branch.name] = branch

    timeline = LockTimeline()
    syncer = RepositorySyncer(
        lock_registry=RecordingLockRegistry(timeline=timeline), importer=RecordingImporter(timeline)
    )

    await syncer.sync(git_repo_04)

    timeline.assert_not_held_at_checkpoint(f"repository.{git_repo_04.name}", "build")
    timeline.assert_held_at_checkpoint(f"repository.{git_repo_04.name}", "apply")
