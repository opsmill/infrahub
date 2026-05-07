from __future__ import annotations

from typing import ClassVar

from infrahub.core.graphql_query.node_id_query import NodeIDQuery


class ComputedAttributeNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "ComputedAttributeFetchNodeIDs"
