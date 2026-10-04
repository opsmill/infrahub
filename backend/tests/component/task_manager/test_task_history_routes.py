from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from prefect.server.database import provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.settings import temporary_settings
from tests.adapters.task_history import FailingRewriter, RecordingRewriter
from tests.helpers.task_manager_seed import days_ago, seed_flow_run, task_manager_database

from infrahub.prefect_server.app import router
from infrahub.prefect_server.task_history import (
    CleanupJobs,
    CleanupRewrite,
    ProcessCleanupLock,
    TaskHistoryCleanup,
    TaskHistoryTables,
    build_task_history_cleanup,
    get_cleanup_jobs,
    get_cleanup_lock,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator
    from pathlib import Path
    from uuid import UUID

    from prefect.server.database import PrefectDBInterface

    from infrahub.prefect_server.task_history import TableRewriter

CLEANUP_URL = "/infrahub/task-history/cleanup"
OLD_RUN_END = datetime(2026, 1, 15, 12, tzinfo=UTC)
OLD_RUNS = 3
RECENT_RUNS = 2


@pytest.fixture
def db(task_manager_database_path: Path) -> PrefectDBInterface:
    return task_manager_database(task_manager_database_path)


@pytest.fixture
def cleanup_lock() -> ProcessCleanupLock:
    return ProcessCleanupLock()


@pytest.fixture
async def cleanup_lock_held_elsewhere(cleanup_lock: ProcessCleanupLock) -> AsyncIterator[None]:
    """The cleanup lock held, as another task manager would hold it, until the test ends."""
    assert await cleanup_lock.try_acquire()
    yield
    await cleanup_lock.release()


@pytest.fixture
def app(db: PrefectDBInterface, cleanup_lock: ProcessCleanupLock) -> Generator[FastAPI, None, None]:
    """Infrahub's task manager routes on the test's own database, cleanup registry and cleanup lock."""
    app = FastAPI()
    app.include_router(router)
    jobs = CleanupJobs()
    app.dependency_overrides[provide_database_interface] = lambda: db
    app.dependency_overrides[get_cleanup_jobs] = lambda: jobs
    app.dependency_overrides[get_cleanup_lock] = lambda: cleanup_lock
    with temporary_settings(updates={"server.services.db_vacuum.retention_period": timedelta(days=30)}):
        yield app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _rewrite_through(app: FastAPI, db: PrefectDBInterface, rewriter: TableRewriter) -> None:
    """Have the routes run their cleanups with the rewriter, which SQLite has none of."""
    app.dependency_overrides[build_task_history_cleanup] = lambda: TaskHistoryCleanup(
        tables=TaskHistoryTables(db=db, ids_per_statement=999), rewriter=rewriter
    )


async def _seed_old_run(db: PrefectDBInterface) -> UUID:
    run = await seed_flow_run(
        db=db, state_type=StateType.COMPLETED, start_time=OLD_RUN_END - timedelta(hours=1), end_time=OLD_RUN_END
    )
    return run.id


async def _seed_mostly_old_runs(db: PrefectDBInterface) -> set[UUID]:
    """Seed old runs and fewer recent ones, so that the deletes free more than half of the runs.

    Returns:
        The recent runs, which the cleanup keeps.

    """
    for _ in range(OLD_RUNS):
        await _seed_old_run(db=db)
    recent = [
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(6), end_time=days_ago(5))
        for _ in range(RECENT_RUNS)
    ]
    return {run.id for run in recent}


async def _flow_run_ids(db: PrefectDBInterface) -> set[UUID]:
    async with db.session_context() as session:
        return set(await session.scalars(sa.select(db.FlowRun.id)))


async def _finished_job(client: httpx.AsyncClient, job_id: str) -> dict[str, Any]:
    async with asyncio.timeout(30):
        while True:
            job: dict[str, Any] = (await client.get(f"{CLEANUP_URL}/{job_id}")).json()
            if job["state"] != "running":
                return job
            await asyncio.sleep(0.05)


@dataclass
class SecondStartCase:
    name: str
    first: CleanupRewrite
    second: CleanupRewrite
    expected_rewrite: CleanupRewrite


