import json
import re
import shutil
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
import httpx
import pytest
from fast_depends import Provider
from git import Repo  # type: ignore[attr-defined]
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.branch import BranchData
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.uuidt import UUIDT
from pytest_httpx._httpx_mock import HTTPXMock

from infrahub.auth.session import AnonymousSession
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import (
    CheckError,
    CommitNotFoundError,
    RepositoryError,
    RepositoryFileNotFoundError,
    RepositoryInvalidBranchError,
    TransformError,
)
from infrahub.git import InfrahubRepository
from infrahub.git.base import (
    RepoFileInformation,
    extract_repo_file_information,
)
from infrahub.git.constants import BRANCHES_DIRECTORY_NAME, COMMITS_DIRECTORY_NAME, TEMPORARY_DIRECTORY_NAME
from infrahub.git.divergence.suppression import RetargetMarkers
from infrahub.git.integrator import (
    ArtifactGenerateResult,
    CheckDefinitionInformation,
)
from infrahub.git.models import GitRepositoryMerge, RequestArtifactGenerate
from infrahub.git.repository import ImportStep
from infrahub.git.sync import RepositoryFileImporter, RepositorySyncer, SyncOutcome
from infrahub.git.tasks import merge_git_repository
from infrahub.git.worktree import Worktree
from infrahub.lock import InfrahubLockRegistry
from infrahub.utils import find_first_file_in_directory
from infrahub.workers.dependencies import build_client, build_event_service, build_message_bus
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.lock import LockTimeline, RecordingImporter
from tests.adapters.repository_record_store import build_in_memory_recorder
from tests.conftest import TestHelper
from tests.helpers.dependency_override import override_dependency
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.flow import call_in_flow
from tests.helpers.git import GraphRecordingClient, build_repository_client, clone_repository, open_repository
from tests.helpers.test_client import dummy_async_request


