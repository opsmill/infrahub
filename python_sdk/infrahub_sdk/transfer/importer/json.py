from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Mapping, Optional, Sequence

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
    from infrahub_sdk.schema import NodeSchema, RelationshipSchema


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
        self.all_nodes: dict[str, InfrahubNode] = {}
        self.schemas_by_kind: Mapping[str, NodeSchema] = {}
        # Map relationship schema by attribute of a node kind e.g. {"MyNodeKind": {"MyRelationship": RelationshipSchema}}
        # This is used to resolve which relationships are many to many to prevent them from being re-imported like others as they'll get duplicated
        self.optional_relationships_schemas_by_node_kind: dict[str, dict[str, RelationshipSchema]] = defaultdict(dict)
        self.optional_relationships_by_node: dict[str, dict[str, Any]] = defaultdict(dict)

    @contextmanager
    def wrapped_task_output(self, start: str, end: str = "[green]done") -> Generator:
        if self.console:
            self.console.print(f"{start}", end="...")
        yield
        if self.console:
            self.console.print(f"{end}")

    async def import_data(self, import_directory: Path, branch: str) -> None:
        node_file = import_directory / "nodes.json"
        relationship_file = import_directory / "relationships.json"
        for f in (node_file, relationship_file):
            if not f.exists():
                raise TransferFileNotFoundError(f"{f.resolve()} does not exist")
        with self.wrapped_task_output("Reading import directory"):
            table = pa_json.read_json(node_file.resolve())

        with self.wrapped_task_output("Analyzing import"):
            import_nodes_by_kind = defaultdict(list)
            for graphql_data, kind in zip(table.column("graphql_json"), table.column("kind")):
                node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
                import_nodes_by_kind[str(kind)].append(node)
                self.all_nodes[node.id] = node

        schema_batch = await self.client.create_batch()
        for kind in import_nodes_by_kind:
            schema_batch.add(task=self.client.schema.get, kind=kind, branch=branch)
        schemas = await self.execute_batches([schema_batch], "Retrieving schema")

        self.schemas_by_kind = {schema.kind: schema for schema in schemas}

        with self.wrapped_task_output("Ordering schema for import"):
            ordered_schema_names = self.topological_sorter.get_sorted_node_schema(schemas)

        with self.wrapped_task_output("Preparing nodes for import"):
            await self.remove_and_store_optional_relationships()

        with self.wrapped_task_output("Building import batches"):
            save_batch = await self.client.create_batch(return_exceptions=True)
            for group in ordered_schema_names:
                for kind in group:
                    schema_import_nodes = import_nodes_by_kind[kind]
                    if not schema_import_nodes:
                        continue
                    for node in schema_import_nodes:
                        save_batch.add(task=node.create, node=node, allow_upsert=True)

        await self.execute_batches([save_batch], "Creating and/or updating nodes")

        if not self.optional_relationships_by_node:
            return

        await self.update_optional_relationships()
        await self.update_many_to_many_relationships(file=relationship_file)

    async def remove_and_store_optional_relationships(self) -> None:
        for node in self.all_nodes.values():
            node_kind = node.get_kind()

            # Build a relationship name to relationship schema map, so we can retrieve the schema based on the name of a relationship later
            for relationship_schema in self.schemas_by_kind[node_kind].relationships:
                if relationship_schema.optional:
                    self.optional_relationships_schemas_by_node_kind[node_kind][relationship_schema.name] = (
                        relationship_schema
                    )

            for relationship_name in self.optional_relationships_schemas_by_node_kind[node_kind].keys():
                relationship_value = getattr(node, relationship_name)
                if isinstance(relationship_value, RelationshipManager):
                    if relationship_value.peer_ids:
                        self.optional_relationships_by_node[node.id][relationship_name] = relationship_value
                        setattr(node, relationship_name, None)
                elif isinstance(relationship_value, RelatedNode):
                    if relationship_value.id:
                        self.optional_relationships_by_node[node.id][relationship_name] = relationship_value
                        setattr(node, relationship_name, None)

    async def update_optional_relationships(self) -> None:
        update_batch = await self.client.create_batch(return_exceptions=True)
        for node in self.all_nodes.values():
            node_kind = node.get_kind()
            if node.id not in self.optional_relationships_by_node:
                continue
            for relationship_attr, relationship_value in self.optional_relationships_by_node[node.id].items():
                ignore = False
                relationship_schema = self.optional_relationships_schemas_by_node_kind[node_kind][relationship_attr]

                # Check if we are in a many-many relationship, ignore importing it if it is
                if relationship_schema.cardinality == "many":
                    if relationship_schema.peer not in self.schemas_by_kind:
                        continue
                    for peer_relationship in self.schemas_by_kind[relationship_schema.peer].relationships:
                        if peer_relationship.cardinality == "many" and peer_relationship.peer == node_kind:
                            ignore = True

                if not ignore:
                    setattr(node, relationship_attr, relationship_value)
            update_batch.add(task=node.update, node=node)
        await self.execute_batches([update_batch], "Adding optional relationships to nodes")

    async def update_many_to_many_relationships(self, file: Path) -> None:
        relationships = ujson.loads(file.read_text())
        update_batch = await self.client.create_batch(return_exceptions=True)

        for relationship in relationships:
            peers = relationship["node"]["peers"]
            src_node = self.all_nodes[peers[0]["id"]]
            dst_node = self.all_nodes[peers[1]["id"]]

            src_node_relationship = src_node._schema.get_relationship_by_identifier(relationship["node"]["identifier"])
            if src_node_relationship:
                update_batch.add(
                    task=src_node.add_relationships,  # type: ignore[arg-type]
                    node=src_node,
                    relation_to_update=src_node_relationship.name,
                    related_nodes=[dst_node.id],
                )

        await self.execute_batches([update_batch], "Adding many-to-many relationships to nodes")

    async def execute_batches(
        self, batches: list[InfrahubBatch], progress_bar_message: str = "Executing batches"
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
