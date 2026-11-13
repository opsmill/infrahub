from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError

from infrahub.prefect_server.task_history import (
    TableOutcome,
    TableSpace,
    TaskHistoryCleanup,
    TaskHistoryTables,
    rewrite_error_outcome,
)
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupJobState, CleanupRewrite
from tests.adapters.task_history import RecordingRewriter, database_error
from tests.helpers.task_manager_seed import task_manager_database


@dataclass
class RewriteErrorTestCase:
    name: str
    error: DBAPIError
    expected_outcome: TableOutcome | None


REWRITE_ERROR_TEST_CASES: list[RewriteErrorTestCase] = [
    RewriteErrorTestCase(
        name="statement_timeout",
        error=database_error(sqlstate="57014"),
        expected_outcome=TableOutcome.TIMED_OUT,
    ),
    RewriteErrorTestCase(
        name="lock_timeout",
        error=database_error(sqlstate="55P03"),
        expected_outcome=TableOutcome.LOCKED,
    ),
    RewriteErrorTestCase(
        name="disk_full",
        error=database_error(sqlstate="53100"),
        expected_outcome=TableOutcome.FAILED,
    ),
    RewriteErrorTestCase(
        name="deadlock",
        error=database_error(sqlstate="40P01"),
        expected_outcome=TableOutcome.FAILED,
    ),
    RewriteErrorTestCase(
        name="lost_connection",
        error=database_error(sqlstate="08003", connection_invalidated=True),
        expected_outcome=None,
    ),
    RewriteErrorTestCase(
        name="client_error",
        error=DBAPIError(
            statement="VACUUM FULL log",
            params=None,
            orig=Exception("cannot perform operation: another operation is in progress"),
        ),
        expected_outcome=None,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REWRITE_ERROR_TEST_CASES])
def test_a_rewrite_error_is_classified_by_the_sqlstate_the_server_sent(test_case: RewriteErrorTestCase) -> None:
    assert rewrite_error_outcome(error=test_case.error) is test_case.expected_outcome


def _job(rewrite: CleanupRewrite, deleted_runs: int = 0) -> CleanupJob:
    return CleanupJob(
        id="test",
        state=CleanupJobState.RUNNING,
        rewrite=rewrite,
        cutoff=datetime(2026, 1, 15, tzinfo=UTC),
        deleted_runs=deleted_runs,
        size_before=1000,
    )


def _cleanup(rewriter: RecordingRewriter) -> TaskHistoryCleanup:
    # The database interface is lazy: no engine, session, or tables are created.
    tables = TaskHistoryTables(db=task_manager_database(Path(":memory:")), ids_per_statement=999, lock_timeout=None)
    return TaskHistoryCleanup(tables=tables, rewriter=rewriter, runs_per_transaction=1000)


MOSTLY_FREE = TableSpace(disk_bytes=1000, live_bytes=499)
HALF_FREE = TableSpace(disk_bytes=1000, live_bytes=500)
MOSTLY_LIVE = TableSpace(disk_bytes=1000, live_bytes=900)


@dataclass
class RewriteDecisionCase:
    name: str
    rewrite: CleanupRewrite
    deleted_runs: int
    spaces: dict[str, TableSpace]
    locked: tuple[str, ...]
    timed_out: tuple[str, ...]
    failed: tuple[str, ...]
    expected_calls: list[str]
    expected_rewritten: list[str]
    expected_mostly_live: list[str]
    expected_not_rewritten: list[str]
    expected_timed_out: list[str]
    expected_failed: list[str]
    expected_size_after: int


