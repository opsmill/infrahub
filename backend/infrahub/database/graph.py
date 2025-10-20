from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.initialization import get_root_node
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


log = get_logger()


async def validate_graph_version(db: InfrahubDatabase) -> None:
    root = await get_root_node(db=db)
    if root.graph_version != GRAPH_VERSION:
        log.warning(
            f"Expected database graph version {GRAPH_VERSION} but got {root.graph_version}, possibly 'infrahub upgrade' has not been executed"
        )
