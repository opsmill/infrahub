from typing import Type

from pydantic import Field

from infrahub.core.node.standard import StandardNode
from infrahub.core.query.standard_node import RootNodeCreateQuery, StandardNodeQuery


class Root(StandardNode):
    graph_version: int = Field(0, description="Internal Version of the graph.")

    _query: Type[StandardNodeQuery] = RootNodeCreateQuery
