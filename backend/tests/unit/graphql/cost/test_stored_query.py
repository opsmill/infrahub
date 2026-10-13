from __future__ import annotations

from datetime import UTC, datetime

from infrahub.core.constants import GraphQLQueryCostLevel, RelationshipCardinality
from infrahub.graphql.cost.constants import NO_STATISTICS_REASON
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
from infrahub.graphql.cost.stored_query import StoredQueryCost, classify_query_estimate

POINTER = StatisticsPointer(
    version=4,
    branch="main",
    computed_at=datetime(2026, 10, 11, 4, 12, 30, tzinfo=UTC),
    schema_hash="9f3c0a7e5d1b",
    kinds=("TestPerson", "TestCar"),
)
PERSON_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
)
CARS_FIELD = FieldDescription(
    kind="TestCar", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.MANY
)
TAGS_FIELD = FieldDescription(
    kind="BuiltinTag", relationship_identifier="builtintag__testcar", cardinality=RelationshipCardinality.MANY
)
OWNER_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.ONE
)


def _estimated(field: FieldDescription, expected_rows: int, worst_case_rows: int) -> FieldEstimate:
    return FieldEstimate(
        field=field,
        expected=CostFigures(nodes=expected_rows // 3, resolver_calls=1, database_rows=expected_rows),
        worst_case=CostFigures(nodes=worst_case_rows // 3, resolver_calls=2, database_rows=worst_case_rows),
        source=EstimateSource.STATISTICS,
        worst_case_is_bound=True,
        reason=None,
    )


def _without_statistics(field: FieldDescription) -> FieldEstimate:
    return FieldEstimate(
        field=field,
        expected=None,
        worst_case=None,
        source=None,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
    )


QUERY_ESTIMATE = QueryEstimate(
    mode=EstimateMode.STATISTICS_ONLY,
    statistics=POINTER,
    estimates={
        "TestPerson": _estimated(PERSON_FIELD, expected_rows=30, worst_case_rows=30),
        "TestPerson/cars": _estimated(CARS_FIELD, expected_rows=90, worst_case_rows=600),
        "TestPerson/cars/tags": _estimated(TAGS_FIELD, expected_rows=120, worst_case_rows=300),
        "TestPerson/cars/owner": _without_statistics(OWNER_FIELD),
    },
)


def test_level_is_high_when_the_worst_case_rows_are_above_the_limit() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=929)

    assert cost.level == GraphQLQueryCostLevel.HIGH
    assert cost.reason is None
    assert cost.high_cost_database_rows == 929
    assert cost.expected is not None
    assert cost.expected.database_rows == 240
    assert cost.worst_case is not None
    assert cost.worst_case.database_rows == 930
    assert cost.worst_case.resolver_calls == 6
    assert cost.fields_without_estimate == 1
    assert cost.statistics_computed_at == POINTER.computed_at
    assert cost.statistics_version == 4


def test_level_is_low_when_the_worst_case_rows_are_not_above_the_limit() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=930)

    assert cost.level == GraphQLQueryCostLevel.LOW


def test_costliest_fields_are_the_three_with_the_most_worst_case_rows() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=930)

    assert [
        (field.path, field.expected_database_rows, field.worst_case_database_rows) for field in cost.costliest_fields
    ] == [
        ("TestPerson/cars", 90, 600),
        ("TestPerson/cars/tags", 120, 300),
        ("TestPerson", 30, 30),
    ]


def test_level_is_unknown_without_statistics() -> None:
    query_estimate = QueryEstimate(
        mode=EstimateMode.STATISTICS_ONLY,
        statistics=None,
        estimates={"TestPerson": _without_statistics(PERSON_FIELD)},
    )

    cost = classify_query_estimate(query_estimate=query_estimate, high_cost_database_rows=10)

    assert cost.level == GraphQLQueryCostLevel.UNKNOWN
    assert cost.reason == NO_STATISTICS_REASON
    assert cost.expected is None
    assert cost.worst_case is None
    assert cost.fields_without_estimate == 1


def test_level_is_unknown_when_no_field_has_an_estimate() -> None:
    query_estimate = QueryEstimate(
        mode=EstimateMode.STATISTICS_ONLY,
        statistics=POINTER,
        estimates={"TestPerson": _without_statistics(PERSON_FIELD)},
    )

    cost = classify_query_estimate(query_estimate=query_estimate, high_cost_database_rows=10)

    assert cost.level == GraphQLQueryCostLevel.UNKNOWN
    assert cost.reason == NO_STATISTICS_REASON
    assert cost.statistics_version == 4


def test_same_estimate_ignores_the_statistics_that_computed_it() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=930)
    stored = cost.model_copy(
        update={"statistics_version": 5, "statistics_computed_at": datetime(2026, 10, 12, 4, 0, tzinfo=UTC)}
    ).model_dump(mode="json")

    assert cost.same_estimate_as(stored)


def test_same_estimate_compares_the_level_and_the_figures() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=930)
    higher_limit = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=10_000)

    assert not cost.same_estimate_as(higher_limit.model_dump(mode="json"))
    assert not cost.same_estimate_as(None)
    assert not cost.same_estimate_as({"level": "high"})


def test_stored_value_is_json() -> None:
    cost = classify_query_estimate(query_estimate=QUERY_ESTIMATE, high_cost_database_rows=929)

    stored = cost.model_dump(mode="json")

    assert stored["level"] == "high"
    assert stored["statistics_computed_at"] == "2026-10-11T04:12:30Z"
    assert StoredQueryCost.model_validate(stored) == cost
