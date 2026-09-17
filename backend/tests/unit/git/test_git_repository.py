import logging
import re
from collections.abc import Iterator
from contextlib import nullcontext as does_not_raise
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from git import Repo
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.branch import BranchData
from infrahub_sdk.uuidt import UUIDT
from pydantic import Field

from infrahub import config
from infrahub.core.constants import RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
)
from infrahub.git import InfrahubRepository
from infrahub.git.repository import FailedImport, ImportStep, PendingObjectImport
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


async def test_pull_infrahub_default_branch_pulls_repository_default_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pulling the Infrahub default branch must pull the repository's own default branch.

    When the two differ, the remote has no branch named after the Infrahub default branch,
    so pulling the unmapped name fails and flips the repository into an error state.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    source = Repo.init(source_dir, initial_branch="production")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_dir / "data.txt").write_text("v1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 1")

    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="production-default-repo",
        location=str(source_dir),
        default_branch_name="production",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    (source_dir / "data.txt").write_text("v2\n", encoding="utf-8")
    source.index.add(["data.txt"])
    new_commit = source.index.commit("commit 2").hexsha

    commit_after = await repository.pull(branch_name="main", update_commit_value=False)
    assert commit_after == new_commit


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


class _RaisingOrigin:
    """Stand-in for GitPython's `origin` remote whose push always raises a transport-level error."""

    def __init__(self, error: GitCommandError) -> None:
        self._error = error

    def push(self, *args: Any, **kwargs: Any) -> None:
        raise self._error


class _RaisingWorktree:
    def __init__(self, error: GitCommandError) -> None:
        self.remotes = type("_Remotes", (), {"origin": _RaisingOrigin(error)})()


class _FailingPushRepository(InfrahubRepository):
    """An InfrahubRepository whose worktree's origin push always fails with a preset transport error.

    Records every operational status write so the test can assert a transient push failure leaves the
    recorded status untouched. The double keeps it in memory; it does not persist.
    """

    push_error: GitCommandError
    recorded_statuses: list[RepositoryOperationalStatus] = Field(default_factory=list)

    def get_git_repo_worktree(self, identifier: str) -> Any:
        return _RaisingWorktree(self.push_error)

    async def _update_operational_status(self, status: RepositoryOperationalStatus) -> None:
        self.recorded_statuses.append(status)


@dataclass
class PushErrorCase:
    name: str
    stderr: str
    expected: type[RepositoryError]


@pytest.mark.parametrize(
    "case",
    [
        PushErrorCase(
            name="credentials",
            stderr="fatal: Authentication failed for 'https://gitlab.example.com/net/repo.git/'",
            expected=RepositoryCredentialsError,
        ),
        PushErrorCase(
            name="connection",
            stderr="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': "
            "Could not resolve host: gitlab.example.com",
            expected=RepositoryConnectionError,
        ),
    ],
    ids=lambda c: c.name,
)
async def test_push_classifies_transport_error(case: PushErrorCase) -> None:
    """A transport-level push GitCommandError is classified into a typed RepositoryError without writing status."""
    repository = _FailingPushRepository(
        id=UUIDT.new(),
        name="push-repo",
        default_branch_name="main",
        location="https://gitlab.example.com/net/repo.git",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status="active",
        reinitialized=False,
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        push_error=GitCommandError(command=["git", "push"], status=128, stderr=case.stderr),
    )

    with pytest.raises(case.expected):
        await repository.push("main")

    assert repository.recorded_statuses == []


