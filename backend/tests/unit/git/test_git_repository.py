import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT
from pytest_httpx import HTTPXMock

from infrahub import config
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.test_client import dummy_async_request

PREFECT_LOGGER_NAME = "infrahub.git.base"


@pytest.fixture
def patch_prefect_logger() -> Iterator[None]:
    """Replace Prefect's `get_run_logger` with a stdlib logger so calls outside a flow context succeed."""
    with patch(
        "infrahub.git.base.get_run_logger",
        return_value=logging.getLogger(PREFECT_LOGGER_NAME),
    ):
        yield


def _build_source_with_conflicting_branches(source_dir: Path) -> None:
    """Initialize a git source repo with `main` and `change1` whose tips edit the same lines."""
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    target = source_dir / "data.txt"
    target.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    base_commit = source.index.commit("base")

    source.git.checkout("-b", "change1")
    target.write_text("change1 version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on change1")

    source.git.checkout("main")
    source.git.reset("--hard", base_commit.hexsha)
    target.write_text("main version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on main")


async def _build_repository_with_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, name: str = "conflicting-repo"
) -> InfrahubRepository:
    """Build an `InfrahubRepository` whose remote has `main` and a divergent `change1`.

    Raises:
        RuntimeError: When the constructed source repo no longer produces a conflict between `main` and `change1`.

    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    _build_source_with_conflicting_branches(source_dir)

    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=name,
        location=str(source_dir),
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    if not repository.has_conflicting_changes(target_branch="main", source_branch="change1"):
        raise RuntimeError(
            "test helper drift: main and change1 must conflict for the conflict-import tests to be meaningful"
        )
    return repository


async def test_create_branch_in_git_with_conflicting_remote_lands_at_remote_tip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remote branch that conflicts with the default branch must still be imported locally.

    The local branch should land at the remote tip so that downstream merge attempts can
    surface the conflict at merge time, rather than aborting the entire import.
    """
    repository = await _build_repository_with_conflict(tmp_path, monkeypatch)

    remote_branches = repository.get_branches_from_remote()
    expected_commit = remote_branches["change1"].commit

    await repository.create_branch_in_git(branch_name="change1", branch_id=str(UUIDT.new()))

    local_branches = repository.get_branches_from_local(include_worktree=False)
    assert "change1" in local_branches
    assert local_branches["change1"].commit == expected_commit


async def test_validate_remote_branch_allows_conflicting_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_prefect_logger: None,
) -> None:
    """validate_remote_branch must accept a branch that conflicts with the default branch.

    Skipping the branch would prevent it from being imported. The conflict is surfaced at
    merge time instead.
    """
    repository = await _build_repository_with_conflict(tmp_path, monkeypatch)
    assert repository.validate_remote_branch(branch_name="change1") is True


