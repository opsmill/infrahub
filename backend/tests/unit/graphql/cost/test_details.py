from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from starlette.datastructures import Headers

from infrahub.core.constants import RelationshipCardinality
from infrahub.graphql.cost.constants import ESTIMATE_FIELD_PATH
from infrahub.graphql.cost.details import build_query_cost_details, query_cost_details_requested
from infrahub.graphql.cost.models import (
    CostFigures,
    EstimateMode,
    EstimateReason,
    EstimateSource,
    FieldDescription,
    FieldEstimate,
    QueryEstimate,
    StatisticsPointer,
)
from infrahub.graphql.cost.recorder import QueryCostRecorder

PERSON_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
)
CARS_FIELD = FieldDescription(
    kind="TestCar", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.MANY
)
OWNER_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.ONE
)
TAGS_FIELD = FieldDescription(
    kind="BuiltinTag", relationship_identifier="builtintag__testcar", cardinality=RelationshipCardinality.MANY
)
PERSON_GROUPS_FIELD = FieldDescription(
    kind="CoreGroup", relationship_identifier="group_member", cardinality=RelationshipCardinality.MANY
)
CAR_GROUPS_FIELD = FieldDescription(
    kind="CoreGroup", relationship_identifier="group_member", cardinality=RelationshipCardinality.MANY
)

ESTIMATE = QueryEstimate(
    mode=EstimateMode.COUNTED_FIRST_STEP,
    statistics=StatisticsPointer(
        version=3,
        branch="main",
        computed_at=datetime(2026, 10, 7, 4, 12, 30, tzinfo=UTC),
        schema_hash="9f3c0a7e5d1b",
        kinds=("TestPerson", "TestElectricCar", "TestGazCar", "BuiltinTag"),
    ),
    estimates={
        "TestPerson": FieldEstimate(
            field=PERSON_FIELD,
            expected=CostFigures(nodes=3, resolver_calls=1, database_rows=9),
            worst_case=CostFigures(nodes=3, resolver_calls=1, database_rows=9),
            source=EstimateSource.COUNTED,
            worst_case_is_bound=True,
            reason=None,
        ),
        "TestPerson/cars": FieldEstimate(
            field=CARS_FIELD,
            expected=CostFigures(nodes=7, resolver_calls=3, database_rows=21),
            worst_case=CostFigures(nodes=7, resolver_calls=3, database_rows=21),
            source=EstimateSource.COUNTED,
            worst_case_is_bound=True,
            reason=None,
        ),
        "TestPerson/cars/owner": FieldEstimate(
            field=OWNER_FIELD,
            expected=None,
            worst_case=None,
            source=None,
            worst_case_is_bound=False,
            reason=EstimateReason.NO_STATISTICS,
        ),
        "TestPerson/cars/tags": FieldEstimate(
            field=TAGS_FIELD,
            expected=CostFigures(nodes=4, resolver_calls=7, database_rows=8),
            worst_case=CostFigures(nodes=11, resolver_calls=7, database_rows=22),
            source=EstimateSource.STATISTICS,
            worst_case_is_bound=True,
            reason=None,
        ),
    },
)


def _build_recorder() -> QueryCostRecorder:
    """Record a request whose recording order differs from the order of the estimation tree."""
    recorder = QueryCostRecorder()
    recorder.record_query(path=None, rows=1)
    recorder.record_query(path=ESTIMATE_FIELD_PATH, rows=2)
    recorder.record_query(path=ESTIMATE_FIELD_PATH, rows=7)

    recorder.record_query(path="TestPerson", rows=9)
    recorder.record_call(path="TestPerson", field=PERSON_FIELD, nodes=3)

    recorder.record_query(path="TestPerson/member_of_groups", rows=2)
    for _ in range(3):
        recorder.record_call(path="TestPerson/member_of_groups", field=PERSON_GROUPS_FIELD, nodes=0)

    for _ in range(7):
        recorder.record_query(path="TestPerson/cars/owner", rows=1)
        recorder.record_call(path="TestPerson/cars/owner", field=OWNER_FIELD, nodes=1)

    for nodes in (0, 2, 5):
        recorder.record_query(path="TestPerson/cars", rows=nodes * 3)
        recorder.record_call(path="TestPerson/cars", field=CARS_FIELD, nodes=nodes)

    recorder.record_query(path="TestPerson/cars/member_of_groups", rows=4)
    recorder.record_call(path="TestPerson/cars/member_of_groups", field=CAR_GROUPS_FIELD, nodes=2)

    recorder.record_query(path=None, rows=3)
    return recorder


