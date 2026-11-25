from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.node import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    """Create and save a node of the kind on the branch with the given attribute and relationship values."""
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node
