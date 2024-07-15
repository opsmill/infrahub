from pydantic import Field

from infrahub.core.node.standard import StandardNode
from infrahub.core.query.standard_node import RootNodeCreateQuery, StandardNodeQuery


class Root(StandardNode):
    graph_version: int = Field(0, description="Internal Version of the graph.")
    default_branch: str = Field(..., description="The name of the default branch")

    _query: type[StandardNodeQuery] = RootNodeCreateQuery
