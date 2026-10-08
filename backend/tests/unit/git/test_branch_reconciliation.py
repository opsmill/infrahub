"""How a synchronisation brings each branch onto its remote head and classifies it against the graph."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError, ServerNotReachableError
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.models import ReconciledBranch, RefClassification, RefDivergence, RewriteRecord
from infrahub.git.divergence.recorder import HistoryRewriteRecorder
from infrahub.git.divergence.suppression import RetargetMarkers
from infrahub.git.repository import FailedImport, ImportStep, PendingObjectImport
from tests.adapters.cache import MemoryCache
from tests.adapters.repository_record_store import (
    FailingRepositoryRecordStore,
    InMemoryRepositoryRecordStore,
    WrittenRecord,
)
from tests.helpers.git import GraphRecordingClient, LocalRemote, clone_repository
from tests.unit.git.writeback.fakes import FixedClock, InMemoryDeliveryState

if TYPE_CHECKING:
    from infrahub.git.repository import InfrahubRepository

SYNC_LOGGER = "infrahub.tasks"
TRACKED = "feature"
OTHER = "other"
STAGING = "staging-x"
UNKNOWN_COMMIT = "0" * 40
"""A commit no clone holds, as when the graph recorded a history this worker never fetched."""
REWRITTEN_AT = datetime(2026, 10, 6, 9, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def capture_sync_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=SYNC_LOGGER)


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


def configure_repositories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))
    monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])


async def clone_with_tracked_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    branches: tuple[str, ...] = (TRACKED,),
    local_branches: tuple[str, ...] | None = None,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
) -> TrackedRepository:
    """Clone a remote whose branches each carry one commit of their own, holding ``local_branches`` locally."""
    configure_repositories(tmp_path=tmp_path, monkeypatch=monkeypatch)

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


def recorder(store: InMemoryRepositoryRecordStore | FailingRepositoryRecordStore) -> HistoryRewriteRecorder:
    return HistoryRewriteRecorder(store=store, clock=lambda: REWRITTEN_AT)


def written_record(tracked: TrackedRepository, branch_name: str, previous_commit: str, commit: str) -> WrittenRecord:
    return WrittenRecord(
        repository_id=str(tracked.repository.id),
        infrahub_branch_name=branch_name,
        record=RewriteRecord(
            previous_commit=previous_commit, commit=commit, rewritten_at=REWRITTEN_AT, rewrite_count=1
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


async def test_a_default_branch_new_to_this_worker_fails_as_the_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed default branch reaches this worker as a branch it does not hold yet."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, local_branches=())
    tracked.repository.default_branch = TRACKED

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits())

    assert collected.failed_imports == [
        FailedImport(
            branch_name=TRACKED,
            step=ImportStep.COLLECTION,
            reason=(
                f"Unable to push the branch {TRACKED} to the remote for repository tracked-repo: "
                "the remote branch has commits that are missing locally (non-fast-forward): "
                "[rejected] (non-fast-forward)"
            ),
            on_default_branch=True,
        )
    ]
    assert collected.imports == []


async def test_a_default_branch_renamed_to_the_infrahub_default_is_queued_as_the_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clone still holds the old default branch, so the renamed one reaches it as a new branch."""
    configure_repositories(tmp_path=tmp_path, monkeypatch=monkeypatch)
    remote = LocalRemote.create(directory=tmp_path / "remote", trunk="master", branches=["main"])
    trunk_commit = str(remote.repo.commit("master"))
    repository = await clone_repository(
        id=UUIDT.new(),
        name="tracked-repo",
        location=str(remote.directory),
        client=GraphRecordingClient(branch_names=("main",)),
        default_branch="master",
        update_commit_value=False,
    )
    repository.default_branch = "main"

    collected = await repository.collect_pending_imports(graph_commits={"main": trunk_commit})

    assert collected.failed_imports == []
    assert collected.imports == [
        PendingObjectImport(
            infrahub_branch_name="main",
            commit=trunk_commit,
            on_default_branch=True,
            reconciled=ReconciledBranch(
                infrahub_branch_name="main",
                infrahub_branch_id="main-id",
                commit=trunk_commit,
                divergence=divergence(trunk_commit, trunk_commit, RefClassification.UNCHANGED, branch_name="main"),
            ),
        )
    ]


async def test_a_rewrite_is_recorded_on_the_branch_whose_commit_was_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)
    tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})
    store = InMemoryRepositoryRecordStore()

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(store)
    )

    assert collected.failed_imports == []
    assert store.written == [written_record(tracked, branch_name=TRACKED, previous_commit=imported, commit=rewritten)]


