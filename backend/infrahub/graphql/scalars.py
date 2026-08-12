from typing import Any

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
