from __future__ import annotations

from typing import ClassVar

from infrahub.core.query.node_query import NodeIDQuery


class ComputedAttributeNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "ComputedAttributeFetchNodeIDs"
