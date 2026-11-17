from typing import Any, ClassVar

from infrahub.core.graphql_query.node_id_query import NodeIDQuery


class ProfileNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "ProfileFetchNodeIDs"
    # Each page evaluates the profile filter over every linked node again, so a few large pages cost less.
    page_size: ClassVar[int] = 5000
    profile_id: str

    def extra_filters(self) -> dict[str, Any]:
        return {"profiles__ids": [self.profile_id]}
