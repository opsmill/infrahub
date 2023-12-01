from typing import List

import ujson

from infrahub_sdk.node import InfrahubNode

from .interface import ExporterInterface


class JSONExporter(ExporterInterface):
    async def export(self, nodes: List[InfrahubNode]) -> str:
        ordered_nodes = sorted(nodes, key=lambda n: n.get_kind())
        export_data = []
        for node in ordered_nodes:
            graphql_data = node.get_raw_graphql_data()
            if graphql_data:
                graphql_data["relationships"] = await node.get_relationships()
                export_data.append(graphql_data)
        return ujson.dumps(export_data)