async def test_a_rewrite_found_on_a_branch_new_to_this_worker_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, local_branches=())
    imported = tracked.imported_commits[TRACKED]
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)
    store = InMemoryRepositoryRecordStore()

    await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits(), recorder=recorder(store))

    assert store.written == [written_record(tracked, branch_name=TRACKED, previous_commit=imported, commit=rewritten)]


async def test_a_rewritten_trunk_of_a_staging_repository_is_recorded_on_the_trunk_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The objects go to the staging branch, but the commit the classification compared is the trunk's."""
    tracked = await clone_with_tracked_branches(
        tmp_path=tmp_path, monkeypatch=monkeypatch, internal_status=RepositoryInternalStatus.STAGING
    )
    rewritten = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    store = InMemoryRepositoryRecordStore()

    await tracked.repository.collect_pending_imports(
        staging_branch=STAGING, graph_commits=tracked.graph_commits(), recorder=recorder(store)
    )

    assert store.written == [
        written_record(tracked, branch_name="main", previous_commit=tracked.trunk_commit, commit=rewritten)
    ]


async def test_a_worktree_that_resets_onto_a_commit_the_graph_already_records_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker that reconciled the branch recorded it, so this clone only catches up."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)
    store = InMemoryRepositoryRecordStore()

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(**{TRACKED: rewritten}), recorder=recorder(store)
    )

    assert [pending_import.commit for pending_import in collected.imports] == [rewritten]
    assert tracked.worktree_head(branch_name=TRACKED) == rewritten
    assert store.written == []


async def test_a_record_that_fails_fails_its_branch_alone_and_keeps_its_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The graph already records the new commit, so no later cycle would select the branch to import it.

    The rewritten branch is new to this worker and the trunk is not, so a failure is kept to its branch on both
    paths.
    """
    tracked = await clone_with_tracked_branches(
        tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER), local_branches=(OTHER,)
    )
    rewritten = tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)
    rewritten_trunk = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    advanced = tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other v2\n"})

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(FailingRepositoryRecordStore())
    )

    assert collected.failed_imports == [
        FailedImport(
            branch_name=TRACKED,
            step=ImportStep.RECORD,
            reason=f"The API is unreachable from {TRACKED}",
            on_default_branch=False,
        ),
        FailedImport(
            branch_name="main",
            step=ImportStep.RECORD,
            reason="The API is unreachable from main",
            on_default_branch=True,
        ),
    ]
    assert [(pending_import.infrahub_branch_name, pending_import.commit) for pending_import in collected.imports] == [
        (TRACKED, rewritten),
        ("main", rewritten_trunk),
        (OTHER, advanced),
    ]
    assert tracked.client.recorded_commits == [(TRACKED, rewritten), ("main", rewritten_trunk), (OTHER, advanced)]


@dataclass
class FailedRecordLogCase:
    name: str
    cause: Exception
    reason: str
    keeps_traceback: bool


FAILED_RECORD_LOG_CASES: list[FailedRecordLogCase] = [
    FailedRecordLogCase(
        name="graphql_error_gives_the_message_of_the_api",
        cause=GraphQLError(errors=[{"message": "Branch feature must be rebased before any updates can be made"}]),
        reason="Branch feature must be rebased before any updates can be made",
        keeps_traceback=False,
    ),
    FailedRecordLogCase(
        name="lost_connection_keeps_its_traceback",
        cause=ServerNotReachableError(address="http://infrahub-server:8000"),
        reason="ServerNotReachableError: Unable to connect to 'http://infrahub-server:8000'.",
        keeps_traceback=True,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_RECORD_LOG_CASES])
async def test_a_record_that_fails_is_logged_once_with_the_reason_of_its_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, test_case: FailedRecordLogCase
) -> None:
    """A recognised failure reads as the API worded it, and only an unexpected one carries its traceback."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    tracked.remote.commit(branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(FailingRepositoryRecordStore(cause=test_case.cause))
    )
    with pytest.raises(
        RepositoryError,
        match=rf"^Unable to synchronize the following branches of repository tracked-repo: "
        rf"{TRACKED} \(step=record\): {re.escape(test_case.reason)}$",
    ):
        tracked.repository.raise_if_branches_failed(collected.failed_imports)

    failure_logs = [
        record
        for record in caplog.records
        if record.name == SYNC_LOGGER and record.getMessage().startswith(("Failed to record", "Failed to synchronize"))
    ]
    assert [record.getMessage() for record in failure_logs] == [
        f"Failed to record the history rewrite of branch {TRACKED} of repository tracked-repo: {test_case.reason}"
    ]
    logged_error = failure_logs[0].exc_info[1] if failure_logs[0].exc_info else None
    assert logged_error is (test_case.cause if test_case.keeps_traceback else None)


