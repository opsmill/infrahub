from typing import Any

from graphene import Scalar
from graphql import language

from infrahub.exceptions import ValidationError


class NonNegativeInt(Scalar):
    """A GraphQL scalar type that validates non-negative integer values.

    This scalar ensures that values are integers >= 0. It accepts None (null in GraphQL)
    and rejects negative integers by raising ValidationError.
    """

    @staticmethod
    def serialize(value: int | None) -> int | None:
        """Serialize the value for output.

        Args:
           value: The value to serialize.

        Returns:
           The validated non-negative integer or None.

        Raises:
           ValidationError: If the value is negative.
        """

        return NonNegativeInt._validate(value)

    @staticmethod
    def parse_value(value: Any) -> int | None:
        """Parse a value from variables.

        Args:
           value: The input value from GraphQL variables.

        Returns:
           The validated non-negative integer or None.

        Raises:
           ValidationError: If the value is negative or cannot be converted to int.
        """

        return NonNegativeInt._validate(value)

    @staticmethod
    def parse_literal(node: language.ast.ValueNode) -> int | None:
        """Parse a value from an AST literal node.

        Args:
           node: The AST node representing the literal value.

        Returns:
           The validated non-negative integer or None.

        Raises:
           ValidationError: If the node is not an IntValueNode or the value is negative.
        """

        if isinstance(node, language.ast.IntValueNode):
            return NonNegativeInt._validate(int(node.value))

        raise ValidationError("Value must be a non-negative integer")

    @staticmethod
    def _validate(value: Any) -> int | None:
        """Validate that the value is a non-negative integer.

        Args:
           value: The value to validate.

        Returns:
           The validated non-negative integer or None if the input is None.

        Raises:
           ValidationError: If the value is negative or cannot be converted to int.
        """

        if value is None:
            return None

        try:
            value = int(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError("Value must be a non-negative integer") from exc

        if value < 0:
            raise ValidationError("Value must be a non-negative integer")

        return value
