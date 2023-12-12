from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyarrow.json as pa_json
import ujson

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter

from .interface import ImporterInterface


class LineDelimitedJSONImporter(ImporterInterface):
    def __init__(self, client: InfrahubClient, topological_sorter: InfrahubSchemaTopologicalSorter):
        self.client = client
        self.topological_sorter = topological_sorter

    async def import_data(
        self,
        import_directory: Path,
        branch: str,
    ) -> None:
        node_file = import_directory / Path("nodes.json")
        if not node_file.exists():
            raise FileNotFoundError(f"{node_file.absolute()} does not exist")
        table = pa_json.read_json(node_file.absolute())

        from time import time

        start_time = time()
        print("ordering schema", end="...")
        ordered_schema_names = await self.topological_sorter.get_sorted_node_schema(self.client.schema, branch=branch)
        print(time() - start_time)

        print("building ID batch", end="...")
        existing_ids_for_kind = defaultdict(set)
        existing_ids_batch = await self.client.create_batch()
        for kind in table.column("kind"):
            kind_str = str(kind)
            existing_ids_batch.add(kind_str, task=self.client.all, branch=branch, include=["id"])
        print(time() - start_time)

        print("getting existing IDs", end="...")
        async for _, kind_nodes in existing_ids_batch.execute():
            for node in kind_nodes:
                existing_ids_for_kind[node.get_kind()].add(node.id)
        print(time() - start_time)

        import_nodes_by_kind = defaultdict(list)
        for graphql_data, kind, timestamp_raw in zip(
            table.column("graphql_json"), table.column("kind"), table.column("timestamp")
        ):
            timestamp = datetime.fromisoformat(str(timestamp_raw))
            node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
            import_nodes_by_kind[str(kind)].append(node)

        for kind in ordered_schema_names:
            save_batch = await self.client.create_batch()

            import_nodes = import_nodes_by_kind[kind]
            if not import_nodes:
                continue

            print(f"creating batch for {kind}", end="...")
            for node in import_nodes:
                create_required = node.id not in existing_ids_for_kind[str(kind)]
                if create_required:
                    save_batch.add(task=node.create, node=node, at=timestamp)
                else:
                    save_batch.add(task=node.update, node=node, at=timestamp, do_full_update=True)
            print(time() - start_time)

            print(f"executing batch for {len(import_nodes)} {kind} nodes", end="...")
            async for _ in save_batch.execute():
                ...
            print(time() - start_time)
