from typing import Any, ClassVar

from infrahub.core.graphql_query.node_id_query import NodeIDQuery


class ProfileNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "ProfileFetchNodeIDs"
    profile_id: str

    def extra_filters(self) -> dict[str, Any]:
        return {"profiles__ids": [self.profile_id]}
