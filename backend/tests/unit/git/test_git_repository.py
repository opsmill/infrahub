import logging
import re
import shutil
from collections.abc import Iterator
from contextlib import nullcontext as does_not_raise
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pydantic
import pytest
from git import Repo
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus, RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository
from infrahub.git.models import GitRepositoryAdd, GitRepositoryMerge
from infrahub.git.repository import FailedImport, ImportStep, InfrahubReadOnlyRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.git import clone_repository, open_repository
from tests.helpers.test_client import dummy_async_request

PREFECT_LOGGER_NAME = "infrahub.git.repository"


@pytest.fixture
def patch_prefect_logger() -> Iterator[None]:
    """Replace Prefect's `get_run_logger` with a stdlib logger so calls outside a flow context succeed."""
    with patch(
        "infrahub.git.repository.get_run_logger",
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

    repository = await clone_repository(
        id=UUIDT.new(),
        name=name,
        location=str(source_dir),
        default_branch="main",
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
    repository = await clone_repository(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        default_branch="main",
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
    repository = await clone_repository(
        id=repo_id,
        name="relocating-repo",
        location=str(source_a),
        default_branch="main",
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

    # Re-open the existing clone with the new location, as the periodic sync does after a location
    # change. Opening it must re-point origin and fetch on its own -- no explicit fetch here.
    relocated = await open_repository(
        id=repo_id,
        name="relocating-repo",
        location=str(source_b),
        default_branch="main",
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

    repository = await clone_repository(
        id=UUIDT.new(),
        name="production-default-repo",
        location=str(source_dir),
        default_branch="production",
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


class RecordingGraphqlClient(InfrahubClient):
    """An SDK client that records the branch of every GraphQL call instead of sending it."""

    def __init__(self) -> None:
        super().__init__(config=Config(requester=dummy_async_request))
        self.recorded_branches: list[str | None] = []

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.recorded_branches.append(kwargs.get("branch_name"))
        return {}


def build_read_write(default_branch: str) -> InfrahubRepository:
    """A read-write repository object with no local clone, for the pure mapping assertions below."""
    return InfrahubRepository(
        id=UUID(str(UUIDT.new())),
        name="mapping-repo",
        location="git@github.com:mock/mapping-repo.git",
        default_branch=default_branch,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
    )


def build_read_only(ref: str) -> InfrahubReadOnlyRepository:
    return InfrahubReadOnlyRepository(
        id=UUID(str(UUIDT.new())),
        name="mapping-read-only-repo",
        location="git@github.com:mock/mapping-repo.git",
        ref=ref,
        infrahub_branch_name="main",
    )


@dataclass
class MappingCase:
    name: str
    branch_name: str
    expected_remote: str
    expected_target: str
    expected_worktree: str


MAPPING_CASES = [
    MappingCase(
        name="infrahub_default_maps_onto_the_trunk",
        branch_name="main",
        expected_remote="develop",
        expected_target="main",
        expected_worktree="main",
    ),
    MappingCase(
        name="trunk_maps_back_onto_the_infrahub_default",
        branch_name="develop",
        expected_remote="develop",
        expected_target="main",
        expected_worktree="main",
    ),
    MappingCase(
        name="any_other_branch_is_unchanged",
        branch_name="feature-1",
        expected_remote="feature-1",
        expected_target="feature-1",
        expected_worktree="feature-1",
    ),
]


@pytest.mark.parametrize("case", MAPPING_CASES, ids=[case.name for case in MAPPING_CASES])
def test_read_write_branch_mapping(case: MappingCase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_write(default_branch="develop")

    assert repository._get_mapped_remote_branch(branch_name=case.branch_name) == case.expected_remote
    assert repository._get_mapped_target_branch(branch_name=case.branch_name) == case.expected_target
    assert repository._resolve_worktree_identifier(branch_name=case.branch_name) == case.expected_worktree


@pytest.mark.parametrize("branch_name", ["main", "develop", "feature-1"])
def test_read_only_branch_mapping_is_identity(branch_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A read-only repository tracks one ref and maps no branch names."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_only(ref="develop")

    assert repository._get_mapped_remote_branch(branch_name=branch_name) == branch_name
    assert repository._get_mapped_target_branch(branch_name=branch_name) == branch_name
    assert repository._resolve_worktree_identifier(branch_name=branch_name) == branch_name


def test_worktree_identifier_when_remote_has_a_literal_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """The trunk's worktree is stored under `main`, which a remote branch literally named `main` shares.

    Documents the collision rather than fixing it: both resolve to the same on-disk identifier.
    """
    monkeypatch.setattr(registry, "_default_branch", "production")
    repository = build_read_write(default_branch="develop")

    assert repository._resolve_worktree_identifier(branch_name="develop") == "main"
    assert repository._resolve_worktree_identifier(branch_name="main") == "main"


@dataclass
class MissingFieldCase:
    name: str
    fields: dict[str, Any]
    missing: str


MISSING_FIELD_CASES = [
    MissingFieldCase(
        name="without_default_branch",
        fields={"name": "no-trunk-repo", "internal_status": RepositoryInternalStatus.ACTIVE},
        missing="default_branch",
    ),
    MissingFieldCase(
        name="without_internal_status",
        fields={"name": "no-status-repo", "default_branch": "develop"},
        missing="internal_status",
    ),
]


@pytest.mark.parametrize("case", MISSING_FIELD_CASES, ids=[case.name for case in MISSING_FIELD_CASES])
def test_read_write_construction_rejects_a_missing_field(case: MissingFieldCase) -> None:
    """Both values are required at construction, which is what makes the broken state unreachable.

    The fields are passed as a mapping so the omission is a runtime one, which is what is under test.
    """
    with pytest.raises(pydantic.ValidationError, match=case.missing):
        InfrahubRepository(id=UUID(str(UUIDT.new())), **case.fields)


def test_read_only_repository_has_no_trunk() -> None:
    """The base model drops an unknown keyword rather than rejecting it, so assert on the instance."""
    fields: dict[str, Any] = {"name": "read-only-repo", "ref": "develop", "default_branch": "develop"}
    repository = InfrahubReadOnlyRepository(id=UUID(str(UUIDT.new())), **fields)

    assert not hasattr(repository, "default_branch")


def test_message_models_no_longer_carry_a_trunk() -> None:
    assert "default_branch_name" not in GitRepositoryAdd.model_fields
    assert "default_branch" not in GitRepositoryMerge.model_fields


async def test_read_only_fetch_failure_keeps_its_classified_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only repository whose remote disappears still raises a classified error.

    The failure path asks for no branch name, which the read-only kind cannot supply.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_dir / "data.txt").write_text("v1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 1")

    repository = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name="vanishing-read-only-repo",
        location=str(source_dir),
        ref="main",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    shutil.rmtree(source_dir)

    with pytest.raises(RepositoryError) as raised:
        await repository.fetch()

    assert isinstance(raised.value.__cause__, GitCommandError)


async def test_update_operational_status_writes_on_the_branch_the_object_was_resolved_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The status mutation names the branch the repository object carries, not the platform default."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_write(default_branch="develop")
    repository.infrahub_branch_name = "feature-branch"
    recorder = RecordingGraphqlClient()
    repository.client = recorder

    await repository._update_operational_status(status=RepositoryOperationalStatus.ONLINE)

    assert recorder.recorded_branches == ["feature-branch"]


@pytest.fixture
def stub_repo() -> InfrahubRepository:
    return InfrahubRepository(
        id=UUID(str(UUIDT.new())),
        name="test-repo",
        default_branch="main",
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
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
