from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from fast_depends import Provider
from git import Repo  # type: ignore[attr-defined]
from git.exc import GitCommandError
from infrahub_sdk.client import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryError
from infrahub.git.models import GitReadOnlyRepositoryImportCommit
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.git.state.cache_keys import refs_check_announced_key
from infrahub.git.tasks import import_read_only_repository_last_commit
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.utils import find_first_file_in_directory
from infrahub.workers.dependencies import build_cache, build_message_bus
from tests.adapters.cache import ClaimAwareCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.test_client import dummy_async_request


async def test_new_empty_dir(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref="branch01",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        service=await InfrahubServices.new(),
    )

    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


@patch("infrahub.git.base.Repo.clone_from")
@patch("infrahub.git.base.Repo")
async def test_new_invalid_branch(
    mock_repo: MagicMock, mock_clone_from: MagicMock, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    mock_repo_instance = MagicMock()
    mock_repo_instance.git.checkout.side_effect = GitCommandError("checkout", stderr="error: pathspec")
    mock_repo.return_value = mock_repo_instance
    mock_clone_from.return_value = mock_repo_instance
    repo_path = str(git_upstream_repo_01["path"])
    repo_name = git_upstream_repo_01["name"]
    with pytest.raises(
        RepositoryError,
        match=f"The branch non-existent-branch isn't a valid branch for the repository {repo_name} at {repo_path}",
    ):
        await InfrahubReadOnlyRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            ref="non-existent-branch",
            infrahub_branch_name="main",
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
            service=await InfrahubServices.new(),
        )


