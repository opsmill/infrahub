from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from infrahub_sdk.exceptions import GraphQLError

import pyarrow.json as pa_json
import ujson
from rich.console import Console
from rich.progress import Progress

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter

from .interface import ImporterInterface


class LineDelimitedJSONImporter(ImporterInterface):
    def __init__(
        self,
        client: InfrahubClient,
        topological_sorter: InfrahubSchemaTopologicalSorter,
        continue_on_error: bool = False,
        console: Optional[Console] = None,
    ):
        self.client = client
        self.topological_sorter = topological_sorter
        self.continue_on_error = continue_on_error
        self.console = console

    async def import_data(
        self,
        import_directory: Path,
        branch: str,
    ) -> None:
        node_file = import_directory / Path("nodes.json")
        if not node_file.exists():
            raise FileNotFoundError(f"{node_file.absolute()} does not exist")
        if self.console:
            self.console.print("Reading import directory", end="...")
        table = pa_json.read_json(node_file.absolute())
        if self.console:
            self.console.print("[green]done")

        if self.console:
            self.console.print("Ordering schema for import", end="...")
        ordered_schema_names = await self.topological_sorter.get_sorted_node_schema(self.client.schema, branch=branch)
        if self.console:
            self.console.print("[green]done")

        import_nodes_by_kind = defaultdict(list)
        for graphql_data, kind, timestamp_raw in zip(
            table.column("graphql_json"), table.column("kind"), table.column("timestamp")
        ):
            timestamp = datetime.fromisoformat(str(timestamp_raw))
            node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
            import_nodes_by_kind[str(kind)].append(node)

        if self.console:
            self.console.print("Building import batches", end="...")
        node_count = 0
        save_batches = []
        for kind in ordered_schema_names:
            schema_import_nodes = import_nodes_by_kind[kind]
            if not schema_import_nodes:
                continue
            save_batch = await self.client.create_batch(return_exceptions=True)
            node_count += len(schema_import_nodes)
            for node in schema_import_nodes:
                save_batch.add(task=node.upsert, node=node, at=timestamp)
            save_batches.append(save_batch)
        if self.console:
            self.console.print("[green]done")

        if self.console:
            progress = Progress()
            progress.start()
            progress_task = progress.add_task("Executing batches...", total=node_count)
        exceptions = []

        for save_batch in save_batches:
            async for result in save_batch.execute():
                if self.console:
                    progress.update(progress_task, advance=1)
                if isinstance(result, Exception):
                    if not self.continue_on_error:
                        if self.console:
                            progress.stop()
                        raise result
                    if isinstance(result, GraphQLError):
                        error_name = type(result).__name__
                        error_msgs = [err["message"] for err in result.errors]
                        error_str = f"{error_name}: {error_msgs}"
                    else:
                        error_str = str(result)
                    exceptions.append(error_str)
        if self.console:
            progress.stop()

        if not exceptions:
            return
        if self.console:
            self.console.print(f"[red]{len(exceptions)} nodes failed to import")
            for exception_str in exceptions:
                self.console.print(f"[red]{exception_str}")
