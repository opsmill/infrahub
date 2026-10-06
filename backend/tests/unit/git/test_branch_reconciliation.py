"""How a synchronisation brings each branch onto its remote head and classifies it against the graph."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.git.divergence.models import ReconciledBranch, RefClassification, RefDivergence
from infrahub.git.repository import FailedImport, ImportStep, PendingObjectImport
from tests.helpers.git import LocalRemote, clone_repository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from infrahub.git.repository import InfrahubRepository

SYNC_LOGGER = "infrahub.tasks"
TRACKED = "feature"
OTHER = "other"
STAGING = "staging-x"
UNKNOWN_COMMIT = "0" * 40
"""A commit no clone holds, as when the graph recorded a history this worker never fetched."""


@pytest.fixture(autouse=True)
def capture_sync_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=SYNC_LOGGER)


def branch_payload(name: str, status: str = "OPEN") -> dict[str, Any]:
    return {
        "id": f"{name}-id",
        "name": name,
        "description": None,
        "sync_with_git": True,
        "is_default": name == "main",
        "has_schema_changes": False,
        "graph_version": None,
        "status": status,
        "origin_branch": "main",
        "branched_from": "2024-01-01T00:00:00Z",
    }


class GraphRecordingClient(InfrahubClient):
    """An SDK client whose graph holds the given Infrahub branches and keeps every commit recorded on them.

    ``branch_statuses`` sets the status the listing reports for a branch, OPEN otherwise, and
    ``rejecting_branches`` refuse a commit write the way the API refuses one on a branch that needs a rebase.
    """

    def __init__(self, branch_names: tuple[str, ...]) -> None:
        super().__init__(config=Config(requester=dummy_async_request))
        self.branch_names = branch_names
        self.branch_statuses: dict[str, str] = {}
        self.rejecting_branches: frozenset[str] = frozenset()
        self.recorded_commits: list[tuple[str, str]] = []

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        tracker = kwargs.get("tracker")
        variables = kwargs.get("variables") or {}
        if tracker == "query-branch-all":
            return {
                "Branch": [
                    branch_payload(name=name, status=self.branch_statuses.get(name, "OPEN"))
                    for name in self.branch_names
                ]
            }
        if tracker == "mutation-branch-create":
            raise GraphQLError(errors=[{"message": "The branch already exists"}])
        if tracker == "query-branch":
            return {"Branch": [branch_payload(name=variables["branch_name"])]}
        if tracker == "mutation-repository-update-commit":
            if kwargs["branch_name"] in self.rejecting_branches:
                raise GraphQLError(errors=[{"message": rejected_commit_message(kwargs["branch_name"])}])
            self.recorded_commits.append((kwargs["branch_name"], variables["commit"]))
        return {}


def rejected_commit_message(branch_name: str) -> str:
    return f"Branch {branch_name} must be rebased before any updates can be made"


@dataclass(frozen=True)
class TrackedRepository:
    remote: LocalRemote
    repository: InfrahubRepository
    client: GraphRecordingClient
    trunk_commit: str
    imported_commits: dict[str, str]
    """The head each tracked branch had when this clone took it, which the graph also records."""

    def graph_commits(self, **overrides: str) -> dict[str, str | None]:
        return {"main": self.trunk_commit, **self.imported_commits, **overrides}

    def worktree_head(self, branch_name: str) -> str:
        return str(self.repository.get_git_repo_worktree(identifier=branch_name).head.commit)


async def clone_with_tracked_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    branches: tuple[str, ...] = (TRACKED,),
    local_branches: tuple[str, ...] | None = None,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
) -> TrackedRepository:
    """Clone a remote whose branches each carry one commit of their own, holding ``local_branches`` locally."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))
    monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])

    remote = LocalRemote.create(directory=tmp_path / "remote", trunk="main", branches=[])
    imported_commits = {
        branch_name: remote.commit(branch_name=branch_name, files={"data.txt": f"{branch_name} v1\n"})
        for branch_name in branches
    }
    client = GraphRecordingClient(branch_names=("main", STAGING, *branches))
    repository = await clone_repository(
        id=UUIDT.new(),
        name="tracked-repo",
        location=str(remote.directory),
        client=client,
        internal_status=internal_status,
        update_commit_value=False,
    )
    for branch_name in branches if local_branches is None else local_branches:
        await repository.create_branch_in_git(branch_name=branch_name, branch_id=f"{branch_name}-id", push_origin=False)

    return TrackedRepository(
        remote=remote,
        repository=repository,
        client=client,
        trunk_commit=str(remote.repo.commit("main")),
        imported_commits=imported_commits,
    )


