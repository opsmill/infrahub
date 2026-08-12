from __future__ import annotations

import math

from graphene.types.scalars import MAX_INT, MIN_INT
from graphql.language.ast import (
    BooleanValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    NameNode,
    ObjectFieldNode,
    ObjectValueNode,
    StringValueNode,
    VariableNode,
)

from infrahub.graphql.scalars import FixedGenericScalar


class TestFixedGenericScalarParseLiteral:
    def test_string(self) -> None:
        assert FixedGenericScalar.parse_literal(StringValueNode(value="hello")) == "hello"

    def test_boolean_true(self) -> None:
        assert FixedGenericScalar.parse_literal(BooleanValueNode(value=True)) is True

    def test_boolean_false(self) -> None:
        assert FixedGenericScalar.parse_literal(BooleanValueNode(value=False)) is False

    def test_int_in_range(self) -> None:
        assert FixedGenericScalar.parse_literal(IntValueNode(value="42")) == 42

    def test_int_at_min_boundary(self) -> None:
        assert FixedGenericScalar.parse_literal(IntValueNode(value=str(MIN_INT))) == MIN_INT

    def test_int_at_max_boundary(self) -> None:
        assert FixedGenericScalar.parse_literal(IntValueNode(value=str(MAX_INT))) == MAX_INT

    def test_int_out_of_range_returns_none(self) -> None:
        assert FixedGenericScalar.parse_literal(IntValueNode(value=str(MAX_INT + 1))) is None

    def test_float(self) -> None:
        assert FixedGenericScalar.parse_literal(FloatValueNode(value=str(math.pi))) == math.pi

    def test_list_of_strings(self) -> None:
        ast = ListValueNode(values=[StringValueNode(value="a"), StringValueNode(value="b")])
        assert FixedGenericScalar.parse_literal(ast) == ["a", "b"]

    def test_list_of_mixed_types(self) -> None:
        ast = ListValueNode(values=[StringValueNode(value="x"), BooleanValueNode(value=True), IntValueNode(value="7")])
        assert FixedGenericScalar.parse_literal(ast) == ["x", True, 7]

    def test_object(self) -> None:
        ast = ObjectValueNode(
            fields=[
                ObjectFieldNode(name=NameNode(value="name"), value=StringValueNode(value="alice")),
                ObjectFieldNode(name=NameNode(value="active"), value=BooleanValueNode(value=True)),
            ]
        )
        assert FixedGenericScalar.parse_literal(ast) == {"name": "alice", "active": True}

    def test_variable_with_variables_dict(self) -> None:
        ast = VariableNode(name=NameNode(value="myVar"))
        assert FixedGenericScalar.parse_literal(ast, _variables={"myVar": "resolved"}) == "resolved"

    def test_variable_without_variables_dict_returns_none(self) -> None:
        ast = VariableNode(name=NameNode(value="myVar"))
        assert FixedGenericScalar.parse_literal(ast, _variables=None) is None

    def test_list_with_variable_substitution(self) -> None:
        ast = ListValueNode(values=[StringValueNode(value="static"), VariableNode(name=NameNode(value="dynamic"))])
        assert FixedGenericScalar.parse_literal(ast, _variables={"dynamic": "value"}) == ["static", "value"]

    def test_object_with_variable_substitution(self) -> None:
        ast = ObjectValueNode(
            fields=[
                ObjectFieldNode(name=NameNode(value="key"), value=VariableNode(name=NameNode(value="val"))),
            ]
        )
        assert FixedGenericScalar.parse_literal(ast, _variables={"val": 99}) == {"key": 99}