async def test_directories_props(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    repo = await clone_repository(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    assert repo.directory_root == git_repos_dir / str(repo.id)
    assert repo.directory_branches == git_repos_dir / str(repo.id) / BRANCHES_DIRECTORY_NAME
    assert repo.directory_commits == git_repos_dir / str(repo.id) / COMMITS_DIRECTORY_NAME
    assert repo.directory_temp == git_repos_dir / str(repo.id) / TEMPORARY_DIRECTORY_NAME


async def test_new_empty_dir(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    repo = await clone_repository(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Check if all the directories are present
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
        await clone_repository(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            default_branch="non-existent-branch",
            infrahub_branch_name="main",
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )


async def test_new_existing_directory(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    # Create a directory and a file where the repository will be created
    (git_repos_dir / git_upstream_repo_01["name"]).mkdir()
    (git_repos_dir / git_upstream_repo_01["name"] / "file1.txt").touch()

    repo = await clone_repository(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Check if all the directories are present
    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


async def test_new_existing_file(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    # Create a file where the repository will be created
    (git_repos_dir / git_upstream_repo_01["name"]).touch()

    repo = await clone_repository(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Check if all the directories are present
    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


async def test_new_wrong_location(
    git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path, tmp_path: Path
) -> None:
    with pytest.raises(RepositoryError) as exc:
        await clone_repository(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(tmp_path),
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )

    assert f"fatal: repository '{tmp_path}' does not exist" in str(exc.value)


async def test_new_wrong_branch(
    git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path, tmp_path: Path
) -> None:
    with pytest.raises(RepositoryInvalidBranchError) as exc:
        await clone_repository(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            default_branch="notvalid",
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )

    assert "isn't a valid branch" in str(exc.value)


async def test_init_existing_repository(git_repo_01: InfrahubRepository) -> None:
    repo = await open_repository(
        id=git_repo_01.id,
        name=git_repo_01.name,
        location=git_repo_01.get_location(),
        client=git_repo_01.get_client(),
    )

    # Check if all the directories are present
    assert repo.has_origin is True
    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


async def test_get_git_repo_main(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    git_repo = repo.get_git_repo_main()

    assert isinstance(git_repo, Repo)


async def test_create_commit_worktree(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    # Modify the first file in the main branch to create a new commit
    first_file = find_first_file_in_directory(repo.directory_default)
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit = repo.get_commit_value(branch_name="main")

    assert repo.has_worktree(identifier=commit) is False
    assert isinstance(repo.create_commit_worktree(commit=commit), Worktree)
    assert repo.has_worktree(identifier=commit) is True
    assert repo.create_commit_worktree(commit=commit) is False


async def test_create_commit_worktree_wrong_commit(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    repo.get_git_repo_main()

    commit = "ffff1c0c64122bb2a7b208f7a9452146685bc7dd"

    with pytest.raises(CommitNotFoundError, match=rf"Commit {commit} not found with GitRepository '{repo.name}'"):
        repo.create_commit_worktree(commit=commit)


async def test_init_fetches_missing_commit_under_repo_lock(
    git_repo_01: InfrahubRepository, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    repo = git_repo_01

    # Add a commit to the upstream main after the local clone exists, without fetching it locally.
    upstream = Repo(git_upstream_repo_01["path"])
    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    upstream.index.add([first_file])
    new_commit = str(upstream.index.commit("Change first file"))

    # The local clone has not fetched the new commit, so the local primitive cannot find it.
    with pytest.raises(CommitNotFoundError, match=rf"Commit {new_commit} not found with GitRepository '{repo.name}'"):
        repo.create_commit_worktree(commit=new_commit)

    # init() recovers by fetching the missing commit and materializing its worktree.
    recovered = await open_repository(
        id=repo.id, name=repo.name, location=repo.get_location(), commit=new_commit, client=repo.get_client()
    )
    assert recovered.has_worktree(identifier=new_commit) is True


async def test_init_missing_commit_without_origin_raises(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    repo.get_git_repo_main().git.remote("remove", "origin")

    commit = "ffff1c0c64122bb2a7b208f7a9452146685bc7dd"

    with pytest.raises(CommitNotFoundError, match=rf"Commit {commit} not found with GitRepository '{repo.name}'"):
        await open_repository(
            id=repo.id, name=repo.name, location=repo.get_location(), commit=commit, client=repo.get_client()
        )


async def test_init_missing_commit_absent_on_remote_raises(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    commit = "ffff1c0c64122bb2a7b208f7a9452146685bc7dd"

    # The commit exists neither locally nor on the remote, so init fetches once and still raises.
    with pytest.raises(CommitNotFoundError, match=rf"Commit {commit} not found with GitRepository '{repo.name}'"):
        await open_repository(
            id=repo.id, name=repo.name, location=repo.get_location(), commit=commit, client=repo.get_client()
        )


async def test_get_worktrees(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    worktrees = repo.get_worktrees()

    assert len(worktrees) == 2
    assert isinstance(worktrees[0], Worktree)
    assert worktrees[0].directory.is_relative_to(repo.directory_root)
    assert worktrees[0].identifier == "main"
    assert len(worktrees[1].identifier) == 40


async def test_has_worktree(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    assert not repo.has_worktree("notvalid")
    assert repo.has_worktree("main")


async def test_get_commit_worktree(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    # Modify the first file in the main branch to create a new commit
    first_file = find_first_file_in_directory(repo.directory_default)
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit = repo.get_commit_value(branch_name="main")

    assert repo.has_worktree(identifier=commit) is False
    worktree = repo.get_commit_worktree(commit=commit)
    assert isinstance(worktree, Worktree)
    assert repo.has_worktree(identifier=commit) is True


async def test_get_branch_worktree(git_repo_01: InfrahubRepository, branch99: BranchData) -> None:
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    git_repo.git.branch(branch99.name)

    assert repo.has_worktree(identifier=branch99.name) is False
    repo.create_branch_worktree(branch_name=branch99.name, branch_id=branch99.id)
    assert repo.has_worktree(identifier=branch99.name)


async def test_get_branches_from_local(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert sorted(local_branches.keys()) == ["main"]


async def test_get_branches_from_remote(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01

    remote_branches = repo.get_branches_from_remote()
    assert isinstance(remote_branches, dict)
    assert sorted(remote_branches.keys()) == ["branch01", "branch02", "clean-branch", "main"]


async def test_get_branches_from_graph(
    git_repo_01_w_client: InfrahubRepository,
    mock_branches_list_query: HTTPXMock,
    mock_schema_query_01: HTTPXMock,
    mock_repositories_query: HTTPXMock,
) -> None:
    repo = git_repo_01_w_client

    branches = await repo.get_branches_from_graph()
    assert isinstance(branches, dict)
    assert len(branches) == 2
    assert branches["cr1234"].commit == "bbbbbbbbbbbbbbbbbbbb"


async def test_get_commit_value(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    commit_main = repo.get_commit_value(branch_name="main", remote=True)
    commit_branch01 = repo.get_commit_value(branch_name="branch01", remote=True)
    commit_branch02 = repo.get_commit_value(branch_name="branch02", remote=True)

    # Each value should be a full 40-character SHA
    assert re.fullmatch(r"[0-9a-f]{40}", commit_main)
    assert re.fullmatch(r"[0-9a-f]{40}", commit_branch01)
    assert re.fullmatch(r"[0-9a-f]{40}", commit_branch02)

    # Each branch should be at a distinct commit
    assert len({commit_main, commit_branch01, commit_branch02}) == 3

    with pytest.raises(ValueError):
        repo.get_commit_value(branch_name="branch01", remote=False)


async def test_compare_remote_local_new_branches(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    new_branches, updated_branches = await repo.compare_local_remote()

    assert new_branches == ["branch01", "branch02", "clean-branch"]
    assert updated_branches == []


async def test_compare_remote_local_no_diff(git_repo_02: InfrahubRepository) -> None:
    repo = git_repo_02
    new_branches, updated_branches = await repo.compare_local_remote()

    assert new_branches == []
    assert updated_branches == []


async def test_create_branch_in_git_present_remote(git_repo_01: InfrahubRepository, branch01: BranchData) -> None:
    repo = git_repo_01
    expected_commit = repo.get_commit_value(branch_name=branch01.name, remote=True)
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name=branch01.name) == expected_commit
    assert len(worktrees) == 4


async def test_create_branch_in_git_not_in_remote(git_repo_01: InfrahubRepository, branch99: BranchData) -> None:
    repo = git_repo_01
    expected_commit = repo.get_commit_value(branch_name="main", remote=True)
    await repo.create_branch_in_git(branch_name=branch99.name, branch_id=branch99.id)
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name=branch99.name) == expected_commit
    assert len(worktrees) == 3


@pytest.mark.xfail(reason="Failing at reproducing conflicts without remote branches to trigger the function to test")
async def test_has_conflicting_changes(git_repos_source_dir_module_scope: Path) -> None:
    test_repo = MultipleStagesFileRepo(name="conflicting-branches", sources_directory=git_repos_source_dir_module_scope)
    repository = await clone_repository(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    assert repository.has_conflicting_changes(target_branch="main", source_branch="change1")


async def test_pull_branch(git_repo_04: InfrahubRepository) -> None:
    repo = git_repo_04
    await repo.fetch()

    branch_name = "branch01"

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)
    assert str(commit1) != str(commit2)

    response = await repo.pull(branch_name=branch_name)
    commit11 = repo.get_commit_value(branch_name=branch_name, remote=False)
    assert str(commit11) == str(commit2)
    assert response == str(commit2)

    response = await repo.pull(branch_name=branch_name)
    assert response is True


async def test_pull_fast_forwards_whatever_the_pull_settings_of_the_clone(git_repo_04: InfrahubRepository) -> None:
    """A pull setting that asks for a merge commit leaves a fast-forward of the worktree a fast-forward."""
    repo = git_repo_04
    with repo.get_git_repo_main().config_writer() as git_config:
        git_config.set_value("pull", "ff", "false")
    remote_commit = repo.get_commit_value(branch_name="branch01", remote=True)

    response = await repo.pull(branch_name="branch01")

    assert response == remote_commit
    assert repo.get_commit_value(branch_name="branch01", remote=False) == remote_commit


async def test_pull_new_branch(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    await repo.fetch()

    branch_name = "branch02"

    response = await repo.pull(
        branch_name=branch_name,
        branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
        create_if_missing=True,
        update_commit_value=False,
    )
    assert response

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)

    assert commit1 == commit2 == response

    response = await repo.pull(
        branch_name=branch_name,
        branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
        create_if_missing=True,
        update_commit_value=False,
    )
    assert response is True


async def test_pull_new_branch_updates_commit_value(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    await repo.fetch()

    branch_name = "branch02"

    response = await repo.pull(
        branch_name=branch_name,
        branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
        create_if_missing=True,
        update_commit_value=True,
    )

    commit = repo.get_commit_value(branch_name=branch_name, remote=False)
    assert response == commit


async def test_pull_resets_a_diverged_branch_onto_the_remote_head(git_repo_06: InfrahubRepository) -> None:
    repo = git_repo_06
    await repo.fetch()

    branch_name = "branch01"

    local_commit = repo.get_commit_value(branch_name=branch_name, remote=False)
    remote_commit = repo.get_commit_value(branch_name=branch_name, remote=True)
    git_repo = repo.get_git_repo_main()
    assert not git_repo.is_ancestor(local_commit, remote_commit)
    assert not git_repo.is_ancestor(remote_commit, local_commit)

    response = await repo.pull(branch_name=branch_name)

    assert response == remote_commit
    assert repo.get_commit_value(branch_name=branch_name, remote=False) == remote_commit
    assert repo.has_worktree(identifier=remote_commit)


@dataclass
class RewoundPullCase:
    name: str
    update_commit_value: bool
    writes_the_commit: bool


@pytest.mark.parametrize(
    "case",
    [
        RewoundPullCase(name="commit-written", update_commit_value=True, writes_the_commit=True),
        RewoundPullCase(name="commit-not-written", update_commit_value=False, writes_the_commit=False),
    ],
    ids=lambda case: case.name,
)
async def test_pull_resets_a_branch_the_remote_rewound(
    git_repo_01: InfrahubRepository, branch01: BranchData, case: RewoundPullCase
) -> None:
    """The worktree holds a commit the remote dropped, as after a force push that removes the last commit."""
    repo = git_repo_01
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    remote_commit = repo.get_commit_value(branch_name=branch01.name, remote=True)

    worktree = repo.get_git_repo_worktree(identifier=branch01.name)
    (Path(str(worktree.working_dir)) / "dropped.txt").write_text("dropped by the remote\n", encoding="utf-8")
    worktree.index.add(["dropped.txt"])
    dropped_commit = str(worktree.index.commit("A commit the remote no longer holds"))
    assert repo.get_git_repo_main().is_ancestor(remote_commit, dropped_commit)

    client = GraphRecordingClient(branch_names=())
    repo.client = client

    response = await repo.pull(branch_name=branch01.name, update_commit_value=case.update_commit_value)

    assert response == remote_commit
    assert repo.get_commit_value(branch_name=branch01.name, remote=False) == remote_commit
    assert repo.has_worktree(identifier=remote_commit)
    assert client.recorded_commits == ([(branch01.name, remote_commit)] if case.writes_the_commit else [])


async def test_pull_main(git_repo_05: InfrahubRepository) -> None:
    repo = git_repo_05
    await repo.fetch()

    branch_name = "main"

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)
    assert str(commit1) != str(commit2)

    response = await repo.pull(branch_name=branch_name)
    commit11 = repo.get_commit_value(branch_name=branch_name, remote=False)
    assert str(commit11) == str(commit2)
    assert response == str(commit2)


async def test_merge_branch01_into_main(git_repo_01: InfrahubRepository, branch01: BranchData) -> None:
    repo = git_repo_01
    await repo.fetch()
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    commit_before = repo.get_commit_value(branch_name="main", remote=False)

    response = await repo.merge(source_branch=branch01.name, dest_branch="main")

    commit_after = repo.get_commit_value(branch_name="main", remote=False)
    assert str(commit_before) != str(commit_after)
    assert response == str(commit_after)


async def test_merge_writes_back_to_non_main_default_branch(
    git_upstream_repo_01: dict[str, str | Path],
    git_repos_dir: Path,
    branch01: BranchData,
) -> None:
    """Merging into Infrahub main writes the merge commit back to a non-main git default branch.

    Reproduces a worker whose clone only ever checked out `main`, so it holds `develop` only as a
    remote-tracking ref with no local branch of that name -- the state a worker is left in when the
    configured trunk is changed after it cloned. The push that maps Infrahub `main` onto the
    configured git default branch must still advance the remote `develop`.
    """
    upstream_path = str(git_upstream_repo_01["path"])
    upstream = Repo(upstream_path)
    upstream.git.branch("develop", "main")

    repo_id = UUIDT.new()
    client = InfrahubClient(config=Config(requester=dummy_async_request))
    await clone_repository(
        id=repo_id,
        name=git_upstream_repo_01["name"],
        location=upstream_path,
        default_branch="main",
        client=client,
    )

    # The trunk has since been changed to `develop`, so the next construction resolves it while the
    # on-disk clone still has only a local `main`.
    repo = await open_repository(
        id=repo_id,
        name=git_upstream_repo_01["name"],
        location=upstream_path,
        default_branch="develop",
        client=client,
    )
    await repo.fetch()

    local_branch_names = {branch.name for branch in repo.get_git_repo_main().branches}
    assert local_branch_names == {"main"}

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    develop_before = Repo(upstream_path).commit("develop").hexsha
    merge_commit = await repo.merge(source_branch=branch01.name, dest_branch="main")

    assert merge_commit != develop_before
    assert Repo(upstream_path).commit("develop").hexsha == merge_commit


async def test_merge_flow_advances_the_trunk_without_a_trunk_on_the_model(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    dependency_provider: Provider,
    prefect_test_fixture: None,
    git_upstream_repo_01: dict[str, str | Path],
    git_repos_dir: Path,
    branch01: BranchData,
    helper: TestHelper,
) -> None:
    """The merge flow resolves the trunk itself now that the merge model no longer carries one.

    Asserts the remote trunk ref advanced, and that the node was read on the destination branch.
    """
    upstream_path = str(git_upstream_repo_01["path"])
    Repo(upstream_path).git.branch("develop", "main")
    develop_before = Repo(upstream_path).commit("develop").hexsha

    repo_node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repo_node.new(db=db, name=git_upstream_repo_01["name"], location=upstream_path, default_branch="develop")
    await repo_node.save(db=db)

    client = build_repository_client(
        repository_id=repo_node.id,
        name=str(git_upstream_repo_01["name"]),
        location=upstream_path,
        default_branch="develop",
        commit=develop_before,
    )
    repo = await clone_repository(
        id=repo_node.id,
        name=git_upstream_repo_01["name"],
        location=upstream_path,
        default_branch="main",
        client=client,
    )
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    model = GitRepositoryMerge(
        repository_id=repo_node.id,
        repository_name=str(git_upstream_repo_01["name"]),
        source_branch=branch01.name,
        destination_branch=default_branch.name,
        destination_branch_id=str(default_branch.get_uuid()),
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        repository_kind=InfrahubKind.REPOSITORY,
        source_commit=repo.get_commit_value(branch_name=branch01.name),
    )
    assert "default_branch" not in model.model_dump()

    bus_simulator = await helper.get_message_bus_simulator()
    with (
        dependency_provider.scope(build_client, lambda: client),
        dependency_provider.scope(build_message_bus, lambda: bus_simulator),
    ):
        await merge_git_repository(model=model)

    assert Repo(upstream_path).commit("develop").hexsha != develop_before


async def test_rebase(git_repo_01: InfrahubRepository, branch01: BranchData) -> None:
    repo = git_repo_01
    await repo.fetch()

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    # Add a new commit in the main branch to have something to rebase.
    git_repo = repo.get_git_repo_main()
    first_file = find_first_file_in_directory(repo.directory_default)
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit_before = repo.get_commit_value(branch_name=branch01.name, remote=False)
    response = await repo.rebase(branch_name=branch01.name, source_branch="main")

    commit_after = repo.get_commit_value(branch_name=branch01.name, remote=False)

    assert str(commit_before) != str(commit_after)
    assert str(response) == str(commit_after)


async def _sync(repo: InfrahubRepository, staging_branch: str | None = None) -> SyncOutcome:
    syncer = RepositorySyncer(
        lock_registry=InfrahubLockRegistry(local_only=True),
        importer=RepositoryFileImporter(),
        recorder=build_in_memory_recorder(),
        retarget_markers=RetargetMarkers(cache=MemoryCache()),
    )
    return await call_in_flow(lambda: syncer.sync(repo, staging_branch=staging_branch))


async def test_sync_no_update(git_repo_02: InfrahubRepository) -> None:
    repo = git_repo_02
    outcome = await _sync(repo)

    assert outcome.failed == ()


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_sync_new_branch(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_03: InfrahubRepository,
    httpx_mock: HTTPXMock,
    mock_add_branch01_query: HTTPXMock,
    mock_branch_all: AsyncMock,
) -> None:
    repo = git_repo_03

    await repo.fetch()
    # Mock update_commit_value query
    branch = Branch(name="branch01", uuid=uuid4())
    registry.branch[branch.name] = branch
    commit = repo.get_commit_value(branch_name=branch.name, remote=True)

    commit_response = {"data": {"repository_update": {"ok": True, "object": {"commit": {"value": str(commit)}}}}}
    httpx_mock.add_response(
        method="POST", json=commit_response, match_headers={"X-Infrahub-Tracker": "mutation-repository-update-commit"}
    )
    admin_response = {"data": {"CoreGenericRepositoryUpdate": {"ok": True}}}
    # Note: The admin-status endpoint is only called from within import_objects_from_files,
    # which we're mocking below, so we don't need to mock it here.
    httpx_mock.add_response(
        method="POST",
        json=admin_response,
        match_headers={"X-Infrahub-Tracker": "mutation-repository-update-operational-status"},
    )

    repo.client = client
    # Skip the object import (build + apply phases) since we're testing git sync, not import functionality
    with (
        patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.build_import_plan", new_callable=AsyncMock),
        patch(
            "infrahub.git.integrator.InfrahubRepositoryIntegrator.apply_import_plan", new_callable=AsyncMock
        ) as mock_apply,
    ):
        outcome = await _sync(repo)
        mock_apply.assert_awaited()
    assert outcome.failed == ()
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name=branch.name) == commit
    assert len(worktrees) == 4


async def test_sync_updated_branch(
    prefect_test_fixture: None, git_repo_04: InfrahubRepository, mock_branch_all: AsyncMock
) -> None:
    repo = git_repo_04

    branch = Branch(name="branch01", uuid=uuid4())
    registry.branch[branch.name] = branch

    # Mock update_commit_value query
    commit = repo.get_commit_value(branch_name="branch01", remote=True)

    # Skip the object import (build + apply phases) since we're testing git sync, not import functionality
    with (
        patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.build_import_plan", new_callable=AsyncMock),
        patch(
            "infrahub.git.integrator.InfrahubRepositoryIntegrator.apply_import_plan", new_callable=AsyncMock
        ) as mock_apply,
    ):
        outcome = await _sync(repo)
        mock_apply.assert_awaited()
    assert outcome.failed == ()

    assert repo.get_commit_value(branch_name="branch01") == str(commit)


async def test_sync_returns_a_failed_branch_alongside_the_branches_it_advanced(
    prefect_test_fixture: None, git_repo_07: InfrahubRepository, mock_branch_all: AsyncMock
) -> None:
    """A branch whose collection fails is returned as failed, and the remaining branches still advance."""
    repo = git_repo_07

    for branch_name in ["branch01", "branch02"]:
        branch = Branch(name=branch_name, uuid=uuid4())
        registry.branch[branch.name] = branch

    # The diverged branch01 is reset onto its remote head, which then fails to get a commit worktree.
    blocked_commit = repo.get_commit_value(branch_name="branch01", remote=True)
    (repo.directory_commits / blocked_commit).mkdir()
    (repo.directory_commits / blocked_commit / "blocker.txt").write_text("blocking worktree creation\n")

    remote_commit_branch02 = repo.get_commit_value(branch_name="branch02", remote=True)
    assert repo.get_commit_value(branch_name="branch02", remote=False) != str(remote_commit_branch02)

    # The importer reads nothing, so only the collection of branch01 can fail.
    syncer = RepositorySyncer(
        lock_registry=InfrahubLockRegistry(local_only=True),
        importer=RecordingImporter(LockTimeline()),
        recorder=build_in_memory_recorder(),
        retarget_markers=RetargetMarkers(cache=MemoryCache()),
    )
    outcome = await syncer.sync(repo)

    assert [(failed.branch_name, failed.step) for failed in outcome.failed] == [("branch01", ImportStep.COLLECTION)]
    assert [(branch.infrahub_branch_name, branch.commit) for branch in outcome.reconciled] == [
        ("branch02", str(remote_commit_branch02))
    ]
    assert outcome.report.imported_branches == ("branch02",)
    assert repo.get_commit_value(branch_name="branch02", remote=False) == str(remote_commit_branch02)


async def test_render_jinja2_template_success(prefect_test_fixture: None, git_repo_jinja: InfrahubRepository) -> None:
    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    commit_branch = repo.get_commit_value(branch_name="branch01", remote=False)
    assert commit_main != commit_branch

    data = {"data": {"items": ["consilium", "potum", "album", "magnum"]}}
    expected_response = """
consilium
potum
album
magnum
"""
    # Render in both branches based on the commit and validate that we are getting different results
    rendered_tpl_main = await repo.render_jinja2_template(commit=commit_main, location="template01.tpl.j2", data=data)
    assert rendered_tpl_main == expected_response

    rendered_tpl_branch = await repo.render_jinja2_template(
        commit=commit_branch, location="template01.tpl.j2", data=data
    )
    assert rendered_tpl_main != rendered_tpl_branch


async def test_render_jinja2_template_error(prefect_test_fixture: None, git_repo_jinja: InfrahubRepository) -> None:
    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(TransformError) as exc:
        await repo.render_jinja2_template(commit=commit_main, location="template02.tpl.j2", data={})

    assert "The innermost block that needs to be closed" in str(exc.value)


async def test_render_jinja2_template_missing(
    client: InfrahubClient, prefect_test_fixture: None, git_repo_jinja: InfrahubRepository
) -> None:
    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(RepositoryFileNotFoundError):
        await repo.render_jinja2_template(commit=commit_main, location="notthere.tpl.j2", data={})


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_execute_python_check_valid(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_checks: InfrahubRepository,
    mock_gql_query_my_query: HTTPXMock,
) -> None:
    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    check = await repo.execute_python_check(
        branch_name="main", commit=commit_main, location="check01.py", class_name="Check01", client=client
    )

    assert check.passed is False


async def test_execute_python_check_file_missing(
    client: InfrahubClient, prefect_test_fixture: None, git_repo_checks: InfrahubRepository
) -> None:
    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(RepositoryFileNotFoundError):
        await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="notthere.py", class_name="Check01", client=client
        )


async def test_execute_python_check_class_missing(
    client: InfrahubClient, prefect_test_fixture: None, git_repo_checks: InfrahubRepository
) -> None:
    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(CheckError):
        await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="check01.py", class_name="Check99", client=client
        )


async def test_execute_python_transform_w_data(
    client: InfrahubClient, prefect_test_fixture: None, git_repo_transforms: InfrahubRepository
) -> None:
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    data = {"key1": "value1", "key2": "value2"}
    expected_data = {"KEY1": "value1", "KEY2": "value2"}

    result = await repo.execute_python_transform(
        branch_name="main",
        data=data,
        commit=commit_main,
        location="transform01.py::Transform01",
        client=client,
        convert_query_response=False,
    )

    assert result == expected_data


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_execute_python_transform_w_query(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_transforms: InfrahubRepository,
    mock_gql_query_my_query: HTTPXMock,
) -> None:
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    expected_data = {"MOCK": []}

    result = await repo.execute_python_transform(
        branch_name="main",
        commit=commit_main,
        location="transform01.py::Transform01",
        client=client,
        convert_query_response=False,
    )

    assert result == expected_data


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_artifact_generate_python_new(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_01: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
    mock_upload_content: HTTPXMock,
    mock_update_artifact: HTTPXMock,
) -> None:
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=result.artifact_id,
    )
    assert result == expected_data


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_artifact_generate_python_existing_same(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_02: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
) -> None:
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_02,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=False,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="13c8914b-0ac0-4c8c-83ec-a79a1f8ad483",
        artifact_id=artifact_node_02.id,
    )
    assert result == expected_data


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_artifact_generate_python_existing_different(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    artifact_node_01: InfrahubNode,
    car_node_01: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
    mock_upload_content: HTTPXMock,
    mock_update_artifact: HTTPXMock,
) -> None:
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=artifact_node_01.id,
    )
    assert result == expected_data


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_artifact_generate_jinja2_new(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_jinja_w_client: InfrahubRepository,
    transformation_node_02: InfrahubNode,
    artifact_definition_node_02: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_01: InfrahubNode,
    mock_gql_query_04: HTTPXMock,
    mock_update_artifact: HTTPXMock,
    mock_upload_content: HTTPXMock,
) -> None:
    repo = git_repo_jinja_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_02,
        transformation=transformation_node_02,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="5032217684d0e0b61d93c8611bffcd8a",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=artifact_node_01.id,
    )
    assert result == expected_data


async def test_render_artifact_python_without_payload(
    client: InfrahubClient,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    artifact_node_01: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
) -> None:
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    branch = Branch(name="main", uuid=uuid4())
    registry.branch[branch.name] = branch

    message = RequestArtifactGenerate(
        artifact_name="myartifact",
        artifact_definition="c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        artifact_definition_name="artifactdef01",
        commit=commit_main,
        content_type="text/plain",
        transform_type=InfrahubKind.TRANSFORMPYTHON,
        transform_location="transform03.py::Transform03",
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=branch.name,
        target_id="b663d7a4-5f95-48dd-b04d-e03169e7fcf3",
        target_kind="TestElectricCar",
        target_name="bolt",
        query="my_query",
        query_id="47800bff-adf1-450d-8388-b04ef2ffb129",
        timeout=10,
        variables={"name": "bolt"},
        context=InfrahubContext(branch=BranchContext(name=branch.name), account=AnonymousSession()),
    )

    with pytest.raises(
        TransformError, match=r"^The transform at transform03\.py::Transform03 did not return a payload$"
    ):
        await repo.render_artifact(artifact=artifact_node_01, artifact_created=True, message=message)

    assert artifact_node_01.status.value == "Pending"
    assert artifact_node_01.checksum.value is None
    assert artifact_node_01.storage_id.value is None


STORED_ARTIFACT_URL = "http://mock/api/storage/object/13c8914b-0ac0-4c8c-83ec-a79a1f8ad483"
RENDERED_CHECKSUM = "e889b9fab24aab3b23ea01d5342b514a"
RENDERED_CONTENT = '{\n  "KEY1": "value1",\n  "KEY2": "value2"\n}'


@pytest.fixture
def main_branch(monkeypatch: pytest.MonkeyPatch) -> Branch:
    branch = Branch(name="main", uuid=uuid4())
    monkeypatch.setitem(registry.branch, branch.name, branch)
    return branch


@pytest.fixture
def event_recorder(dependency_provider: Provider) -> Generator[MemoryInfrahubEvent, None, None]:
    recorder = MemoryInfrahubEvent()
    with override_dependency(build_event_service, lambda: recorder, dependency_provider=dependency_provider):
        yield recorder


def render_again_request(repo: InfrahubRepository, branch: Branch, check_stored_file: bool) -> RequestArtifactGenerate:
    """Request rendering the stored artifact again with the Transformation that produced its recorded checksum."""
    return RequestArtifactGenerate(
        artifact_name="artifact01",
        artifact_definition="c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        artifact_definition_name="artifactdef01",
        commit=repo.get_commit_value(branch_name=branch.name, remote=False),
        content_type="application/json",
        transform_type=InfrahubKind.TRANSFORMPYTHON,
        transform_location="transform01.py::Transform01",
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=branch.name,
        target_id="b663d7a4-5f95-48dd-b04d-e03169e7fcf3",
        target_kind="TestElectricCar",
        target_name="bolt",
        query="my_query",
        query_id="47800bff-adf1-450d-8388-b04ef2ffb129",
        timeout=10,
        variables={"name": "bolt"},
        context=InfrahubContext(branch=BranchContext(name=branch.name), account=AnonymousSession()),
        check_stored_file=check_stored_file,
    )


@pytest.mark.parametrize("check_stored_file", [False, True], ids=["not-checked", "checked-and-intact"])
@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_render_artifact_unchanged_keeps_the_stored_file(
    check_stored_file: bool,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    artifact_node_02: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
    main_branch: Branch,
    event_recorder: MemoryInfrahubEvent,
    httpx_mock: HTTPXMock,
) -> None:
    if check_stored_file:
        httpx_mock.add_response(
            method="GET",
            url=STORED_ARTIFACT_URL,
            text=RENDERED_CONTENT,
            match_headers={"X-Infrahub-Tracker": "artifact-verify-content"},
        )

    result = await git_repo_transforms_w_client.render_artifact(
        artifact=artifact_node_02,
        artifact_created=False,
        message=render_again_request(
            repo=git_repo_transforms_w_client, branch=main_branch, check_stored_file=check_stored_file
        ),
    )

    assert result == ArtifactGenerateResult(
        changed=False,
        checksum=RENDERED_CHECKSUM,
        storage_id="13c8914b-0ac0-4c8c-83ec-a79a1f8ad483",
        artifact_id=artifact_node_02.id,
    )
    assert len(httpx_mock.get_requests(method="GET", url=STORED_ARTIFACT_URL)) == int(check_stored_file)
    assert event_recorder.events == []


@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (404, '{"data": null, "errors": [{"message": "Unable to find the node", "extensions": {"code": 404}}]}'),
        (409, '{"data": null, "errors": [{"message": "does not match its checksum", "extensions": {"code": 409}}]}'),
        (200, '{\n  "KEY1": "modified in the object storage"\n}'),
    ],
    ids=["missing", "refused", "modified-and-served"],
)
@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_render_artifact_unchanged_stores_a_bad_stored_file_again_when_checked(
    status_code: int,
    body: str,
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    artifact_node_02: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
    mock_upload_content: HTTPXMock,
    mock_update_artifact: HTTPXMock,
    main_branch: Branch,
    event_recorder: MemoryInfrahubEvent,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=STORED_ARTIFACT_URL,
        status_code=status_code,
        text=body,
        match_headers={"X-Infrahub-Tracker": "artifact-verify-content"},
    )

    result = await git_repo_transforms_w_client.render_artifact(
        artifact=artifact_node_02,
        artifact_created=False,
        message=render_again_request(repo=git_repo_transforms_w_client, branch=main_branch, check_stored_file=True),
    )

    assert result == ArtifactGenerateResult(
        changed=True,
        checksum=RENDERED_CHECKSUM,
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=artifact_node_02.id,
    )
    updates = httpx_mock.get_requests(
        method="POST", match_headers={"X-Infrahub-Tracker": "mutation-coreartifact-update"}
    )
    assert len(updates) == 1
    assert re.search(
        r'storage_id: \{\s+value: "ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a"\s+\}', json.loads(updates[0].content)["query"]
    )
    assert len(event_recorder.events) == 1


@pytest.mark.httpx_mock(should_mock=lambda request: "prefect" not in request.headers.get("User-Agent", ""))
async def test_render_artifact_unchanged_fails_when_the_checked_stored_file_is_unreadable(
    prefect_test_fixture: None,
    git_repo_transforms_w_client: InfrahubRepository,
    artifact_node_02: InfrahubNode,
    mock_gql_query_03: HTTPXMock,
    main_branch: Branch,
    event_recorder: MemoryInfrahubEvent,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=STORED_ARTIFACT_URL,
        status_code=500,
        json={"data": None, "errors": [{"message": "storage unavailable", "extensions": {"code": 500}}]},
        match_headers={"X-Infrahub-Tracker": "artifact-verify-content"},
    )

    with pytest.raises(httpx.HTTPStatusError, match="500 Internal Server Error"):
        await git_repo_transforms_w_client.render_artifact(
            artifact=artifact_node_02,
            artifact_created=False,
            message=render_again_request(repo=git_repo_transforms_w_client, branch=main_branch, check_stored_file=True),
        )

    assert artifact_node_02.storage_id.value == "13c8914b-0ac0-4c8c-83ec-a79a1f8ad483"
    assert event_recorder.events == []


async def test_execute_python_transform_file_missing(
    client: InfrahubClient, prefect_test_fixture: None, git_repo_transforms: InfrahubRepository
) -> None:
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(RepositoryFileNotFoundError):
        await repo.execute_python_transform(
            branch_name="main",
            commit=commit_main,
            location="transform99.py::Transform01",
            client=client,
            convert_query_response=False,
        )


async def test_find_files(git_repo_jinja: InfrahubRepository) -> None:
    repo = git_repo_jinja

    with pytest.raises(ValueError):
        await repo.find_files(extension="yml")

    yaml_files = await repo.find_files(extension="yml", branch_name="main")
    assert len(yaml_files) == 4  # 2 in test_files/ + .infrahub.yml matched twice by both glob patterns

    yaml_files = await repo.find_files(extension=["yml"], branch_name="main")
    assert len(yaml_files) == 4  # 2 in test_files/ + .infrahub.yml matched twice by both glob patterns

    yaml_files = await repo.find_files(extension=["yml", "j2"], branch_name="main")
    assert len(yaml_files) == 6  # 4 yml + 2 j2

    yaml_files = await repo.find_files(extension="yml", directory=Path("test_files"), branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension="yml", directory=Path("notpresent"), branch_name="main")
    assert len(yaml_files) == 0


async def test_find_files_by_commit(git_repo_jinja: InfrahubRepository) -> None:
    repo = git_repo_jinja

    commit = repo.get_commit_value(branch_name="main")

    yaml_files = await repo.find_files(extension="yml", commit=commit)
    assert len(yaml_files) == 4  # 2 in test_files/ + .infrahub.yml matched twice by both glob patterns

    yaml_files = await repo.find_files(extension=["yml"], branch_name=commit)
    assert len(yaml_files) == 4  # 2 in test_files/ + .infrahub.yml matched twice by both glob patterns

    yaml_files = await repo.find_files(extension=["yml", "j2"], branch_name=commit)
    assert len(yaml_files) == 6  # 4 yml + 2 j2


async def test_calculate_diff_between_commits(
    git_repo_01: InfrahubRepository, branch01: BranchData, branch02: BranchData
) -> None:
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)

    worktree = repo.get_worktree(identifier=branch01.name)
    git_repo = repo.get_git_repo_worktree(identifier=branch01.name)

    # Add a file
    new_file = "mynewfile.txt"
    (worktree.directory / new_file).write_text("this is a new file\n", encoding="utf-8")

    # Remove a file
    file_to_remove = "pyproject.toml"
    (worktree.directory / file_to_remove).unlink()

    git_repo.index.add([new_file])
    git_repo.index.remove([file_to_remove])

    git_repo.index.commit("Add 1, remove 1")

    # TODO Need to move this code, it's useful to modify a file in the repo
    # for branch in ["branch01", "branch02"]:

    #     worktree = repo.get_worktree(identifier=branch)
    #     git_repo = repo.get_git_repo_worktree(identifier=branch)

    #     sports_file = worktree.directory / "test_files" / "sports.yml"

    #     with open(sports_file, 'r') as file:
    #         data = file.readlines()

    #     # now change the 2nd line, note that you have to add a newline
    #     data[1] = f'sports_{branch}:\n'

    #     # and write everything back
    #     with open(sports_file, 'w') as file:
    #         file.writelines( data )

    #     git_repo.index.add([sports_file])
    #     git_repo.index.commit("Change sport file")

    # repo.merge(source_branch="branch01", dest_branch="main", push_remote=False)

    # commit_main = repo.get_commit_value(branch_name="main", remote=False)

    commit_branch01 = repo.get_commit_value(branch_name=branch01.name, remote=False)
    commit_branch02 = repo.get_commit_value(branch_name=branch02.name, remote=False)

    # branch02 is the base, branch01 holds the changes; first_commit is the old side, second_commit the new.
    changed, added, removed = await repo.calculate_diff_between_commits(
        first_commit=commit_branch02, second_commit=commit_branch01
    )
    assert changed == ["README.md", "test_files/sports.yml"]
    assert added == ["mynewfile.txt"]
    assert removed == ["pyproject.toml"]


async def test_list_all_files(git_repo_01: InfrahubRepository, branch01: BranchData, branch02: BranchData) -> None:
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)

    worktree = repo.get_worktree(identifier=branch01.name)
    git_repo = repo.get_git_repo_worktree(identifier=branch01.name)

    # Add a file
    new_file = "mynewfile.txt"
    (worktree.directory / new_file).write_text("this is a new file\n", encoding="utf-8")

    # Remove a file
    file_to_remove = "pyproject.toml"
    (worktree.directory / file_to_remove).unlink()

    git_repo.index.add([new_file])
    git_repo.index.remove([file_to_remove])

    git_repo.index.commit("Add 1, remove 1")

    commit_branch01 = repo.get_commit_value(branch_name=branch01.name, remote=False)
    commit_branch02 = repo.get_commit_value(branch_name=branch02.name, remote=False)

    branch01_files = await repo.list_all_files(commit=commit_branch01)
    branch02_files = await repo.list_all_files(commit=commit_branch02)

    assert branch01_files == [
        ".gitignore",
        ".infrahub.yml",
        "README.md",
        "mynewfile.txt",
        "poetry.lock",
        "tasks.py",
        "test_files/countries.yml",
        "test_files/sports.yml",
    ]
    assert branch02_files == [
        ".gitignore",
        ".infrahub.yml",
        "README.md",
        "poetry.lock",
        "pyproject.toml",
        "tasks.py",
        "test_files/countries.yml",
        "test_files/sports.yml",
    ]


def test_extract_repo_file_information(tmp_path_module_scope: Path) -> None:
    file_info = extract_repo_file_information(
        full_filename=tmp_path_module_scope / "dir1/dir2/dir3/myfile.py",
        repo_directory=tmp_path_module_scope,
        worktree_directory=tmp_path_module_scope / "dir1",
    )

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_path_dir == "dir2/dir3"
    assert file_info.relative_repo_path_dir == "dir1/dir2/dir3"
    assert file_info.absolute_path_dir == str(tmp_path_module_scope / "dir1/dir2/dir3")
    assert file_info.relative_path_file == "dir2/dir3/myfile.py"
    assert file_info.module_name == "dir1.dir2.dir3.myfile"

    file_info = extract_repo_file_information(
        full_filename=tmp_path_module_scope / "dir1/dir2/dir3/myfile.py", repo_directory=tmp_path_module_scope / "dir1"
    )

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_repo_path_dir == "dir2/dir3"
    assert file_info.relative_path_dir == str(tmp_path_module_scope / "dir1/dir2/dir3")
    assert file_info.absolute_path_dir == str(tmp_path_module_scope / "dir1/dir2/dir3")
    assert file_info.relative_path_file == str(tmp_path_module_scope / "dir1/dir2/dir3/myfile.py")
    assert file_info.module_name == "dir2.dir3.myfile"


async def test_create_python_check_definition(
    helper: TestHelper,
    git_repo_03_w_client: InfrahubRepository,
    mock_schema_query_01: HTTPXMock,
    gql_query_data_01: dict,
    mock_check_create: HTTPXMock,
) -> None:
    repo = git_repo_03_w_client

    module = helper.import_module_in_fixtures(module="checks/check01")
    check_class = module.Check01

    assert repo.client is not None
    assert repo.client.schema is not None
    gql_schema = await repo.client.schema.get(kind=InfrahubKind.GRAPHQLQUERY)
    assert gql_schema is not None

    query = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_01)

    check = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query.id),
        timeout=check_class.timeout,
    )
    obj = await repo.create_python_check_definition(branch_name="main", check=check)

    assert isinstance(obj, InfrahubNode)


async def test_compare_python_check(
    helper: TestHelper,
    git_repo_03_w_client: InfrahubRepository,
    mock_schema_query_01: HTTPXMock,
    gql_query_data_01: dict,
    gql_query_data_02: dict,
    check_definition_data_01: dict,
) -> None:
    repo = git_repo_03_w_client

    module = helper.import_module_in_fixtures(module="checks/check01")
    check_class = module.Check01

    assert repo.client is not None
    assert repo.client.schema is not None
    gql_schema = await repo.client.schema.get(kind=InfrahubKind.GRAPHQLQUERY)
    check_schema = await repo.client.schema.get(kind=InfrahubKind.CHECKDEFINITION)
    assert gql_schema is not None
    assert check_schema is not None

    query_01 = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_01)
    query_02 = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_02)
    existing_check = InfrahubNode(client=repo.client, schema=check_schema, data=check_definition_data_01)

    check01 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query_01.id),
        timeout=check_class.timeout,
    )

    assert await repo.compare_python_check_definition(existing_check=existing_check, check=check01) is True

    check02 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/newpath.py",
        query=str(query_01.id),
        timeout=check_class.timeout,
    )

    assert (
        await repo.compare_python_check_definition(
            existing_check=existing_check,
            check=check02,
        )
        is False
    )

    check03 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query_02.id),
        timeout=check_class.timeout,
    )

    assert await repo.compare_python_check_definition(check=check03, existing_check=existing_check) is False


