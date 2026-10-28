from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.exc import DBAPIError

from infrahub.prefect_server.task_history import TableOutcome, rewrite_error_outcome
from tests.adapters.task_history import database_error


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
