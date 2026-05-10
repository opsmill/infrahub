from unittest.mock import MagicMock

import pytest
from graphql import GraphQLError

from infrahub.graphql.resolvers.resolver import default_paginated_list_resolver


@pytest.mark.anyio
async def test_negative_limit_raises() -> None:
    info = MagicMock()
    with pytest.raises(GraphQLError, match="limit"):
        await default_paginated_list_resolver(root=None, info=info, limit=-1)


@pytest.mark.anyio
async def test_negative_offset_raises() -> None:
    info = MagicMock()
    with pytest.raises(GraphQLError, match="offset"):
        await default_paginated_list_resolver(root=None, info=info, offset=-1)