class _BranchSyncRepository(InfrahubRepository):
    """Drives collect_pending_imports over two new branches, one of whose git push fails.

    Every collaborator the collection loop calls is stubbed to an in-memory result so the test
    isolates a single behavior: a per-branch push failure records that branch as failed without
    aborting collection of the others. ``git_pushed_branches`` records the branches whose push
    succeeded so the test can assert the survivor was still processed.
    """

    connection_error_branch: str
    git_pushed_branches: list[str] = Field(default_factory=list)

    async def fetch(self) -> bool:
        return True

    async def compare_local_remote(self) -> tuple[list[str], list[str]]:
        return (["branch01", "branch02"], [])

    async def _exclude_read_only_branches(
        self, new_branches: list[str], updated_branches: list[str]
    ) -> tuple[list[str], list[str]]:
        return (new_branches, updated_branches)

    def validate_remote_branch(self, branch_name: str) -> bool:
        return True

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        return branch_name

    async def create_branch_in_graph(self, branch_name: str) -> BranchData:
        return BranchData(
            id=str(UUIDT.new()),
            name=branch_name,
            description=None,
            sync_with_git=True,
            is_default=False,
            has_schema_changes=False,
            graph_version=1,
            status="OPEN",
            origin_branch="main",
            branched_from="2024-01-01",
        )

    async def create_branch_in_git(
        self, branch_name: str, branch_id: str | None = None, push_origin: bool = True
    ) -> bool:
        if branch_name == self.connection_error_branch:
            raise RepositoryConnectionError(identifier=self.name)
        self.git_pushed_branches.append(branch_name)
        return True

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        return f"commit-{branch_name}"

    def create_commit_worktree(self, commit: str) -> bool:
        return True

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        return True

    async def _collect_staging_imports(
        self, staging_branch: str | None, updated_branches: list[str]
    ) -> list[PendingObjectImport]:
        return []


async def test_collect_pending_imports_isolates_per_branch_push_failure() -> None:
    """A connection failure while pushing one new branch is recorded, not raised over the others."""
    repository = _BranchSyncRepository(
        id=UUIDT.new(),
        name="sync-repo",
        default_branch_name="main",
        location="https://gitlab.example.com/net/repo.git",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status="active",
        reinitialized=False,
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        connection_error_branch="branch01",
    )

    collected = await repository.collect_pending_imports()

    assert collected.imports == [PendingObjectImport(infrahub_branch_name="branch02", commit="commit-branch02")]
    assert collected.failed_imports == [
        FailedImport(
            branch_name="branch01",
            step=ImportStep.COLLECTION,
            reason=str(RepositoryConnectionError(identifier="sync-repo")),
        )
    ]
    assert repository.git_pushed_branches == ["branch02"]


@pytest.fixture
def stub_repo() -> InfrahubRepository:
    # Spell out all fields that carry positional defaults in Field() so mypy sees them.
    return InfrahubRepository(
        id=UUIDT.new(),
        name="test-repo",
        default_branch_name=None,
        location=None,
        has_origin=False,
        cache_repo=None,
        is_read_only=False,
        internal_status="active",
        reinitialized=False,
        infrahub_branch_name=None,
    )


@dataclass
class RaiseBranchesCase:
    name: str
    failed_imports: list[FailedImport]
    expectation: Any


@pytest.mark.parametrize(
    "case",
    [
        RaiseBranchesCase(
            name="empty_list_does_not_raise",
            failed_imports=[],
            expectation=does_not_raise(),
        ),
        RaiseBranchesCase(
            name="single_failure",
            failed_imports=[
                FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="schema validation failed"),
            ],
            expectation=pytest.raises(
                RepositoryError,
                match=rf"^{
                    re.escape(
                        'Unable to synchronize the following branches of repository test-repo:'
                        ' branch01 (step=collection): schema validation failed'
                    )
                }$",
            ),
        ),
        RaiseBranchesCase(
            name="multiple_failures",
            failed_imports=[
                FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="error 1"),
                FailedImport(branch_name="branch02", step=ImportStep.IMPORT, reason="error 2"),
            ],
            expectation=pytest.raises(
                RepositoryError,
                match=rf"^{
                    re.escape(
                        'Unable to synchronize the following branches of repository test-repo:'
                        ' branch01 (step=collection): error 1; branch02 (step=import): error 2'
                    )
                }$",
            ),
        ),
    ],
    ids=lambda c: c.name,
)
def test_raise_if_branches_failed(stub_repo: InfrahubRepository, case: RaiseBranchesCase) -> None:
    with case.expectation:
        stub_repo.raise_if_branches_failed(case.failed_imports)


def test_raise_if_branches_failed_logs_structured_fields(
    stub_repo: InfrahubRepository, caplog: pytest.LogCaptureFixture
) -> None:
    failed = FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="schema validation failed")
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"), pytest.raises(RepositoryError):
        stub_repo.raise_if_branches_failed([failed])
    assert len(caplog.records) == 1
    attrs = vars(caplog.records[0])
    assert attrs["branch"] == "branch01"
    assert attrs["step"] == "collection"
    assert attrs["reason"] == "schema validation failed"
    assert attrs["repository"] == "test-repo"
