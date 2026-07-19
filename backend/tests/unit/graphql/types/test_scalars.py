from __future__ import annotations

import math

import pytest
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

from infrahub.exceptions import ValidationError
from infrahub.graphql.scalars import FixedGenericScalar, NonNegativeInt


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


class TestNonNegativeIntParseValue:
    def test_positive_integer(self) -> None:
        assert NonNegativeInt.parse_value(5) == 5

    def test_zero(self) -> None:
        assert NonNegativeInt.parse_value(0) == 0

    def test_whole_float(self) -> None:
        assert NonNegativeInt.parse_value(2.0) == 2

    def test_none(self) -> None:
        assert NonNegativeInt.parse_value(None) is None

    def test_negative_integer(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_value(-1)

    def test_fractional_float(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_value(1.9)

    def test_boolean(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_value(True)

    def test_numeric_string(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_value("1")


class TestNonNegativeIntParseLiteral:
    def test_positive_integer_literal(self) -> None:
        assert NonNegativeInt.parse_literal(IntValueNode(value="5")) == 5

    def test_zero_literal(self) -> None:
        assert NonNegativeInt.parse_literal(IntValueNode(value="0")) == 0

    def test_negative_integer_literal(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_literal(IntValueNode(value="-1"))

    def test_non_integer_literal(self) -> None:
        with pytest.raises(ValidationError, match=r"^Value must be a non-negative integer$"):
            NonNegativeInt.parse_literal(StringValueNode(value="5"))

    def test_accepts_variables_argument(self) -> None:
        assert NonNegativeInt.parse_literal(IntValueNode(value="7"), _variables={"foo": "bar"}) == 7
