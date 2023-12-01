import asyncio
from collections import defaultdict
from typing import Dict, List

from infrahub_sdk.node.model import InfrahubNodeBase


class NodeDeduplicator:
    async def deduplicate(self, nodes: List[InfrahubNodeBase]) -> List[InfrahubNodeBase]:
        nodes_by_id: Dict[str, List[InfrahubNodeBase]] = defaultdict(list)
        for node in nodes:
            nodes_by_id[node.id].append(node)

        deduplicated = []
        tasks = []
        for nodes_with_same_id in nodes_by_id.values():
            if len(nodes_with_same_id) == 1:
                deduplicated.append(nodes_with_same_id[0])
                continue

            tasks.append(self._select_node(nodes_with_same_id))
        unique_nodes = await asyncio.gather(*tasks)
        deduplicated.extend(unique_nodes)

        return deduplicated

    async def _select_node(self, nodes: List[InfrahubNodeBase]) -> InfrahubNodeBase:
        # TODO: better selection, if necessary
        return nodes[0]
