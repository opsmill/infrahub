from collections.abc import Sequence
from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def create_chain(
    db: InfrahubDatabase, branch: Branch, kinds: Sequence[str], relationship_name: str, name_prefix: str
) -> list[Node]:
    """Create one node per kind in order, each linked to the node created before it through `relationship_name`."""
    chain: list[Node] = []
    for position, kind in enumerate(kinds):
        links = {relationship_name: chain[-1]} if chain else {}
        chain.append(await create_node(db=db, branch=branch, kind=kind, name=f"{name_prefix}-{position}", **links))
    return chain
