from graphene.types import Scalar
from graphql.language import ast


class Any(Scalar):
    """DateTime Scalar Description"""

    @staticmethod
    def serialize(dt):
        return "in_serialize"

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            return "in_parse_literal"

    @staticmethod
    def parse_value(value):
        return "in_parse_value"
