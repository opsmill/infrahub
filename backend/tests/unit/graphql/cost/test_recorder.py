from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.graphql.cost.constants import ESTIMATE_FIELD_PATH
from infrahub.graphql.cost.models import FieldDescription
from infrahub.graphql.cost.recorder import (
    FieldActual,
    QueryCostRecorder,
    QueryTotals,
    activate_recorder,
    count_returned_nodes,
    field_path_from_response_keys,
    get_cost_recorder,
    get_current_field,
    record_resolver_call,
    resolving_field,
)

PERSON_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
)
CARS_FIELD = FieldDescription(
    kind="TestCar", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.MANY
)
OWNER_FIELD = FieldDescription(
    kind="TestPerson", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.ONE
)


class ResolverBodyError(Exception):
    pass


BODY_ERROR_MESSAGE = "the resolver body failed"


@dataclass
class FieldPathTestCase:
    name: str
    keys: list[str | int]
    expected: str


FIELD_PATH_TEST_CASES: list[FieldPathTestCase] = [
    FieldPathTestCase(name="top_level_field", keys=["TestPerson"], expected="TestPerson"),
    FieldPathTestCase(
        name="many_then_one_relationship",
        keys=["TestPerson", "edges", 0, "node", "cars", "edges", 3, "node", "owner"],
        expected="TestPerson/cars/owner",
    ),
    FieldPathTestCase(
        name="aliases_replace_field_names",
        keys=["persons", "edges", 0, "node", "vehicles", "edges", 1, "node", "commander"],
        expected="persons/vehicles/commander",
    ),
    FieldPathTestCase(
        name="relationship_under_a_cardinality_one_peer",
        keys=["TestCar", "edges", 2, "node", "owner", "node", "cars"],
        expected="TestCar/owner/cars",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIELD_PATH_TEST_CASES])
def test_field_path_from_response_keys(test_case: FieldPathTestCase) -> None:
    assert field_path_from_response_keys(keys=test_case.keys) == test_case.expected


@dataclass
class ReturnedNodesTestCase:
    name: str
    result: dict[str, Any]
    expected: int


RETURNED_NODES_TEST_CASES: list[ReturnedNodesTestCase] = [
    ReturnedNodesTestCase(
        name="paginated_result_counts_its_edges",
        result={"edges": [{"node": {"id": "a"}}, {"node": {"id": "b"}}, {"node": {"id": "c"}}], "count": 9},
        expected=3,
    ),
    ReturnedNodesTestCase(name="paginated_result_without_edges", result={"edges": [], "count": 4}, expected=0),
    ReturnedNodesTestCase(name="single_peer_result", result={"node": {"id": "a"}, "properties": {}}, expected=1),
    ReturnedNodesTestCase(name="single_result_without_peer", result={"node": None, "properties": {}}, expected=0),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RETURNED_NODES_TEST_CASES])
def test_count_returned_nodes(test_case: ReturnedNodesTestCase) -> None:
    assert count_returned_nodes(result=test_case.result) == test_case.expected


def test_recorder_adds_calls_nodes_and_rows_for_each_path() -> None:
    recorder = QueryCostRecorder()

    recorder.record_call(path="TestPerson", field=PERSON_FIELD, nodes=3)
    recorder.record_query(path="TestPerson", rows=6)
    for nodes, rows in ((0, 1), (2, 4), (5, 10)):
        recorder.record_call(path="TestPerson/cars", field=CARS_FIELD, nodes=nodes)
        recorder.record_query(path="TestPerson/cars", rows=rows)

    assert dict(recorder.fields) == {
        "TestPerson": FieldActual(field=PERSON_FIELD, nodes=3, resolver_calls=1, database_rows=6),
        "TestPerson/cars": FieldActual(field=CARS_FIELD, nodes=7, resolver_calls=3, database_rows=15),
    }
    assert recorder.estimate_queries == QueryTotals(queries=0, database_rows=0)
    assert recorder.unattributed == QueryTotals(queries=0, database_rows=0)