async def test_get_filtered_remote_branches__all_branches_exists(
    git_repo_01: InfrahubRepository, mock_create_branch_git_repo_01: None, import_sync_branch_names: None
) -> None:
    repo = git_repo_01
    filtered_remote_branches = await repo.get_filtered_remote_branches()
    assert sorted(filtered_remote_branches.keys()) == ["branch01", "branch02", "main"]


async def test_get_filtered_remote_branches__some_branches_exists(
    git_repo_01: InfrahubRepository, mock_create_branch_git_repo_03: None, import_sync_branch_names: None
) -> None:
    repo = git_repo_01
    filtered_remote_branches = await repo.get_filtered_remote_branches()
    assert sorted(filtered_remote_branches.keys()) == ["branch01", "branch02", "main"]


async def test_get_filtered_remote_branches__no_import_sync_branch_names(git_repo_01: InfrahubRepository) -> None:
    repo = git_repo_01
    filtered_remote_branches = await repo.get_filtered_remote_branches()
    assert sorted(filtered_remote_branches.keys()) == ["branch01", "branch02", "clean-branch", "main"]


async def test_repo_merge_use_explicit_merge_commit(
    git_repo_01: InfrahubRepository,
    branch02: BranchData,
    git_user_config: None,
    git_use_explicit_merge_commit_config: None,
) -> None:
    repo = git_repo_01
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)
    response = await repo.merge(source_branch=branch02.name, dest_branch="main")
    commit = repo.get_git_repo_main().commit(response)
    assert commit.message.strip() == "Merged by Infrahub"


async def test_init_reinitialized_after_missing_directory(
    git_repo_02: InfrahubRepository, git_upstream_repo_02: dict[str, str | Path]
) -> None:
    """Verify that when the local clone directory is missing, re-clones from the upstream and sets the reinitialized flag."""
    original_commit = git_repo_02.get_commit_value(branch_name="main", remote=False)
    repo_id = git_repo_02.id

    assert not git_repo_02.reinitialized

    shutil.rmtree(git_repo_02.directory_root)
    assert not git_repo_02.directory_root.exists()

    recovered = await open_repository(
        id=repo_id,
        name=git_upstream_repo_02["name"],
        location=str(git_upstream_repo_02["path"]),
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    assert recovered.reinitialized
    assert recovered.directory_root.is_dir()
    assert recovered.directory_branches.is_dir()
    assert recovered.directory_commits.is_dir()
    assert recovered.has_origin

    assert recovered.get_commit_value(branch_name="main", remote=False) == original_commit

    new_branches, updated_branches = await recovered.compare_local_remote()
    assert not new_branches
    assert not updated_branches
