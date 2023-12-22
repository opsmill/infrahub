from collections import defaultdict
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow.json as pa_json
import ujson
from rich.console import Console
from rich.progress import Progress

from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.node import InfrahubNode, RelatedNode, RelationshipManager
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
            self.console.print("Analyzing import", end="...")
        import_nodes_by_kind = defaultdict(list)
        for graphql_data, kind in zip(table.column("graphql_json"), table.column("kind")):
            node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
            import_nodes_by_kind[str(kind)].append(node)
        if self.console:
            self.console.print("[green]done")

        if self.console:
            self.console.print("Retrieving schema", end="...")
        schemas = [await self.client.schema.get(kind=kind, branch=branch) for kind in import_nodes_by_kind]
        schemas_by_kind = {schema.kind: schema for schema in schemas}
        if self.console:
            self.console.print("[green]done")

        if self.console:
            self.console.print("Extracting optional relationships from nodes", end="...")
        optional_relationships_by_node: Dict[str, Dict[str, Any]] = defaultdict(dict)
        for kind, nodes in import_nodes_by_kind.items():
            optional_relationship_names = [
                relationship_schema.name
                for relationship_schema in schemas_by_kind[kind].relationships
                if relationship_schema.optional
            ]
            for node in nodes:
                for relationship_name in optional_relationship_names:
                    relationship_value = getattr(node, relationship_name)
                    if isinstance(relationship_value, RelationshipManager):
                        if relationship_value.peer_ids:
                            optional_relationships_by_node[node.id][relationship_name] = relationship_value
                            setattr(node, relationship_name, None)
                    elif isinstance(relationship_value, RelatedNode):
                        if relationship_value.id:
                            optional_relationships_by_node[node.id][relationship_name] = relationship_value
                            setattr(node, relationship_name, None)
        if self.console:
            self.console.print("[green]done")

        if self.console:
            self.console.print("Ordering schema for import", end="...")
        ordered_schema_names = await self.topological_sorter.get_sorted_node_schema(schemas)
        if self.console:
            self.console.print("[green]done")

        right_now = datetime.now(timezone.utc).astimezone()
        if self.console:
            self.console.print("Building import batches", end="...")
        save_batch = await self.client.create_batch(return_exceptions=True)
        for group in ordered_schema_names:
            for kind in group:
                schema_import_nodes = import_nodes_by_kind[kind]
                if not schema_import_nodes:
                    continue
                for node in schema_import_nodes:
                    save_batch.add(task=node.create, node=node, at=right_now, allow_update=True)
        if self.console:
            self.console.print("[green]done")

        await self.execute_batches([save_batch], "Creating and/or updating nodes")

        if not optional_relationships_by_node:
            return

        all_nodes = chain(*[nodes for nodes in import_nodes_by_kind.values()])
        update_batch = await self.client.create_batch(return_exceptions=True)
        for node in all_nodes:
            if node.id not in optional_relationships_by_node:
                continue
            for relationship_attr, relationship_value in optional_relationships_by_node[node.id].items():
                setattr(node, relationship_attr, relationship_value)
            update_batch.add(task=node.update, node=node, at=right_now)
        await self.execute_batches([update_batch], "Adding optional relationships to nodes")

    async def execute_batches(
        self, save_batches: List[InfrahubBatch], progress_bar_message: str = "Executing batches"
    ) -> None:
        if self.console:
            task_count = sum([batch.num_tasks for batch in save_batches])
            progress = Progress()
            progress.start()
            progress_task = progress.add_task(f"{progress_bar_message}...", total=task_count)
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
