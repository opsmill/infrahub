from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from graphql import parse_value

from infrahub.graphql.analyzer import GraphQLArgument


def _argument(graphql_value: str) -> GraphQLArgument:
    return GraphQLArgument(name="filter", value_node=parse_value(graphql_value))


@dataclass(frozen=True, kw_only=True)
class ValueCase:
    name: str
    graphql_value: str
    value: Any
    kind: str
    is_variable: bool = False


VALUE_CASES = [
    ValueCase(name="a_string", graphql_value='"aggregate"', value="aggregate", kind="string_value"),
    ValueCase(name="an_integer", graphql_value="5", value=5, kind="int_value"),
    ValueCase(name="a_float", graphql_value="1.5", value=1.5, kind="float_value"),
    ValueCase(name="a_boolean", graphql_value="true", value=True, kind="boolean_value"),
    ValueCase(name="a_null", graphql_value="null", value=None, kind="null_value"),
    ValueCase(name="an_enum_reads_as_its_name", graphql_value="UPLINK", value="UPLINK", kind="enum_value"),
    ValueCase(
        name="a_variable_reads_as_its_prefixed_name",
        graphql_value="$role",
        value="$role",
        kind="variable",
        is_variable=True,
    ),
    ValueCase(name="a_list", graphql_value="[1, 2]", value=[1, 2], kind="list_value"),
    ValueCase(
        name="an_object",
        graphql_value='{ name: { value: "Accord" }, seats: 5 }',
        value={"name": {"value": "Accord"}, "seats": 5},
        kind="object_value",
    ),
]


@pytest.mark.parametrize("case", VALUE_CASES, ids=lambda case: case.name)
def test_value_and_kind_derive_from_the_value_node(case: ValueCase) -> None:
    argument = _argument(case.graphql_value)

    assert argument.value == case.value
    assert argument.kind == case.kind
    assert argument.is_variable is case.is_variable


def test_a_variable_name_drops_its_prefix() -> None:
    assert _argument("$role").as_variable_name == "role"


def test_the_fields_of_an_object_are_sorted() -> None:
    assert _argument("{ seats: 5, name: { value: 1 } }").fields == ["name", "seats"]


def test_a_value_other_than_an_object_has_no_fields() -> None:
    assert _argument("[1, 2]").fields == []
