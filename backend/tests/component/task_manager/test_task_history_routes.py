from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from prefect.server.database import provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.settings import temporary_settings
from tests.helpers.task_manager_seed import seed_flow_run, task_manager_database

from infrahub.prefect_server.app import router
from infrahub.prefect_server.task_history import CleanupJobs, ProcessCleanupLock, get_cleanup_jobs, get_cleanup_lock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator
    from pathlib import Path
    from uuid import UUID

    from prefect.server.database import PrefectDBInterface

CLEANUP_URL = "/infrahub/task-history/cleanup"
OLD_RUN_END = datetime(2026, 1, 15, 12, tzinfo=UTC)


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


@asynccontextmanager
async def _sqlite_write_lock(db: PrefectDBInterface) -> AsyncIterator[None]:
    """Hold the database's write lock, so that a cleanup waits before its first delete."""
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await session.execute(sa.select(1))
        yield


async def _seed_old_run(db: PrefectDBInterface) -> UUID:
    run = await seed_flow_run(
        db=db, state_type=StateType.COMPLETED, start_time=OLD_RUN_END - timedelta(hours=1), end_time=OLD_RUN_END
    )
    return run.id


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


async def test_a_second_start_returns_the_running_cleanup(app: FastAPI, db: PrefectDBInterface) -> None:
    """Starting a cleanup while one runs in the task manager returns the running cleanup instead of a new one."""
    await _seed_old_run(db=db)

    async with _client(app) as client:
        async with _sqlite_write_lock(db=db):
            first = await client.post(CLEANUP_URL, json={"rewrite": "never"})
            second = await client.post(CLEANUP_URL, json={"rewrite": "always"})
        finished = await _finished_job(client=client, job_id=first.json()["id"])

    assert (first.status_code, second.status_code) == (202, 202)
    assert second.json()["id"] == first.json()["id"]
    assert (first.json()["state"], second.json()["state"], second.json()["rewrite"]) == ("running", "running", "never")
    assert (finished["state"], finished["deleted_runs"]) == ("completed", 1)
    assert await _flow_run_ids(db=db) == set()


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