def test_details_with_estimate_dump_to_the_response_content() -> None:
    details = build_query_cost_details(estimate=ESTIMATE, recorder=_build_recorder())

    assert details.model_dump(mode="json") == {
        "estimate_mode": "counted_first_step",
        "statistics": {"branch": "main", "computed_at": "2026-10-07T04:12:30Z", "version": 3},
        "fields": [
            {
                "path": "TestPerson",
                "kind": "TestPerson",
                "relationship_identifier": None,
                "cardinality": "many",
                "estimate": {
                    "expected": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
                    "worst_case": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
                    "worst_case_is_bound": True,
                    "source": "counted",
                    "reason": None,
                },
                "actual": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
            },
            {
                "path": "TestPerson/cars",
                "kind": "TestCar",
                "relationship_identifier": "testcar__testperson",
                "cardinality": "many",
                "estimate": {
                    "expected": {"nodes": 7, "resolver_calls": 3, "database_rows": 21},
                    "worst_case": {"nodes": 7, "resolver_calls": 3, "database_rows": 21},
                    "worst_case_is_bound": True,
                    "source": "counted",
                    "reason": None,
                },
                "actual": {"nodes": 7, "resolver_calls": 3, "database_rows": 21},
            },
            {
                "path": "TestPerson/cars/owner",
                "kind": "TestPerson",
                "relationship_identifier": "testcar__testperson",
                "cardinality": "one",
                "estimate": {
                    "expected": None,
                    "worst_case": None,
                    "worst_case_is_bound": False,
                    "source": None,
                    "reason": "no statistics",
                },
                "actual": {"nodes": 7, "resolver_calls": 7, "database_rows": 7},
            },
            {
                "path": "TestPerson/cars/tags",
                "kind": "BuiltinTag",
                "relationship_identifier": "builtintag__testcar",
                "cardinality": "many",
                "estimate": {
                    "expected": {"nodes": 4, "resolver_calls": 7, "database_rows": 8},
                    "worst_case": {"nodes": 11, "resolver_calls": 7, "database_rows": 22},
                    "worst_case_is_bound": True,
                    "source": "statistics",
                    "reason": None,
                },
                "actual": {"nodes": 0, "resolver_calls": 0, "database_rows": 0},
            },
            {
                "path": "TestPerson/member_of_groups",
                "kind": "CoreGroup",
                "relationship_identifier": "group_member",
                "cardinality": "many",
                "estimate": {
                    "expected": None,
                    "worst_case": None,
                    "worst_case_is_bound": False,
                    "source": None,
                    "reason": "no statistics",
                },
                "actual": {"nodes": 0, "resolver_calls": 3, "database_rows": 2},
            },
            {
                "path": "TestPerson/cars/member_of_groups",
                "kind": "CoreGroup",
                "relationship_identifier": "group_member",
                "cardinality": "many",
                "estimate": {
                    "expected": None,
                    "worst_case": None,
                    "worst_case_is_bound": False,
                    "source": None,
                    "reason": "no statistics",
                },
                "actual": {"nodes": 2, "resolver_calls": 1, "database_rows": 4},
            },
        ],
        "estimate_queries": {"queries": 2, "database_rows": 9},
        "unattributed": {"queries": 2, "database_rows": 4},
    }