def lose_an_object_store(tracked: TrackedRepository, tmp_path: Path) -> Path:
    """Point the clone at a borrowed object store that is gone, which git skips without failing."""
    missing_store = (tmp_path / "missing-store").resolve()
    git_dir = Path(tracked.repository.get_git_repo_main().git_dir)
    (git_dir / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (git_dir / "objects" / "info" / "alternates").write_text(f"{missing_store}\n", encoding="utf-8")
    return missing_store


def divergence(
    imported_commit: str | None, remote_head: str, classification: RefClassification, branch_name: str = TRACKED
) -> RefDivergence:
    return RefDivergence(
        branch_name=branch_name,
        infrahub_branch_name=branch_name,
        imported_commit=imported_commit,
        remote_head=remote_head,
        classification=classification,
    )


def queued(
    commit: str,
    divergence: RefDivergence | None,
    branch_name: str = TRACKED,
    import_branch: str | None = None,
    git_branch_name: str | None = None,
) -> PendingObjectImport:
    return PendingObjectImport(
        infrahub_branch_name=import_branch or branch_name,
        commit=commit,
        git_branch_name=git_branch_name,
        on_default_branch=branch_name == "main",
        reconciled=ReconciledBranch(
            infrahub_branch_name=branch_name,
            infrahub_branch_id=f"{branch_name}-id",
            commit=commit,
            divergence=divergence,
        ),
    )


def reconciliation_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == SYNC_LOGGER and record.getMessage().startswith("Reconciled branch")
    ]


def reconciliation_message(discarded_commit: str, commit: str) -> str:
    return (
        f"Reconciled branch {TRACKED} of repository tracked-repo with the remote history: "
        f"{discarded_commit} was discarded and replaced by {commit}"
    )


