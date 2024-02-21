from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Mapping, Optional, Sequence

import pyarrow.json as pa_json
import ujson
from rich.console import Console
from rich.progress import Progress

from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.node import InfrahubNode, RelatedNode, RelationshipManager
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter

from ..exceptions import TransferFileNotFoundError
from .interface import ImporterInterface

if TYPE_CHECKING:
    from infrahub_sdk.schema import NodeSchema


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
        self.all_nodes: List[InfrahubNode] = []
        self.schemas_by_kind: Mapping[str, NodeSchema] = {}
        self.optional_relationships_by_node: Dict[str, Dict[str, Any]] = defaultdict(dict)

    @contextmanager
    def wrapped_task_output(self, start: str, end: str = "[green]done") -> Generator:
        if self.console:
            self.console.print(f"{start}", end="...")
        yield
        if self.console:
            self.console.print(f"{end}")

    async def import_data(self, import_directory: Path, branch: str) -> None:
        node_file = import_directory / "nodes.json"
        if not node_file.exists():
            raise TransferFileNotFoundError(f"{node_file.absolute()} does not exist")
        with self.wrapped_task_output("Reading import directory"):
            table = pa_json.read_json(node_file.absolute())

        with self.wrapped_task_output("Analyzing import"):
            import_nodes_by_kind = defaultdict(list)
            for graphql_data, kind in zip(table.column("graphql_json"), table.column("kind")):
                node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
                import_nodes_by_kind[str(kind)].append(node)
                self.all_nodes.append(node)

        schema_batch = await self.client.create_batch()
        for kind in import_nodes_by_kind:
            schema_batch.add(task=self.client.schema.get, kind=kind, branch=branch)
        schemas = await self.execute_batches([schema_batch], "Retrieving schema")

        self.schemas_by_kind = {schema.kind: schema for schema in schemas}

        with self.wrapped_task_output("Ordering schema for import"):
            ordered_schema_names = await self.topological_sorter.get_sorted_node_schema(schemas)

        with self.wrapped_task_output("Preparing nodes for import"):
            await self.remove_and_store_optional_relationships()

        right_now = datetime.now(timezone.utc).astimezone()
        with self.wrapped_task_output("Building import batches"):
            save_batch = await self.client.create_batch(return_exceptions=True)
            for group in ordered_schema_names:
                for kind in group:
                    schema_import_nodes = import_nodes_by_kind[kind]
                    if not schema_import_nodes:
                        continue
                    for node in schema_import_nodes:
                        save_batch.add(task=node.create, node=node, at=right_now, allow_upsert=True)

        await self.execute_batches([save_batch], "Creating and/or updating nodes")

        if not self.optional_relationships_by_node:
            return

        await self.update_optional_relationships(at=right_now)

    async def remove_and_store_optional_relationships(self) -> None:
        for node in self.all_nodes:
            optional_relationship_names = [
                relationship_schema.name
                for relationship_schema in self.schemas_by_kind[node.get_kind()].relationships
                if relationship_schema.optional
            ]
            for relationship_name in optional_relationship_names:
                relationship_value = getattr(node, relationship_name)
                if isinstance(relationship_value, RelationshipManager):
                    if relationship_value.peer_ids:
                        self.optional_relationships_by_node[node.id][relationship_name] = relationship_value
                        setattr(node, relationship_name, None)
                elif isinstance(relationship_value, RelatedNode):
                    if relationship_value.id:
                        self.optional_relationships_by_node[node.id][relationship_name] = relationship_value
                        setattr(node, relationship_name, None)

    async def update_optional_relationships(self, at: datetime) -> None:
        update_batch = await self.client.create_batch(return_exceptions=True)
        for node in self.all_nodes:
            if node.id not in self.optional_relationships_by_node:
                continue
            for relationship_attr, relationship_value in self.optional_relationships_by_node[node.id].items():
                setattr(node, relationship_attr, relationship_value)
            update_batch.add(task=node.update, node=node, at=at)
        await self.execute_batches([update_batch], "Adding optional relationships to nodes")

    async def execute_batches(
        self, batches: List[InfrahubBatch], progress_bar_message: str = "Executing batches"
    ) -> Sequence[Any]:
        if self.console:
            task_count = sum((batch.num_tasks for batch in batches))
            progress = Progress()
            progress.start()
            progress_task = progress.add_task(f"{progress_bar_message}...", total=task_count)
        exceptions, results = [], []
        for batch in batches:
            async for result in batch.execute():
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
                else:
                    results.append(result[1])
        if self.console:
            progress.stop()

        if self.console and exceptions:
            self.console.print(f"[red]{len(exceptions)} failures")
            for exception_str in exceptions:
                self.console.print(f"[red]{exception_str}")
        return results