class CountingCache(MemoryCache):
    """Counts the reads, so a test can check how often a cycle asks the cache."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    async def get(self, key: str) -> str | None:
        self.reads += 1
        return await super().get(key)


class CacheWrittenDuringTheCycle(MemoryCache):
    """Applies a pending write right after the first read, as an edit that lands while a cycle runs does."""

    def __init__(self, pending: dict[str, str]) -> None:
        super().__init__()
        self.pending = pending

    async def get(self, key: str) -> str | None:
        value = await super().get(key)
        self.storage.update(self.pending)
        self.pending = {}
        return value


@dataclass(frozen=True)
class RePointedTrunk:
    tracked: TrackedRepository
    discarded_commit: str
    """The trunk commit the graph records, which the newly tracked branch does not contain."""

    @property
    def new_head(self) -> str:
        return self.tracked.imported_commits[TRACKED]

    def graph_commits(self, **overrides: str) -> dict[str, str | None]:
        return self.tracked.graph_commits(**{"main": self.discarded_commit, **overrides})

    def retarget(self, classification: RefClassification, imported_commit: str, commit: str) -> PendingObjectImport:
        return PendingObjectImport(
            infrahub_branch_name="main",
            commit=commit,
            on_default_branch=True,
            reconciled=ReconciledBranch(
                infrahub_branch_name="main",
                infrahub_branch_id="main-id",
                commit=commit,
                divergence=RefDivergence(
                    branch_name=TRACKED,
                    infrahub_branch_name="main",
                    imported_commit=imported_commit,
                    remote_head=commit,
                    classification=classification,
                ),
            ),
        )


async def re_point_the_trunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branches: tuple[str, ...] = (TRACKED,)
) -> RePointedTrunk:
    """Make the tracked branch the default branch, after the trunk the graph records moved past it."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=branches)
    discarded_commit = tracked.remote.commit(branch_name="main", files={"data.txt": "main v2\n"})
    tracked.repository.default_branch = TRACKED
    return RePointedTrunk(tracked=tracked, discarded_commit=discarded_commit)


async def marked(tracked: TrackedRepository, target: str) -> RetargetMarkers:
    markers = RetargetMarkers(cache=MemoryCache())
    await markers.mark(repository_id=str(tracked.repository.id), target=target)
    return markers


async def is_marked(markers: RetargetMarkers, tracked: TrackedRepository, target: str) -> bool:
    return await markers.is_retargeted(repository_id=str(tracked.repository.id), target=target)


async def test_a_trunk_re_pointed_on_purpose_is_reset_records_nothing_and_clears_its_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()

    collected = await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert collected.failed_imports == []
    assert collected.imports == [
        re_pointed.retarget(
            RefClassification.RETARGET, imported_commit=re_pointed.discarded_commit, commit=re_pointed.new_head
        )
    ]
    assert re_pointed.tracked.client.recorded_commits == [("main", re_pointed.new_head)]
    assert store.written == []
    assert not await is_marked(markers, re_pointed.tracked, target=TRACKED)


async def test_a_trunk_re_pointed_without_a_marker_is_recorded_as_a_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    store = InMemoryRepositoryRecordStore()

    await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(),
        recorder=recorder(store),
        retarget_markers=RetargetMarkers(cache=MemoryCache()),
    )

    assert store.written == [
        written_record(
            re_pointed.tracked,
            branch_name="main",
            previous_commit=re_pointed.discarded_commit,
            commit=re_pointed.new_head,
        )
    ]


async def test_a_marker_suppresses_one_cycle_so_a_later_rewrite_of_the_trunk_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()
    await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )
    rewritten = re_pointed.tracked.remote.commit(
        branch_name=TRACKED, files={"data.txt": "feature rewritten\n"}, amend=True
    )

    await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(main=re_pointed.new_head),
        recorder=recorder(store),
        retarget_markers=markers,
    )

    assert store.written == [
        written_record(re_pointed.tracked, branch_name="main", previous_commit=re_pointed.new_head, commit=rewritten)
    ]