async def test_a_rewritten_branch_is_reset_onto_the_remote_head_and_imported_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.failed_imports == []
    rewrite = divergence(imported, rewritten, RefClassification.REWRITE)
    assert collected.imports == [queued(commit=rewritten, divergence=rewrite)]
    assert collected.reconciled == [
        ReconciledBranch(
            infrahub_branch_name=TRACKED, infrahub_branch_id=f"{TRACKED}-id", commit=rewritten, divergence=rewrite
        )
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == rewritten
    assert tracked.client.recorded_commits == [(TRACKED, rewritten)]
    assert reconciliation_messages(caplog) == [reconciliation_message(discarded_commit=imported, commit=rewritten)]


async def test_a_fast_forwarded_branch_is_moved_onto_the_remote_head_and_reports_no_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    advanced = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature v2\n"})

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.imports == [
        queued(commit=advanced, divergence=divergence(imported, advanced, RefClassification.FAST_FORWARD))
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == advanced
    assert reconciliation_messages(caplog) == []


async def test_a_branch_the_remote_rewound_is_reset_back_onto_the_remote_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A remote head behind the imported commit means the remote discarded it, exactly as a rewrite does."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    tracked.remote.move_branch(branch_name=TRACKED, commit=tracked.trunk_commit)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.imports == [
        queued(
            commit=tracked.trunk_commit,
            divergence=divergence(imported, tracked.trunk_commit, RefClassification.REWRITE),
        )
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == tracked.trunk_commit
    assert reconciliation_messages(caplog) == [
        reconciliation_message(discarded_commit=imported, commit=tracked.trunk_commit)
    ]


async def test_a_stale_worktree_resets_even_when_the_graph_already_records_the_remote_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Another worker reconciled the branch, so only this clone still holds the discarded history.

    The classification is unchanged, which is what keeps the rewrite from being reported a second time.
    """
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: rewritten})
    )

    assert collected.imports == [
        queued(commit=rewritten, divergence=divergence(rewritten, rewritten, RefClassification.UNCHANGED))
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == rewritten
    assert reconciliation_messages(caplog) == [reconciliation_message(discarded_commit=imported, commit=rewritten)]


async def test_a_worktree_on_the_remote_head_records_the_commit_the_graph_lacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Nothing moves in git, so only the graph comparison selects the branch, and no pull would record it."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    assert await tracked.repository.compare_local_remote() == ([], [])

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: tracked.trunk_commit})
    )

    assert collected.imports == [
        queued(commit=imported, divergence=divergence(tracked.trunk_commit, imported, RefClassification.FAST_FORWARD))
    ]
    assert tracked.client.recorded_commits == [(TRACKED, imported)]
    assert tracked.worktree_head(branch_name=TRACKED) == imported
    assert reconciliation_messages(caplog) == []


async def test_a_worktree_on_the_remote_head_reports_the_commit_the_graph_held_and_the_remote_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: UNKNOWN_COMMIT})
    )

    assert collected.imports == [
        queued(commit=imported, divergence=divergence(UNKNOWN_COMMIT, imported, RefClassification.REWRITE))
    ]
    assert tracked.client.recorded_commits == [(TRACKED, imported)]
    assert reconciliation_messages(caplog) == [reconciliation_message(discarded_commit=UNKNOWN_COMMIT, commit=imported)]


async def test_an_empty_graph_commit_is_one_the_graph_never_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits(**{TRACKED: ""}))

    assert collected.failed_imports == []
    assert collected.imports == [
        queued(commit=imported, divergence=divergence(None, imported, RefClassification.FAST_FORWARD))
    ]
    assert tracked.client.recorded_commits == [(TRACKED, imported)]


async def test_a_branch_on_the_remote_head_in_both_git_and_the_graph_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.imports == []
    assert collected.failed_imports == []
    assert tracked.client.recorded_commits == []


async def test_a_malformed_graph_commit_counts_as_none_and_the_branch_is_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Git cannot classify a commit id the graph mangled, which would otherwise fail the branch on every cycle."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: "not-a-commit"})
    )

    assert collected.failed_imports == []
    assert collected.imports == [
        queued(commit=rewritten, divergence=divergence(None, rewritten, RefClassification.FAST_FORWARD))
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == rewritten
    assert reconciliation_messages(caplog) == [reconciliation_message(discarded_commit=imported, commit=rewritten)]


async def test_a_branch_whose_object_store_cannot_be_read_fails_alone_and_keeps_its_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absence git reports from a store it cannot read is not a rewrite, so the branch must not move."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    imported = tracked.imported_commits[TRACKED]
    tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)
    advanced = tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})
    missing_store = lose_an_object_store(tracked=tracked, tmp_path=tmp_path)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: UNKNOWN_COMMIT})
    )

    assert collected.failed_imports == [
        FailedImport(
            branch_name=TRACKED,
            step=ImportStep.COLLECTION,
            reason=f"Unable to read {UNKNOWN_COMMIT} from the object database: {missing_store} is unreadable",
        )
    ]
    assert collected.imports == [
        queued(
            commit=advanced,
            divergence=divergence(
                tracked.imported_commits[OTHER], advanced, RefClassification.FAST_FORWARD, branch_name=OTHER
            ),
            branch_name=OTHER,
        )
    ]
    assert tracked.worktree_head(branch_name=TRACKED) == imported


async def test_a_branch_whose_infrahub_branch_is_gone_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The graph has nowhere to record its commit, so trying would only fail again on every cycle."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    imported = tracked.imported_commits[TRACKED]
    tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature v2\n"})
    advanced = tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})
    tracked.client.branch_names = ("main", OTHER)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.failed_imports == []
    assert collected.imports == [
        queued(
            commit=advanced,
            divergence=divergence(
                tracked.imported_commits[OTHER], advanced, RefClassification.FAST_FORWARD, branch_name=OTHER
            ),
            branch_name=OTHER,
        )
    ]
    assert tracked.client.recorded_commits == [(OTHER, advanced)]
    assert tracked.worktree_head(branch_name=TRACKED) == imported


async def test_a_branch_that_needs_a_rebase_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The graph refuses a commit on a branch that needs a rebase, so trying would only fail again on every cycle."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    imported = tracked.imported_commits[TRACKED]
    tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature v2\n"})
    advanced = tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})
    tracked.client.branch_statuses = {TRACKED: "NEED_REBASE"}

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.failed_imports == []
    assert collected.imports == [
        queued(
            commit=advanced,
            divergence=divergence(
                tracked.imported_commits[OTHER], advanced, RefClassification.FAST_FORWARD, branch_name=OTHER
            ),
            branch_name=OTHER,
        )
    ]
    assert tracked.client.recorded_commits == [(OTHER, advanced)]
    assert tracked.worktree_head(branch_name=TRACKED) == imported


async def test_a_branch_whose_commit_the_graph_refuses_fails_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The listing can predate the status that makes the graph refuse the commit, as when a merge starts."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature v2\n"})
    advanced = tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})
    tracked.client.rejecting_branches = frozenset({TRACKED})

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.failed_imports == [
        FailedImport(
            branch_name=TRACKED,
            step=ImportStep.COLLECTION,
            reason=(
                "An error occurred while executing the GraphQL Query None, "
                "[{'message': 'Branch feature must be rebased before any updates can be made'}]"
            ),
        )
    ]
    assert collected.imports == [
        queued(
            commit=advanced,
            divergence=divergence(
                tracked.imported_commits[OTHER], advanced, RefClassification.FAST_FORWARD, branch_name=OTHER
            ),
            branch_name=OTHER,
        )
    ]
    assert tracked.client.recorded_commits == [(OTHER, advanced)]


async def test_a_branch_new_to_this_worker_is_classified_against_the_commit_another_worker_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The graph records what another worker imported, so a rewrite shows even on a worker without the branch."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, local_branches=())
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.imports == [
        queued(commit=rewritten, divergence=divergence(imported, rewritten, RefClassification.REWRITE))
    ]
    assert tracked.client.recorded_commits == [(TRACKED, rewritten)]
    assert reconciliation_messages(caplog) == [reconciliation_message(discarded_commit=imported, commit=rewritten)]


async def test_a_branch_new_to_this_worker_is_created_even_when_it_cannot_be_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The classification only names a discarded history, so it must not keep the branch from being imported."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, local_branches=())
    imported = tracked.imported_commits[TRACKED]
    missing_store = lose_an_object_store(tracked=tracked, tmp_path=tmp_path)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: UNKNOWN_COMMIT})
    )

    assert collected.failed_imports == []
    assert collected.imports == [queued(commit=imported, divergence=None)]
    assert tracked.client.recorded_commits == [(TRACKED, imported)]
    assert [
        record.getMessage() for record in caplog.records if record.getMessage().startswith("Unable to classify")
    ] == [
        f"Unable to classify the new branch {TRACKED} of repository tracked-repo against the graph: "
        f"Unable to read {UNKNOWN_COMMIT} from the object database: {missing_store} is unreadable"
    ]


async def test_a_rewritten_trunk_of_a_staging_repository_is_reset_and_imported_into_the_staging_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(
        tmp_path=tmp_path, monkeypatch=monkeypatch, internal_status=RepositoryInternalStatus.STAGING
    )
    imported = tracked.trunk_commit
    rewritten = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(
        staging_branch=STAGING, graph_commits=tracked.graph_commits()
    )

    assert collected.imports == [
        queued(
            commit=rewritten,
            divergence=divergence(imported, rewritten, RefClassification.REWRITE, branch_name="main"),
            branch_name="main",
            import_branch=STAGING,
            git_branch_name="main",
        )
    ]
    assert tracked.worktree_head(branch_name="main") == rewritten


async def test_a_staging_trunk_whose_commit_the_graph_refuses_fails_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raise from the trunk of one repository would stop the synchronization of every repository after it."""
    tracked = await clone_with_tracked_branches(
        tmp_path=tmp_path, monkeypatch=monkeypatch, internal_status=RepositoryInternalStatus.STAGING
    )
    tracked.remote.commit(branch_name="main", files={"data.txt": "main v2\n"})
    tracked.client.rejecting_branches = frozenset({"main"})

    collected = await tracked.repository.collect_pending_imports(
        staging_branch=STAGING, graph_commits=tracked.graph_commits()
    )

    assert collected.failed_imports == [
        FailedImport(
            branch_name="main",
            step=ImportStep.COLLECTION,
            reason=(
                "An error occurred while executing the GraphQL Query None, "
                "[{'message': 'Branch main must be rebased before any updates can be made'}]"
            ),
            on_default_branch=True,
        )
    ]
    assert collected.imports == []
