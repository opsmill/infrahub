import pytest
from graphql import GraphQLError

from infrahub.graphql.resolvers.resolver import validate_offset_and_limit


def test_negative_limit_raises() -> None:
    with pytest.raises(GraphQLError, match="limit"):
        validate_offset_and_limit(offset=None, limit=-1)


def test_negative_offset_raises() -> None:
    with pytest.raises(GraphQLError, match="offset"):
        validate_offset_and_limit(offset=-1, limit=None)
