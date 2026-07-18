from typing import ClassVar

from infrahub.core.graphql_query.node_id_query import NodeIDQuery


class HFIDNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "HFIDFetchNodeIDs"
