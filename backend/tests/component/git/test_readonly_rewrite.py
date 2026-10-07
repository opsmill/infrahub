"""A read-only repository whose tracked ref no longer leads from the commit Infrahub imported."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.recorder import HistoryRewriteRecorder
from infrahub.git.divergence.store import SdkRepositoryReader
from infrahub.git.models import GitReadOnlyRepositoryImportCommit
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.git.tasks import import_read_only_repository_last_commit
from infrahub.workflows.catalogue import GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT, GIT_REPOSITORIES_PULL_READ_ONLY
from tests.adapters.repository_record_store import (
    FailingGraphCommitReader,
    FailingRepositoryRecordStore,
    InMemoryRepositoryRecordStore,
)
from tests.helpers.git import LocalRemote
from tests.helpers.test_app import TestInfrahubAppHoldingWorkflows

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock import LockTimeline
    from tests.adapters.workflow import HoldingWorkflowExecution

TRACKED_REF = "release"
OTHER_BRANCH = "hotfix"
NO_RECORD = (None, None, None, None)
RE_POINT_WORKFLOWS = [GIT_REPOSITORIES_PULL_READ_ONLY.name, GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT.name]

IMPORT_LAST_COMMIT = """
mutation ImportLastCommit($id: String!) {
    InfrahubReadOnlyRepositoryImportLastCommit(data: { id: $id }) {
        ok
    }
}
"""


@dataclass(frozen=True)
class TrackedRef:
    name: str
    repository_id: str
    remote: LocalRemote
    imported_commit: str
    """The head of the tracked ref when the repository was added, which the graph records."""


async def _read_repository(db: InfrahubDatabase, tracked: TrackedRef) -> CoreReadOnlyRepository:
    return await NodeManager.get_one(db=db, id=tracked.repository_id, kind=CoreReadOnlyRepository, raise_on_error=True)


async def _rewrite_record(
    db: InfrahubDatabase, tracked: TrackedRef
) -> tuple[str | None, str | None, str | None, int | None]:
    repository = await _read_repository(db=db, tracked=tracked)
    return (
        repository.last_rewrite_previous_commit.value,
        repository.last_rewrite_commit.value,
        repository.last_rewrite_at.value,
        repository.rewrite_count.value,
    )


async def _import_last_commit(client: InfrahubClient, tracked: TrackedRef) -> None:
    response = await client.execute_graphql(query=IMPORT_LAST_COMMIT, variables={"id": tracked.repository_id})
    assert response["InfrahubReadOnlyRepositoryImportLastCommit"]["ok"] is True


async def _open_clone(client: InfrahubClient, tracked: TrackedRef) -> InfrahubReadOnlyRepository:
    return await InfrahubReadOnlyRepository.init(
        id=tracked.repository_id,
        name=tracked.name,
        client=client,
        infrahub_branch_name=registry.default_branch,
        ref=TRACKED_REF,
    )


async def _wait_until_queued(timeline: LockTimeline, lock_name: str, count: int) -> None:
    async def queued() -> None:
        while timeline.waiting(lock_name) != count:  # noqa: ASYNC110
            await asyncio.sleep(0.05)

    await asyncio.wait_for(queued(), timeout=60)


def _rewrite_the_tracked_ref(tracked: TrackedRef) -> str:
    return tracked.remote.commit(branch_name=TRACKED_REF, files={"data.txt": "rewritten\n"}, amend=True)


class TestReadOnlyRepositoryRewrite(TestInfrahubAppHoldingWorkflows):
    async def _add_repository(
        self, client: InfrahubClient, db: InfrahubDatabase, tmp_path: Path, name: str
    ) -> TrackedRef:
        """Add a read-only repository whose tracked ref carries one commit of its own, beside a branch it does not hold."""
        remote = LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[])
        imported_commit = remote.commit(branch_name=TRACKED_REF, files={"data.txt": "imported\n"})
        remote.commit(branch_name=OTHER_BRANCH, files={"other.txt": "other\n"})
        repository = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY, name=name, location=str(remote.directory), ref=TRACKED_REF
        )
        await repository.save()

        tracked = TrackedRef(name=name, repository_id=repository.id, remote=remote, imported_commit=imported_commit)
        added = await _read_repository(db=db, tracked=tracked)
        assert added.commit.value == imported_commit, "the tracked ref was not imported when the repository was added"
        return tracked

    async def test_a_rewritten_ref_is_imported_and_recorded_without_a_reset(
        self, db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, git_repos_dir: Path
    ) -> None:
        """The local clone of the ref stays where the import of the repository left it."""
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="rewritten-ref")
        rewritten = _rewrite_the_tracked_ref(tracked)
        started_at = datetime.now(tz=UTC)

        await _import_last_commit(client=client, tracked=tracked)

        finished_at = datetime.now(tz=UTC)
        repository = await _read_repository(db=db, tracked=tracked)
        assert (
            repository.commit.value,
            repository.last_rewrite_previous_commit.value,
            repository.last_rewrite_commit.value,
            repository.rewrite_count.value,
        ) == (rewritten, tracked.imported_commit, rewritten, 1)
        assert repository.last_rewrite_at.value is not None
        assert started_at <= datetime.fromisoformat(repository.last_rewrite_at.value) <= finished_at
        clone = await _open_clone(client=client, tracked=tracked)
        assert clone.get_branches_from_local()[TRACKED_REF].commit == tracked.imported_commit

    async def test_a_fast_forwarded_ref_is_imported_and_records_nothing(
        self, db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, git_repos_dir: Path
    ) -> None:
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="fast-forwarded-ref")
        advanced = tracked.remote.commit(branch_name=TRACKED_REF, files={"data.txt": "advanced\n"})

        await _import_last_commit(client=client, tracked=tracked)

        assert (await _read_repository(db=db, tracked=tracked)).commit.value == advanced
        assert await _rewrite_record(db=db, tracked=tracked) == NO_RECORD

    async def test_two_imports_queued_behind_one_rewrite_record_it_once(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        recording_lock_timeline: LockTimeline,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """Both imports wait for the repository lock while another run holds it."""
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="queued-imports")
        rewritten = _rewrite_the_tracked_ref(tracked)
        model = GitReadOnlyRepositoryImportCommit(
            repository_id=tracked.repository_id,
            repository_name=tracked.name,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            infrahub_branch_name=registry.default_branch,
            ref=TRACKED_REF,
        )
        held = asyncio.Event()
        release = asyncio.Event()

        async def hold_the_repository_lock() -> None:
            async with lock.registry.get(name=tracked.name, namespace="repository"):
                held.set()
                await release.wait()

        holder = asyncio.create_task(hold_the_repository_lock())
        await asyncio.wait_for(held.wait(), timeout=10)
        imports = [asyncio.create_task(import_read_only_repository_last_commit(model=model)) for _ in range(2)]
        try:
            await _wait_until_queued(timeline=recording_lock_timeline, lock_name=f"repository.{tracked.name}", count=2)
        finally:
            release.set()
        await asyncio.wait_for(asyncio.gather(holder, *imports), timeout=120)

        record = await _rewrite_record(db=db, tracked=tracked)
        assert (record[0], record[1], record[3]) == (tracked.imported_commit, rewritten, 1)

    async def test_a_ref_moved_to_another_branch_records_nothing(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The import runs before the pull, so it finds the commit the old ref imported."""
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="moved-ref")
        other_head = tracked.remote.repo.commit(OTHER_BRANCH).hexsha
        repository = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=tracked.repository_id)

        with workflow_local.hold() as held:
            repository.ref.value = OTHER_BRANCH
            await repository.save()

        assert [submitted.workflow.name for submitted in held] == RE_POINT_WORKFLOWS
        assert (await _read_repository(db=db, tracked=tracked)).commit.value == tracked.imported_commit
        for submitted in reversed(held):
            await workflow_local.run(submitted)

        assert (await _read_repository(db=db, tracked=tracked)).commit.value == other_head
        assert await _rewrite_record(db=db, tracked=tracked) == NO_RECORD

    async def test_a_commit_pinned_outside_the_ref_records_nothing(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The import finds the pinned commit, which the head of the ref does not hold."""
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="pinned-commit")
        pinned = tracked.remote.repo.commit(OTHER_BRANCH).hexsha
        repository = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=tracked.repository_id)

        with workflow_local.hold() as held:
            repository.commit.value = pinned
            await repository.save()

        assert [submitted.workflow.name for submitted in held] == RE_POINT_WORKFLOWS
        assert (await _read_repository(db=db, tracked=tracked)).commit.value == pinned
        for submitted in held:
            await workflow_local.run(submitted)

        assert await _rewrite_record(db=db, tracked=tracked) == NO_RECORD

    async def test_a_graph_that_cannot_be_read_still_imports_the_latest_commit(
        self, db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, git_repos_dir: Path
    ) -> None:
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="unreadable-graph")
        rewritten = _rewrite_the_tracked_ref(tracked)
        store = InMemoryRepositoryRecordStore()
        clone = await _open_clone(client=client, tracked=tracked)

        await clone.update_latest_commit(
            graph_commits=FailingGraphCommitReader(), recorder=HistoryRewriteRecorder(store=store)
        )

        assert (await _read_repository(db=db, tracked=tracked)).commit.value == rewritten
        assert store.written == []

    async def test_a_record_that_fails_leaves_the_new_commit_imported(
        self, db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, git_repos_dir: Path
    ) -> None:
        tracked = await self._add_repository(client=client, db=db, tmp_path=tmp_path, name="failed-record")
        rewritten = _rewrite_the_tracked_ref(tracked)
        clone = await _open_clone(client=client, tracked=tracked)

        with pytest.raises(RepositoryError, match=rf"^The API is unreachable from {registry.default_branch}$"):
            await clone.update_latest_commit(
                graph_commits=SdkRepositoryReader(client=client),
                recorder=HistoryRewriteRecorder(store=FailingRepositoryRecordStore()),
            )

        assert (await _read_repository(db=db, tracked=tracked)).commit.value == rewritten
        assert await _rewrite_record(db=db, tracked=tracked) == NO_RECORD
