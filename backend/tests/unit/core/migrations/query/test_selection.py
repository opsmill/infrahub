from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.migrations.query.selection import MigrationSelectionQuery
from infrahub.core.query import QueryType
from infrahub.core.timestamp import Timestamp

T1 = "2026-01-01T00:00:01.000000Z"
T2 = "2026-01-01T00:00:02.000000Z"


class SelectionQueryForTest(MigrationSelectionQuery):
    name = "selection_query_for_test"
    type = QueryType.WRITE


@dataclass
class OperationAtsParamTestCase:
    name: str
    at: str
    operation_ats: list[str]
    expected: list[str]


OPERATION_ATS_PARAM_TEST_CASES: list[OperationAtsParamTestCase] = [
    OperationAtsParamTestCase(
        name="no_operation_ats_gives_its_own_at",
        at=T1,
        operation_ats=[],
        expected=[T1],
    ),
    OperationAtsParamTestCase(
        name="own_at_is_added_after_the_earlier_steps",
        at=T2,
        operation_ats=[T1],
        expected=[T1, T2],
    ),
    OperationAtsParamTestCase(
        name="own_at_already_listed_is_not_repeated",
        at=T2,
        operation_ats=[T1, T2],
        expected=[T1, T2],
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in OPERATION_ATS_PARAM_TEST_CASES],
)
def test_operation_ats_param(test_case: OperationAtsParamTestCase) -> None:
    query = SelectionQueryForTest(
        at=Timestamp(test_case.at), operation_ats=[Timestamp(at) for at in test_case.operation_ats]
    )

    assert query.operation_ats_param == test_case.expected
