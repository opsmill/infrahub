from typing import Any

from graphene import Scalar
from graphene.types.generic import GenericScalar
from graphene.types.scalars import MAX_INT, MIN_INT
from graphql.language.ast import (
    BooleanValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    ObjectValueNode,
    StringValueNode,
    ValueNode,
    VariableNode,
)

from infrahub.exceptions import ValidationError


class NonNegativeInt(Scalar):
    """A GraphQL scalar that validates non-negative integer values.

    It accepts integers >= 0 (and whole-number floats, matching the built-in Int
    scalar) and rejects negative, fractional or non-integer values by raising
    ValidationError, which the executor wraps with the argument type name and
    source location.
    """

    @staticmethod
    def serialize(value: int | None) -> int | None:
        """Serialize the value for output."""
        return NonNegativeInt._validate(value)

    @staticmethod
    def parse_value(value: Any) -> int | None:
        """Parse a value supplied through query variables."""
        return NonNegativeInt._validate(value)

    @staticmethod
    def parse_literal(node: ValueNode, _variables: dict[str, Any] | None = None) -> int | None:
        """Parse a value supplied as an inline literal in the query.

        Raises:
            ValidationError: If the literal is not a non-negative integer.

        """
        if isinstance(node, IntValueNode):
            return NonNegativeInt._validate(int(node.value))
        raise ValidationError("Value must be a non-negative integer")

    @staticmethod
    def _validate(value: Any) -> int | None:
        """Validate that the value is a non-negative integer.

        Booleans, strings and fractional floats are rejected so that variable
        inputs are validated as strictly as inline integer literals.

        Raises:
            ValidationError: If the value is not a non-negative integer.

        """
        if value is None:
            return None

        is_integer = isinstance(value, int) and not isinstance(value, bool)
        is_whole_float = isinstance(value, float) and value.is_integer()
        if not (is_integer or is_whole_float):
            raise ValidationError("Value must be a non-negative integer")

        value = int(value)
        if value < 0:
            raise ValidationError("Value must be a non-negative integer")

        return value


class FixedGenericScalar(GenericScalar):
    """GenericScalar with correct variable substitution in parse_literal.

    graphene's GenericScalar.parse_literal does not forward _variables to
    recursive calls, so $variable references inside a nested object or list
    resolve to None instead of their supplied values.
    """

    @staticmethod
    def parse_literal(ast: ValueNode, _variables: dict[str, Any] | None = None) -> Any:
        result: Any = None
        if isinstance(ast, (StringValueNode, BooleanValueNode)):
            result = ast.value
        elif isinstance(ast, IntValueNode):
            num = int(ast.value)
            if MIN_INT <= num <= MAX_INT:
                result = num
        elif isinstance(ast, FloatValueNode):
            result = float(ast.value)
        elif isinstance(ast, ListValueNode):
            result = [FixedGenericScalar.parse_literal(v, _variables) for v in ast.values]
        elif isinstance(ast, ObjectValueNode):
            result = {
                field.name.value: FixedGenericScalar.parse_literal(field.value, _variables) for field in ast.fields
            }
        elif isinstance(ast, VariableNode) and _variables is not None:
            result = _variables.get(ast.name.value)
        return result
