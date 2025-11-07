from graphene import Scalar
from graphql import GraphQLError, language

class NonNegativeInt(Scalar):
	@staticmethod
	def serialize(value):
	  return NonNegativeInt._validate(value)

	@staticmethod
	def parse_value(value):
	  return NonNegativeInt._validate(value)

	@staticmethod
	def parse_literal(node):
	  if isinstance(node, language.ast.IntValueNode):
	      return NonNegativeInt._validate(int(node.value))
	  raise GraphQLError("Value must be a non-negative integer")

	@staticmethod
	def _validate(value):
	  if value is None:
	      return None
	  value = int(value)
	  if value < 0:
	      raise GraphQLError("Value must be a non-negative integer")
	  return value