REWRITE_DECISION_CASES: list[RewriteDecisionCase] = [
    RewriteDecisionCase(
        name="if_freed_rewrites_each_table_more_than_half_free",
        rewrite=CleanupRewrite.IF_FREED,
        deleted_runs=3,
        spaces={
            "flow_run": MOSTLY_FREE,
            "task_run": MOSTLY_FREE,
            "log": MOSTLY_FREE,
            "artifact": MOSTLY_FREE,
            "events": HALF_FREE,
            "event_resources": MOSTLY_FREE,
        },
        locked=("log",),
        timed_out=("artifact",),
        failed=("task_run",),
        expected_calls=[
            "space flow_run",
            "space task_run",
            "space log",
            "space artifact",
            "space events",
            "space event_resources",
            "rewrite flow_run task_run log artifact event_resources",
            "total_size",
        ],
        expected_rewritten=["flow_run", "event_resources"],
        expected_mostly_live=["events"],
        expected_not_rewritten=["log"],
        expected_timed_out=["artifact"],
        expected_failed=["task_run"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="if_freed_with_the_runs_deleted_before_the_cleanup_started",
        rewrite=CleanupRewrite.IF_FREED,
        deleted_runs=0,
        spaces={"flow_run": TableSpace(disk_bytes=1000, live_bytes=100)},
        locked=(),
        timed_out=(),
        failed=(),
        expected_calls=["space flow_run", "rewrite flow_run", "total_size"],
        expected_rewritten=["flow_run"],
        expected_mostly_live=[],
        expected_not_rewritten=[],
        expected_timed_out=[],
        expected_failed=[],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="if_freed_with_every_table_mostly_live",
        rewrite=CleanupRewrite.IF_FREED,
        deleted_runs=3,
        spaces={"flow_run": MOSTLY_LIVE, "events": MOSTLY_LIVE},
        locked=(),
        timed_out=(),
        failed=(),
        expected_calls=["space flow_run", "space events", "total_size"],
        expected_rewritten=[],
        expected_mostly_live=["flow_run", "events"],
        expected_not_rewritten=[],
        expected_timed_out=[],
        expected_failed=[],
        expected_size_after=1000,
    ),
    RewriteDecisionCase(
        name="never_with_a_table_holding_no_live_rows",
        rewrite=CleanupRewrite.NEVER,
        deleted_runs=3,
        spaces={"flow_run": TableSpace(disk_bytes=1000, live_bytes=0)},
        locked=(),
        timed_out=(),
        failed=(),
        expected_calls=["total_size"],
        expected_rewritten=[],
        expected_mostly_live=[],
        expected_not_rewritten=[],
        expected_timed_out=[],
        expected_failed=[],
        expected_size_after=1000,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REWRITE_DECISION_CASES])
async def test_each_table_is_rewritten_when_the_cleanup_asks_and_most_of_it_is_free(
    case: RewriteDecisionCase,
) -> None:
    """Asked to rewrite, the cleanup rewrites each table whose live rows hold less than half of it, whoever freed it."""
    rewriter = RecordingRewriter(spaces=case.spaces, locked=case.locked, timed_out=case.timed_out, failed=case.failed)
    job = _job(rewrite=case.rewrite, deleted_runs=case.deleted_runs)
    cleanup = _cleanup(rewriter=rewriter)

    await cleanup.rewrite(job=job, mode=job.rewrite)

    assert rewriter.calls == case.expected_calls
    assert (
        job.deleted_runs,
        job.rewrite,
        job.rewritten,
        job.mostly_live,
        job.not_rewritten,
        job.timed_out,
        job.failed,
        job.size_before,
        job.size_after,
    ) == (
        case.deleted_runs,
        case.rewrite,
        case.expected_rewritten,
        case.expected_mostly_live,
        case.expected_not_rewritten,
        case.expected_timed_out,
        case.expected_failed,
        1000,
        case.expected_size_after,
    )


async def test_a_rewrite_that_fails_at_a_table_keeps_the_outcome_of_each_table_before_it() -> None:
    """A rewrite that fails at a table keeps what it did with each table before it, and measures no size after."""
    rewriter = RecordingRewriter(
        spaces={
            "flow_run": MOSTLY_FREE,
            "log": MOSTLY_FREE,
            "artifact": MOSTLY_FREE,
            "task_run": MOSTLY_FREE,
            "event_resources": MOSTLY_FREE,
            "events": MOSTLY_LIVE,
        },
        locked=("log",),
        timed_out=("artifact",),
        fails_on="task_run",
    )
    job = _job(rewrite=CleanupRewrite.IF_FREED)
    cleanup = _cleanup(rewriter=rewriter)

    with pytest.raises(RuntimeError, match=r"^rewrite of task_run rejected$"):
        await cleanup.rewrite(job=job, mode=job.rewrite)

    assert rewriter.calls == [
        "space flow_run",
        "space log",
        "space artifact",
        "space task_run",
        "space event_resources",
        "space events",
        "rewrite flow_run log artifact task_run event_resources",
    ]
    assert (job.rewritten, job.mostly_live, job.not_rewritten, job.timed_out, job.size_after) == (
        ["flow_run"],
        ["events"],
        ["log"],
        ["artifact"],
        None,
    )