async def test_has_conflicting_changes_no_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """has_conflicting_changes() must not flag a diff that only adds lines containing '======='."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    sources_dir = tmp_path / "source"
    sources_dir.mkdir()

    test_repo = MultipleStagesFileRepo(name="false-positive-conflicts", sources_directory=sources_dir)
    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Confirm the diff between the branches actually contains ======= to validate the test premise
    diff = test_repo.repo.git.diff("main", "change1")
    assert "=======" in diff

    # The branch adds a file containing ======= but has no actual conflicts with main
    assert not repository.has_conflicting_changes(target_branch="main", source_branch="change1")


async def test_init_repoints_origin_after_location_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reinitializing a repository after its location changed must re-point the cached clone's origin.

    When the location is updated to a remote that has advanced, opening the existing clone and fetching
    must surface the new remote's commit, not the commit baked in at the original clone location.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    # Remote A: the original location, main at commit 1.
    source_a = tmp_path / "source-a"
    source_a.mkdir()
    repo_a = Repo.init(source_a, initial_branch="main")
    with repo_a.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_a / "data.txt").write_text("v1\n", encoding="utf-8")
    repo_a.index.add(["data.txt"])
    commit_a = repo_a.index.commit("commit 1").hexsha

    repo_id = str(UUIDT.new())
    client = InfrahubClient(config=Config(requester=dummy_async_request))
    repository = await InfrahubRepository.new(
        id=repo_id,
        name="relocating-repo",
        location=str(source_a),
        default_branch_name="main",
        client=client,
    )
    assert repository.get_branches_from_remote()["main"].commit == commit_a

    # Remote B: the new location, a clone of A that has advanced with commit 2.
    source_b = tmp_path / "source-b"
    repo_b = repo_a.clone(str(source_b))
    with repo_b.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_b / "data.txt").write_text("v2\n", encoding="utf-8")
    repo_b.index.add(["data.txt"])
    commit_b = repo_b.index.commit("commit 2").hexsha

    # Re-open the existing clone with the new location, as the periodic sync does after a location change.
    # init must re-point origin and fetch on its own -- no explicit fetch here.
    relocated = await InfrahubRepository.init(
        id=repo_id,
        name="relocating-repo",
        location=str(source_b),
        default_branch_name="main",
        client=client,
    )

    assert relocated.get_git_repo_main().remotes.origin.url == str(source_b)
    assert relocated.get_branches_from_remote()["main"].commit == commit_b


def _build_source_with_working_branch(source_dir: Path) -> None:
    """Initialize a git source repo with `main` and a `branch01` that adds a commit on top of it."""
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")

    target = source_dir / "data.txt"
    target.write_text("line 1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("initial commit on main")

    source.git.checkout("-b", "branch01")
    target.write_text("line 1\nline 2\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit on branch01")

    source.git.checkout("main")


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_collect_pending_imports_skips_merged_read_only_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
) -> None:
    """A remote git branch mapping to an already-merged (read-only) Infrahub branch must be skipped.

    A git branch present on the remote but absent from the worker's local clone is classified as a
    new branch. When the matching Infrahub branch already exists and has been merged, it is
    read-only, so recording a commit against it is rejected server-side with a GraphQLError. That
    rejection must not abort the collection: the merged branch should be skipped -- neither queued
    for import nor recorded as a permanent per-cycle failure -- so the remaining branches and
    repositories keep syncing.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    _build_source_with_working_branch(source_dir)

    client = InfrahubClient(config=Config(address="http://mock", insert_tracker=True))
    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="merged-read-only-repo",
        location=str(source_dir),
        default_branch_name="main",
        client=client,
        update_commit_value=False,
    )

    # Precondition: branch01 lives on the remote but not in the local clone, so it is collected as a
    # "new" branch -- the exact path that breaks when the Infrahub branch is already merged.
    new_branches, updated_branches = await repository.compare_local_remote()
    assert new_branches == ["branch01"]
    assert updated_branches == []

    # fetch() reports the repository as online at the start of collection.
    httpx_mock.add_response(
        method="POST",
        json={"data": {"CoreGenericRepositoryUpdate": {"ok": True}}},
        match_headers={"X-Infrahub-Tracker": "mutation-repository-update-operational-status"},
    )

    # create_branch_in_graph: the Infrahub branch already exists, so BranchCreate is rejected with an
    # "already exist" error, sending collection down the branch.get() lookup path.
    httpx_mock.add_response(
        method="POST",
        json={"errors": [{"message": "An error occurred while creating the branch 'branch01', already exist"}]},
        match_headers={"X-Infrahub-Tracker": "mutation-branch-create"},
    )

    # branch.get: the existing Infrahub branch has been merged and is therefore read-only.
    httpx_mock.add_response(
        method="POST",
        json={
            "data": {
                "Branch": [
                    {
                        "id": "8927425e-fd89-482a-bcec-aad267eb2c66",
                        "name": "branch01",
                        "description": "",
                        "origin_branch": "main",
                        "branched_from": "2023-02-17T09:30:17.811719Z",
                        "is_default": False,
                        "sync_with_git": True,
                        "has_schema_changes": False,
                        "graph_version": 1,
                        "status": "MERGED",
                    }
                ]
            }
        },
        match_headers={"X-Infrahub-Tracker": "query-branch"},
    )

    # update_commit_value: recording a commit on the read-only branch is rejected by the server. A
    # correct implementation skips the branch before reaching this call, so this response may be
    # left unused (assert_all_responses_were_requested=False above).
    httpx_mock.add_response(
        method="POST",
        json={
            "errors": [{"message": "Branch 'branch01' has been merged and is read-only. No modifications are allowed."}]
        },
        match_headers={"X-Infrahub-Tracker": "mutation-repository-update-commit"},
    )

    result = await repository.collect_pending_imports()

    # The merged/read-only branch is skipped: it is neither queued for import nor recorded as a
    # permanent per-cycle failure (which would tag the repository with a sync error every minute).
    assert [pending.infrahub_branch_name for pending in result.imports] == []
    assert result.failed_imports == []


def test_check_connectivity_ignores_cwd_git_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git operations must not be affected by a broken .git worktree pointer in the process current working directory."""
    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    Repo.init(source_dir, initial_branch="main")

    # Simulate a worktree environment: current working directory has a .git file pointing to a path that doesn't exist
    cwd = tmp_path / "broken-worktree"
    cwd.mkdir()
    (cwd / ".git").write_text("gitdir: /nonexistent/.git/worktrees/fake\n")
    monkeypatch.chdir(cwd)

    InfrahubRepository.check_connectivity(name="test", url=f"file://{source_dir}")