def test_rows_read_for_the_estimate_go_to_the_estimate_totals() -> None:
    recorder = QueryCostRecorder()

    with activate_recorder(recorder=recorder), resolving_field(path=ESTIMATE_FIELD_PATH):
        recorder.record_query(path=get_current_field(), rows=4)
        recorder.record_query(path=get_current_field(), rows=2)

    assert recorder.estimate_queries == QueryTotals(queries=2, database_rows=6)
    assert recorder.unattributed == QueryTotals(queries=0, database_rows=0)
    assert dict(recorder.fields) == {}


def test_rows_read_outside_any_field_go_to_the_unattributed_totals() -> None:
    recorder = QueryCostRecorder()

    with activate_recorder(recorder=recorder):
        recorder.record_query(path=get_current_field(), rows=5)

    assert recorder.unattributed == QueryTotals(queries=1, database_rows=5)
    assert recorder.estimate_queries == QueryTotals(queries=0, database_rows=0)
    assert dict(recorder.fields) == {}


def test_activate_recorder_restores_the_previous_recorder() -> None:
    outer = QueryCostRecorder()
    inner = QueryCostRecorder()

    assert get_cost_recorder() is None
    with activate_recorder(recorder=outer):
        with activate_recorder(recorder=inner):
            assert get_cost_recorder() is inner
        assert get_cost_recorder() is outer

        with pytest.raises(ResolverBodyError, match=rf"^{BODY_ERROR_MESSAGE}$"), activate_recorder(recorder=inner):
            raise ResolverBodyError(BODY_ERROR_MESSAGE)
        assert get_cost_recorder() is outer
    assert get_cost_recorder() is None


def test_resolving_field_restores_the_previous_field() -> None:
    assert get_current_field() is None
    with resolving_field(path="TestPerson"):
        with resolving_field(path="TestPerson/cars"):
            assert get_current_field() == "TestPerson/cars"
        assert get_current_field() == "TestPerson"

        with (
            pytest.raises(ResolverBodyError, match=rf"^{BODY_ERROR_MESSAGE}$"),
            resolving_field(path="TestPerson/cars"),
        ):
            raise ResolverBodyError(BODY_ERROR_MESSAGE)
        assert get_current_field() == "TestPerson"
    assert get_current_field() is None


async def test_record_resolver_call_counts_the_returned_nodes_and_the_rows_read_by_the_body() -> None:
    recorder = QueryCostRecorder()
    paths_seen_by_body: list[str | None] = []

    async def body() -> dict[str, Any]:
        paths_seen_by_body.append(get_current_field())
        recorder.record_query(path=get_current_field(), rows=3)
        return {"edges": [{"node": {"id": "a"}}, {"node": {"id": "b"}}]}

    with activate_recorder(recorder=recorder), resolving_field(path="TestPerson"):
        result = await record_resolver_call(recorder=recorder, path="TestPerson/cars", field=CARS_FIELD, body=body())
        assert get_current_field() == "TestPerson"

    assert result == {"edges": [{"node": {"id": "a"}}, {"node": {"id": "b"}}]}
    assert paths_seen_by_body == ["TestPerson/cars"]
    assert dict(recorder.fields) == {
        "TestPerson/cars": FieldActual(field=CARS_FIELD, nodes=2, resolver_calls=1, database_rows=3),
    }


async def test_record_resolver_call_records_a_call_with_no_nodes_when_the_body_raises() -> None:
    recorder = QueryCostRecorder()

    async def body() -> dict[str, Any]:
        recorder.record_query(path=get_current_field(), rows=1)
        raise ResolverBodyError(BODY_ERROR_MESSAGE)

    with activate_recorder(recorder=recorder):
        with pytest.raises(ResolverBodyError, match=rf"^{BODY_ERROR_MESSAGE}$"):
            await record_resolver_call(recorder=recorder, path="TestPerson/cars/owner", field=OWNER_FIELD, body=body())
        assert get_current_field() is None

    assert dict(recorder.fields) == {
        "TestPerson/cars/owner": FieldActual(field=OWNER_FIELD, nodes=0, resolver_calls=1, database_rows=1),
    }
