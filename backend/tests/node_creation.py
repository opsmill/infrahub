from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def create_and_save(db: InfrahubDatabase, schema: str, branch: Branch | str | None = None, **kwargs: Any) -> Node:
    node = await Node.init(db=db, schema=schema, branch=branch)
    await node.new(db=db, **kwargs)
    await node.save(db=db)
    return node