async def test_get_commit_value(
    git_repo_01_read_only: InfrahubReadOnlyRepository, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    repo = git_repo_01_read_only
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    assert repo.get_commit_value(branch_name="does_not_matter") == branch01_commit
    assert repo.get_commit_value(branch_name="branch02", remote=True) == branch01_commit


async def test_get_commit_value_follows_a_tag_moved_upstream(
    git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
) -> None:
    """A copy already holding the tag still resolves where it points now, rather than refusing or keeping the old target."""
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.create_tag("release", ref="main", message="Release")
    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref="release",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    tagged_before = repo.get_commit_value(branch_name="release", remote=True)

    upstream.git.checkout("main")
    new_file = Path(git_upstream_repo_01["path"]) / "tagged_change.txt"
    new_file.write_text("the release tag moved upstream", encoding="utf-8")
    upstream.index.add(["tagged_change.txt"])
    moved_sha = str(upstream.index.commit("Change the release tag now points at"))
    upstream.create_tag("release", ref=moved_sha, message="Release", force=True)
    assert tagged_before != moved_sha

    assert repo.get_commit_value(branch_name="release", remote=True) == moved_sha


async def test_get_branches_from_local(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert set(local_branches.keys()) == {"main", "branch01"}


@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_sync_from_remote_new_ref(
    mock_import_objects: AsyncMock,
    git_repo_01_read_only: InfrahubReadOnlyRepository,
    git_upstream_repo_01: dict[str, str | Path],
) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch02"
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    branch02_commit = str(upstream.commit("branch02"))
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", branch01_commit, branch02_commit}
    mock_client.repository_update_commit.assert_awaited_once_with(
        branch_name="main", repository_id=repo.id, commit=branch02_commit, is_read_only=True
    )


async def test_sync_from_remote_existing_ref(
    git_repo_01_read_only: InfrahubReadOnlyRepository, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch01"
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", branch01_commit}
    mock_client.repository_update_commit.assert_not_awaited()


@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_update_latest_commit_with_annotated_tag(
    mock_import_objects: AsyncMock,
    git_upstream_repo_01: dict[str, str | Path],
    git_repos_dir: Path,
) -> None:
    """Verify that update_latest_commit stores the commit SHA, not the tag object SHA, for annotated tags."""
    upstream = Repo(git_upstream_repo_01["path"])
    tag_name = "v1.0.0"
    expected_commit = str(upstream.commit("main"))
    upstream.create_tag(tag_name, ref="main", message="Release v1.0.0")

    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref=tag_name,
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        service=await InfrahubServices.new(),
    )
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.update_latest_commit()

    mock_client.repository_update_commit.assert_awaited_with(
        branch_name="main", repository_id=repo.id, commit=expected_commit, is_read_only=True
    )


@patch("infrahub.git.tasks.get_client")
@patch("infrahub.git.tasks.add_tags")
@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_import_read_only_repository_last_commit(
    mock_import_objects: AsyncMock,
    mock_add_tags: MagicMock,
    mock_get_client: MagicMock,
    git_repo_01_read_only: InfrahubReadOnlyRepository,
    git_upstream_repo_01: dict[str, str | Path],
    dependency_provider: Provider,
) -> None:
    repo = git_repo_01_read_only
    initial_commit_id = repo.get_commit_value(branch_name="main")
    model = await _advance_upstream_main(repo=repo, git_upstream_repo_01=git_upstream_repo_01)
    mock_add_tags.return_value = None
    mock_get_client.return_value = AsyncMock(InfrahubClient)
    bus = BusRecorder()
    cache = ClaimAwareCache()

    with (
        override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await import_read_only_repository_last_commit(model=model)

    new_commit_id = repo.get_commit_value(branch_name="main")
    assert initial_commit_id != new_commit_id
    assert new_commit_id == str(Repo(git_upstream_repo_01["path"]).head.commit)
    # Only this worker fetched, so the rest of the pool is told to check out the same commit.
    assert [
        (message.infrahub_branch_name, message.infrahub_branch_id, message.commit, message.repository_kind)
        for message in bus.messages
        if isinstance(message, RefreshGitFetch)
    ] == [("main", IMPORT_BRANCH_ID, new_commit_id, InfrahubKind.READONLYREPOSITORY)]
    assert len(bus.messages) == 1
    assert cache.storage == {refs_check_announced_key(str(repo.id), branch_name="main"): new_commit_id}


@patch("infrahub.git.tasks.get_client")
@patch("infrahub.git.tasks.add_tags")
@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_import_read_only_repository_last_commit_leaves_a_failed_broadcast_unannounced(
    mock_import_objects: AsyncMock,
    mock_add_tags: MagicMock,
    mock_get_client: MagicMock,
    git_repo_01_read_only: InfrahubReadOnlyRepository,
    git_upstream_repo_01: dict[str, str | Path],
    dependency_provider: Provider,
) -> None:
    """The refs check retries a head nobody recorded, so one whose broadcast failed must stay unrecorded."""
    repo = git_repo_01_read_only
    model = await _advance_upstream_main(repo=repo, git_upstream_repo_01=git_upstream_repo_01)
    mock_add_tags.return_value = None
    mock_get_client.return_value = AsyncMock(InfrahubClient)
    cache = ClaimAwareCache()
    bus = PublishFailingBus()

    with (
        override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
        pytest.raises(ConnectionError, match=r"^broker unreachable$"),
    ):
        await import_read_only_repository_last_commit(model=model)

    assert cache.storage == {}


IMPORT_BRANCH_ID = "8808dcea-f7b4-4f5a-b5e9-a0605d4c11ba"


class PublishFailingBus(BusRecorder):
    """Fails every publish, the way a broker outage during the broadcast would."""

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        raise ConnectionError("broker unreachable")


async def _advance_upstream_main(
    repo: InfrahubReadOnlyRepository, git_upstream_repo_01: dict[str, str | Path]
) -> GitReadOnlyRepositoryImportCommit:
    """Commit to the upstream's main, and return the request to import it."""
    repo.client = AsyncMock()
    repo.ref = "main"
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.git.checkout("main")

    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    upstream.index.add([first_file])
    upstream.index.commit("Change first file")

    return GitReadOnlyRepositoryImportCommit(
        repository_id=str(repo.id),
        repository_name=str(repo.name),
        repository_kind=InfrahubKind.READONLYREPOSITORY,
        location=str(git_upstream_repo_01["path"]),
        infrahub_branch_name="main",
        infrahub_branch_id=IMPORT_BRANCH_ID,
        ref="main",
    )
