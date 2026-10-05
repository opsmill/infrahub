from __future__ import annotations

from dataclasses import dataclass

import graphene
import pytest
from graphql import GraphQLInputObjectType, Undefined

from infrahub.graphql.mutations.attribute import NumberAttributeCreate, NumberAttributeUpdate


@dataclass(frozen=True)
class NumberInputCase:
    name: str
    input_type: type[graphene.InputObjectType]


NUMBER_INPUT_CASES = [
    NumberInputCase(name="create", input_type=NumberAttributeCreate),
    NumberInputCase(name="update", input_type=NumberAttributeUpdate),
]


def _echo_schema(input_type: type[graphene.InputObjectType]) -> graphene.Schema:
    class Query(graphene.ObjectType):
        echo = graphene.String(data=input_type(required=True))

        @staticmethod
        def resolve_echo(root: object, info: object, data: graphene.InputObjectType) -> str:  # noqa: ARG004
            return repr(sorted(dict(data).items()))

    return graphene.Schema(query=Query, auto_camelcase=False)


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in NUMBER_INPUT_CASES])
def test_from_pool_has_no_default(case: NumberInputCase) -> None:
    schema = _echo_schema(input_type=case.input_type)

    field = schema.graphql_schema.get_type(case.input_type._meta.name)
    assert isinstance(field, GraphQLInputObjectType)
    assert field.fields["from_pool"].default_value is Undefined


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in NUMBER_INPUT_CASES])
def test_an_omitted_from_pool_stays_out_of_the_payload(case: NumberInputCase) -> None:
    schema = _echo_schema(input_type=case.input_type)

    omitted = schema.execute("{ echo(data: { value: 5 }) }")
    null = schema.execute("{ echo(data: { value: 5, from_pool: null }) }")

    assert omitted.errors is None
    assert null.errors is None
    assert omitted.data == {"echo": "[('value', 5)]"}
    assert null.data == {"echo": "[('from_pool', None), ('value', 5)]"}