async def test_a_re_pointed_trunk_does_not_hide_a_rewrite_of_another_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch, branches=(TRACKED, OTHER))
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()
    rewritten = re_pointed.tracked.remote.commit(branch_name=OTHER, files={"data.txt": "other rewritten\n"}, amend=True)

    await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert store.written == [
        written_record(
            re_pointed.tracked,
            branch_name=OTHER,
            previous_commit=re_pointed.tracked.imported_commits[OTHER],
            commit=rewritten,
        )
    ]


async def test_a_re_pointed_trunk_that_fails_keeps_its_marker_for_the_next_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()
    re_pointed.tracked.client.rejecting_branches = frozenset({"main"})

    failed = await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert failed.failed_imports == [
        FailedImport(
            branch_name=TRACKED,
            step=ImportStep.COLLECTION,
            reason=(
                "An error occurred while executing the GraphQL Query None, "
                "[{'message': 'Branch main must be rebased before any updates can be made'}]"
            ),
            on_default_branch=True,
        )
    ]
    assert await is_marked(markers, re_pointed.tracked, target=TRACKED)

    re_pointed.tracked.client.rejecting_branches = frozenset()
    retried = await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert retried.failed_imports == []
    assert retried.imports == [
        re_pointed.retarget(
            RefClassification.RETARGET, imported_commit=re_pointed.discarded_commit, commit=re_pointed.new_head
        )
    ]
    assert store.written == []
    assert not await is_marked(markers, re_pointed.tracked, target=TRACKED)


async def test_a_marker_no_branch_needed_is_swept_so_a_later_rewrite_of_the_trunk_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-point that moves no commit, such as a renamed remote branch, selects no branch at all."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(tracked, target="main")
    store = InMemoryRepositoryRecordStore()

    idle = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert idle.imports == []
    assert not await is_marked(markers, tracked, target="main")

    rewritten = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert store.written == [
        written_record(tracked, branch_name="main", previous_commit=tracked.trunk_commit, commit=rewritten)
    ]


async def test_a_marker_for_another_target_is_left_for_the_cycle_that_synchronises_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default branch changed after this cycle read it, so this cycle still synchronises the old one."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()
    rewritten = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)

    await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert store.written == [
        written_record(tracked, branch_name="main", previous_commit=tracked.trunk_commit, commit=rewritten)
    ]
    assert await is_marked(markers, tracked, target=TRACKED)


async def test_an_inactive_repository_keeps_its_marker_for_the_cycle_that_synchronises_the_trunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cycle of an inactive repository leaves the trunk on the commit of the old default branch."""
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()
    re_pointed.tracked.repository.internal_status = RepositoryInternalStatus.INACTIVE

    idle = await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert idle.imports == []
    assert await is_marked(markers, re_pointed.tracked, target=TRACKED)

    re_pointed.tracked.repository.internal_status = RepositoryInternalStatus.ACTIVE
    active = await re_pointed.tracked.repository.collect_pending_imports(
        graph_commits=re_pointed.graph_commits(), recorder=recorder(store), retarget_markers=markers
    )

    assert active.imports == [
        re_pointed.retarget(
            RefClassification.RETARGET, imported_commit=re_pointed.discarded_commit, commit=re_pointed.new_head
        )
    ]
    assert store.written == []
    assert not await is_marked(markers, re_pointed.tracked, target=TRACKED)


async def test_a_re_pointed_trunk_of_a_staging_repository_records_nothing_and_clears_its_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The objects go to the staging branch, but the commit the classification compared is the trunk's."""
    re_pointed = await re_point_the_trunk(tmp_path=tmp_path, monkeypatch=monkeypatch)
    re_pointed.tracked.repository.internal_status = RepositoryInternalStatus.STAGING
    markers = await marked(re_pointed.tracked, target=TRACKED)
    store = InMemoryRepositoryRecordStore()

    collected = await re_pointed.tracked.repository.collect_pending_imports(
        staging_branch=STAGING,
        graph_commits=re_pointed.graph_commits(),
        recorder=recorder(store),
        retarget_markers=markers,
    )

    assert collected.failed_imports == []
    assert collected.imports == [
        PendingObjectImport(
            infrahub_branch_name=STAGING,
            commit=re_pointed.new_head,
            git_branch_name=TRACKED,
            on_default_branch=True,
            reconciled=ReconciledBranch(
                infrahub_branch_name="main",
                infrahub_branch_id="main-id",
                commit=re_pointed.new_head,
                divergence=RefDivergence(
                    branch_name=TRACKED,
                    infrahub_branch_name="main",
                    imported_commit=re_pointed.discarded_commit,
                    remote_head=re_pointed.new_head,
                    classification=RefClassification.RETARGET,
                ),
            ),
        )
    ]
    assert store.written == []
    assert not await is_marked(markers, re_pointed.tracked, target=TRACKED)