def test_details_without_estimate_mark_every_recorded_field_without_statistics() -> None:
    details = build_query_cost_details(estimate=None, recorder=_build_recorder())

    no_statistics = {
        "expected": None,
        "worst_case": None,
        "worst_case_is_bound": False,
        "source": None,
        "reason": "no statistics",
    }
    assert details.model_dump(mode="json") == {
        "estimate_mode": "statistics_only",
        "statistics": None,
        "fields": [
            {
                "path": "TestPerson",
                "kind": "TestPerson",
                "relationship_identifier": None,
                "cardinality": "many",
                "estimate": no_statistics,
                "actual": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
            },
            {
                "path": "TestPerson/member_of_groups",
                "kind": "CoreGroup",
                "relationship_identifier": "group_member",
                "cardinality": "many",
                "estimate": no_statistics,
                "actual": {"nodes": 0, "resolver_calls": 3, "database_rows": 2},
            },
            {
                "path": "TestPerson/cars/owner",
                "kind": "TestPerson",
                "relationship_identifier": "testcar__testperson",
                "cardinality": "one",
                "estimate": no_statistics,
                "actual": {"nodes": 7, "resolver_calls": 7, "database_rows": 7},
            },
            {
                "path": "TestPerson/cars",
                "kind": "TestCar",
                "relationship_identifier": "testcar__testperson",
                "cardinality": "many",
                "estimate": no_statistics,
                "actual": {"nodes": 7, "resolver_calls": 3, "database_rows": 21},
            },
            {
                "path": "TestPerson/cars/member_of_groups",
                "kind": "CoreGroup",
                "relationship_identifier": "group_member",
                "cardinality": "many",
                "estimate": no_statistics,
                "actual": {"nodes": 2, "resolver_calls": 1, "database_rows": 4},
            },
        ],
        "estimate_queries": {"queries": 2, "database_rows": 9},
        "unattributed": {"queries": 2, "database_rows": 4},
    }


def test_details_list_tree_fields_first_then_other_recorded_fields_in_recording_order() -> None:
    recorder = QueryCostRecorder()
    recorder.record_call(path="TestPerson/member_of_groups", field=PERSON_GROUPS_FIELD, nodes=0)
    recorder.record_call(path="TestPerson/cars/tags", field=TAGS_FIELD, nodes=1)
    recorder.record_call(path="TestPerson/cars/member_of_groups", field=CAR_GROUPS_FIELD, nodes=0)
    recorder.record_call(path="TestPerson/cars", field=CARS_FIELD, nodes=2)
    recorder.record_call(path="TestPerson", field=PERSON_FIELD, nodes=1)

    details = build_query_cost_details(estimate=ESTIMATE, recorder=recorder)

    assert [field.path for field in details.fields] == [
        "TestPerson",
        "TestPerson/cars",
        "TestPerson/cars/owner",
        "TestPerson/cars/tags",
        "TestPerson/member_of_groups",
        "TestPerson/cars/member_of_groups",
    ]


def test_details_reject_rows_recorded_for_a_field_without_a_resolver_call() -> None:
    recorder = QueryCostRecorder()
    recorder.record_query(path="TestPerson/cars", rows=4)

    with pytest.raises(
        ValueError,
        match=r"^Database rows were recorded for the field 'TestPerson/cars' without a resolver call$",
    ):
        build_query_cost_details(estimate=None, recorder=recorder)


@dataclass
class DetailsRequestedTestCase:
    name: str
    headers: dict[str, str]
    expected: bool


DETAILS_REQUESTED_TEST_CASES: list[DetailsRequestedTestCase] = [
    DetailsRequestedTestCase(name="details_value", headers={"X-Infrahub-Query-Cost": "details"}, expected=True),
    DetailsRequestedTestCase(
        name="value_compared_without_case", headers={"x-infrahub-query-cost": "DeTaiLs"}, expected=True
    ),
    DetailsRequestedTestCase(name="other_value", headers={"X-Infrahub-Query-Cost": "summary"}, expected=False),
    DetailsRequestedTestCase(name="empty_value", headers={"X-Infrahub-Query-Cost": ""}, expected=False),
    DetailsRequestedTestCase(name="header_absent", headers={"X-Infrahub-Admission": "details"}, expected=False),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DETAILS_REQUESTED_TEST_CASES])
def test_query_cost_details_requested(test_case: DetailsRequestedTestCase) -> None:
    assert query_cost_details_requested(headers=Headers(headers=test_case.headers)) is test_case.expected