SECOND_START_CASES: list[SecondStartCase] = [
    SecondStartCase(
        name="never_raised_to_if_freed",
        first=CleanupRewrite.NEVER,
        second=CleanupRewrite.IF_FREED,
        expected_rewrite=CleanupRewrite.IF_FREED,
    ),
    SecondStartCase(
        name="never_raised_to_always",
        first=CleanupRewrite.NEVER,
        second=CleanupRewrite.ALWAYS,
        expected_rewrite=CleanupRewrite.ALWAYS,
    ),
    SecondStartCase(
        name="always_kept_against_never",
        first=CleanupRewrite.ALWAYS,
        second=CleanupRewrite.NEVER,
        expected_rewrite=CleanupRewrite.ALWAYS,
    ),
    SecondStartCase(
        name="if_freed_kept_against_never",
        first=CleanupRewrite.IF_FREED,
        second=CleanupRewrite.NEVER,
        expected_rewrite=CleanupRewrite.IF_FREED,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SECOND_START_CASES])
async def test_a_second_start_returns_the_running_cleanup_with_the_stronger_rewrite(
    app: FastAPI, db: PrefectDBInterface, case: SecondStartCase
) -> None:
    """A start while a cleanup runs returns that cleanup, which then rewrites with the stronger of the two modes."""
    recent_runs = await _seed_mostly_old_runs(db=db)
    rewriter = RecordingRewriter(pause_at_call=1)
    _rewrite_through(app=app, db=db, rewriter=rewriter)

    async with _client(app) as client:
        first = await client.post(CLEANUP_URL, json={"rewrite": case.first.value})
        await rewriter.wait_until_paused()
        second = await client.post(CLEANUP_URL, json={"rewrite": case.second.value})
        rewriter.resume()
        job = first.json()
        finished = await _finished_job(client=client, job_id=job["id"])

    assert (first.status_code, second.status_code) == (202, 202)
    assert (job["rewrite"], second.json()) == (case.first.value, job | {"rewrite": case.expected_rewrite.value})
    assert finished == job | {
        "state": "completed",
        "rewrite": case.expected_rewrite.value,
        "rewritten": True,
        "deleted_runs": OLD_RUNS,
        "current_day": "2026-01-15",
        "size_before": 1000,
        "size_after": 100,
        "not_rewritten": ["log"],
    }
    assert rewriter.calls == ["total_size", "rewrite", "total_size"]
    assert await _flow_run_ids(db=db) == recent_runs


async def test_a_stronger_start_after_the_cleanup_decided_against_a_rewrite_makes_it_decide_again(
    app: FastAPI, db: PrefectDBInterface
) -> None:
    """A stronger mode that arrives after the decision is decided again, against the runs counted when the cleanup began."""
    await _seed_mostly_old_runs(db=db)
    rewriter = RecordingRewriter(pause_at_call=2)
    _rewrite_through(app=app, db=db, rewriter=rewriter)

    async with _client(app) as client:
        started = await client.post(CLEANUP_URL, json={"rewrite": "never"})
        await rewriter.wait_until_paused()
        raised = await client.post(CLEANUP_URL, json={"rewrite": "if_freed"})
        rewriter.resume()
        finished = await _finished_job(client=client, job_id=started.json()["id"])

    assert raised.json()["id"] == started.json()["id"]
    assert rewriter.calls == ["total_size", "total_size", "rewrite", "total_size"]
    assert (finished["state"], finished["rewrite"], finished["rewritten"], finished["size_after"]) == (
        "completed",
        "if_freed",
        True,
        100,
    )


async def test_a_stronger_start_after_the_cleanup_rewrote_rewrites_nothing_more(
    app: FastAPI, db: PrefectDBInterface
) -> None:
    """A stronger mode that arrives after the cleanup rewrote the tables leaves them as they are."""
    await _seed_mostly_old_runs(db=db)
    rewriter = RecordingRewriter(pause_at_call=3)
    _rewrite_through(app=app, db=db, rewriter=rewriter)

    async with _client(app) as client:
        started = await client.post(CLEANUP_URL, json={"rewrite": "if_freed"})
        await rewriter.wait_until_paused()
        raised = await client.post(CLEANUP_URL, json={"rewrite": "always"})
        rewriter.resume()
        finished = await _finished_job(client=client, job_id=started.json()["id"])

    assert raised.json()["id"] == started.json()["id"]
    assert rewriter.calls == ["total_size", "rewrite", "total_size"]
    assert (finished["state"], finished["rewrite"], finished["rewritten"], finished["size_after"]) == (
        "completed",
        "always",
        True,
        100,
    )