async def test_a_default_branch_the_remote_does_not_hold_yet_keeps_its_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    tracked.repository.default_branch = "release"
    markers = await marked(tracked, target="release")

    await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(),
        recorder=recorder(InMemoryRepositoryRecordStore()),
        retarget_markers=markers,
    )

    assert await is_marked(markers, tracked, target="release")


async def test_a_cycle_without_a_marker_reads_the_cache_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    cache = CountingCache()

    await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(),
        recorder=recorder(InMemoryRepositoryRecordStore()),
        retarget_markers=RetargetMarkers(cache=cache),
    )

    assert cache.reads == 1


async def test_a_marker_written_after_the_read_is_left_for_the_next_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trunk is already on the remote head, so a sweep of this cycle would delete the new marker."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    edit = MemoryCache()
    await RetargetMarkers(cache=edit).mark(repository_id=str(tracked.repository.id), target="main")
    markers = RetargetMarkers(cache=CacheWrittenDuringTheCycle(pending=edit.storage))

    await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(),
        recorder=recorder(InMemoryRepositoryRecordStore()),
        retarget_markers=markers,
    )

    assert await is_marked(markers, tracked, target="main")


def pushed_state(tracked: TrackedRepository, last_delivered_commit: str) -> InMemoryDeliveryState:
    """A delivery state with no pending push, whose last push delivered the given commit."""
    repository_id = str(tracked.repository.id)
    state = InMemoryDeliveryState(
        clock=FixedClock(now=REWRITTEN_AT), repository_names={repository_id: tracked.repository.name}
    )
    state.intents[repository_id] = replace(state.intents[repository_id], last_delivered_commit=last_delivered_commit)
    return state


def reverted_push(state: InMemoryDeliveryState, tracked: TrackedRepository) -> tuple[str, str] | None:
    reverted = state.intents[str(tracked.repository.id)].reverted
    return (reverted.delivered_commit, reverted.new_head) if reverted else None


async def test_a_rewrite_of_the_default_branch_that_discards_the_pushed_commit_records_a_reverted_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    rewritten_trunk = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    state = pushed_state(tracked, last_delivered_commit=tracked.trunk_commit)

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits(), state=state)

    assert collected.failed_imports == []
    assert reverted_push(state, tracked) == (tracked.trunk_commit, rewritten_trunk)
    assert (
        f"The rewrite of branch main of repository tracked-repo discarded the pushed commit {tracked.trunk_commit}, "
        f"the branch now points to {rewritten_trunk}"
    ) in caplog.messages


async def test_a_rewrite_of_the_default_branch_that_keeps_the_pushed_commit_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the commit imported after the push is discarded, so the pushed commit is still on the remote."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    imported_trunk = tracked.remote.commit(branch_name="main", files={"data.txt": "main v2\n"})
    await tracked.repository.fetch()
    tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    state = pushed_state(tracked, last_delivered_commit=tracked.trunk_commit)

    collected = await tracked.repository.collect_pending_imports(
        graph_commits=tracked.graph_commits(main=imported_trunk), state=state
    )

    assert collected.failed_imports == []
    assert reverted_push(state, tracked) is None


async def test_a_reverted_push_that_fails_to_record_fails_the_default_branch_and_keeps_its_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The graph already records the new commit, so no later cycle would select the branch to import it."""
    tracked = await clone_with_tracked_branches(tmp_path=tmp_path, monkeypatch=monkeypatch)
    rewritten_trunk = tracked.remote.commit(branch_name="main", files={"data.txt": "main rewritten\n"}, amend=True)
    state = pushed_state(tracked, last_delivered_commit=tracked.trunk_commit)
    state.failures["record_reverted"] = [RepositoryError(identifier="tracked-repo", message="The database is down")]

    collected = await tracked.repository.collect_pending_imports(graph_commits=tracked.graph_commits(), state=state)

    assert collected.failed_imports == [
        FailedImport(
            branch_name="main",
            step=ImportStep.RECORD,
            reason="RepositoryError: The database is down",
            on_default_branch=True,
        )
    ]
    assert [(pending_import.infrahub_branch_name, pending_import.commit) for pending_import in collected.imports] == [
        ("main", rewritten_trunk)
    ]