async def test_a_start_after_a_completed_cleanup_starts_a_new_cleanup(app: FastAPI, db: PrefectDBInterface) -> None:
    """A completed cleanup frees this task manager and the cleanup lock for the next start."""
    await _seed_old_run(db=db)

    async with _client(app) as client:
        first = (await client.post(CLEANUP_URL, json={"rewrite": "never"})).json()
        completed = await _finished_job(client=client, job_id=first["id"])
        second = await client.post(CLEANUP_URL, json={"rewrite": "never"})
        assert second.status_code == 202, second.json()
        completed_again = await _finished_job(client=client, job_id=second.json()["id"])

    assert completed == first | {"state": "completed", "deleted_runs": 1, "current_day": "2026-01-15"}
    assert second.json()["id"] != first["id"]
    assert completed_again == second.json() | {"state": "completed", "deleted_runs": 0, "current_day": None}


async def test_a_start_after_a_failed_cleanup_starts_a_new_cleanup(app: FastAPI, db: PrefectDBInterface) -> None:
    """A failed cleanup frees this task manager and the cleanup lock for the next start."""
    await _seed_old_run(db=db)
    _rewrite_through(app=app, db=db, rewriter=FailingRewriter())
    failure = {
        "state": "failed",
        "size_before": 1000,
        "error": "The cleanup failed with RuntimeError; the task manager log has the details",
    }

    async with _client(app) as client:
        first = (await client.post(CLEANUP_URL, json={"rewrite": "always"})).json()
        failed = await _finished_job(client=client, job_id=first["id"])
        second = await client.post(CLEANUP_URL, json={"rewrite": "always"})
        assert second.status_code == 202, second.json()
        failed_again = await _finished_job(client=client, job_id=second.json()["id"])

    assert failed == first | failure | {"deleted_runs": 1, "current_day": "2026-01-15"}
    assert second.json()["id"] != first["id"]
    assert failed_again == second.json() | failure | {"deleted_runs": 0, "current_day": None}


@pytest.mark.usefixtures("cleanup_lock_held_elsewhere")
async def test_start_is_refused_while_another_task_manager_holds_the_cleanup_lock(
    app: FastAPI, db: PrefectDBInterface
) -> None:
    """A cleanup is refused with 409, and deletes nothing, while the cleanup lock is held outside this task manager."""
    old_run = await _seed_old_run(db=db)

    async with _client(app) as client:
        response = await client.post(CLEANUP_URL, json={"rewrite": "never"})

    assert (response.status_code, response.json()) == (409, {"detail": "a cleanup is running elsewhere"})
    assert await _flow_run_ids(db=db) == {old_run}


async def test_an_unknown_cleanup_is_not_found(app: FastAPI) -> None:
    """Reading a cleanup the task manager does not know answers 404."""
    async with _client(app) as client:
        response = await client.get(f"{CLEANUP_URL}/unknown")

    assert (response.status_code, response.json()) == (404, {"detail": "the cleanup is unknown to this task manager"})


async def test_cleanup_on_sqlite_reports_that_it_rewrites_nothing(app: FastAPI, db: PrefectDBInterface) -> None:
    """On SQLite a cleanup asked to always rewrite the tables deletes the old runs and reports neither a rewrite nor sizes."""
    await _seed_old_run(db=db)
    before = datetime.now(UTC)

    async with _client(app) as client:
        started = await client.post(CLEANUP_URL, json={"rewrite": "always"})
        after = datetime.now(UTC)
        job = started.json()
        finished = await _finished_job(client=client, job_id=job["id"])

    assert started.status_code == 202
    assert before - timedelta(days=30) <= datetime.fromisoformat(job["cutoff"]) <= after - timedelta(days=30)
    assert finished == {
        "id": job["id"],
        "state": "completed",
        "rewrite": "always",
        "rewritten": False,
        "cutoff": job["cutoff"],
        "deleted_runs": 1,
        "current_day": "2026-01-15",
        "size_before": None,
        "size_after": None,
        "not_rewritten": [],
        "error": None,
    }
    assert await _flow_run_ids(db=db) == set()
