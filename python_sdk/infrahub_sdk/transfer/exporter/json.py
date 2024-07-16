from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Optional

import ujson
from rich.console import Console
from rich.progress import Progress

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.queries import QUERY_RELATIONSHIPS
from infrahub_sdk.schema import MainSchemaTypes, NodeSchema

from ..constants import ILLEGAL_NAMESPACES
from ..exceptions import FileAlreadyExistsError, InvalidNamespaceError
from .interface import ExporterInterface

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode


class LineDelimitedJSONExporter(ExporterInterface):
    def __init__(self, client: InfrahubClient, console: Optional[Console] = None):
        self.client = client
        self.console = console

    @contextmanager
    def wrapped_task_output(self, start: str, end: str = "[green]done") -> Generator:
        if self.console:
            self.console.print(f"{start}", end="...")
        yield
        if self.console:
            self.console.print(f"{end}")

    def identify_many_to_many_relationships(
        self, node_schema_map: dict[str, MainSchemaTypes]
    ) -> dict[tuple[str, str], str]:
        # Identify many to many relationships by src/dst couples
        many_relationship_identifiers: dict[tuple[str, str], str] = {}

        for node_schema in node_schema_map.values():
            for relationship in node_schema.relationships:
                if (
                    relationship.cardinality != "many"
                    or not relationship.optional
                    or not relationship.identifier
                    or relationship.peer not in node_schema_map
                ):
                    continue
                for peer_relationship in node_schema_map[relationship.peer].relationships:
                    if peer_relationship.cardinality != "many" or peer_relationship.peer != node_schema.kind:
                        continue

                    forward = many_relationship_identifiers.get((node_schema.kind, relationship.peer))
                    backward = many_relationship_identifiers.get((relationship.peer, node_schema.kind))

                    # Record the relationship only if it's not known in one way or another
                    if not forward and not backward:
                        many_relationship_identifiers[(node_schema.kind, relationship.peer)] = relationship.identifier

        return many_relationship_identifiers

    async def retrieve_many_to_many_relationships(
        self, node_schema_map: dict[str, MainSchemaTypes], branch: str
    ) -> list[dict[str, Any]]:
        has_remaining_items = True
        page_number = 1
        page_size = 50

        many_relationship_identifiers = list(self.identify_many_to_many_relationships(node_schema_map).values())
        many_relationships: list[dict[str, Any]] = []

        if not many_relationship_identifiers:
            return []

        while has_remaining_items:
            offset = (page_number - 1) * page_size

            response = await self.client.execute_graphql(
                QUERY_RELATIONSHIPS,
                variables={
                    "offset": offset,
                    "limit": page_size,
                    "relationship_identifiers": many_relationship_identifiers,
                },
                branch_name=branch,
                tracker=f"query-relationships-page{page_number}",
            )
            many_relationships.extend(response["Relationship"]["edges"])

            remaining_items = response["Relationship"]["count"] - (offset + page_size)
            if remaining_items <= 0:
                has_remaining_items = False
            page_number += 1

        return many_relationships

    # FIXME: Split in smaller functions
    async def export(  # pylint: disable=too-many-branches
        self, export_directory: Path, namespaces: list[str], branch: str, exclude: Optional[list[str]] = None
    ) -> None:
        illegal_namespaces = set(ILLEGAL_NAMESPACES)
        node_file = export_directory / "nodes.json"
        relationship_file = export_directory / "relationships.json"

        for f in (node_file, relationship_file):
            if f.exists():
                raise FileAlreadyExistsError(f"{f.resolve()} already exists")
        if set(namespaces) & illegal_namespaces:
            raise InvalidNamespaceError(f"namespaces cannot include {illegal_namespaces}")

        with self.wrapped_task_output("Retrieving schema to export"):
            node_schema_map = await self.client.schema.all(branch=branch, namespaces=namespaces)
            node_schema_map = {
                kind: schema
                for kind, schema in node_schema_map.items()
                if isinstance(schema, NodeSchema)
                and schema.namespace not in illegal_namespaces
                and (not exclude or kind not in exclude)
            }
            retrieved_namespaces = {node_schema.namespace for node_schema in node_schema_map.values()}

        if namespaces:
            invalid_namespaces = [ns for ns in namespaces if ns not in retrieved_namespaces]
            if invalid_namespaces:
                raise InvalidNamespaceError(f"these namespaces do not exist on branch {branch}: {invalid_namespaces}")

        with self.wrapped_task_output("Retrieving many-to-many relationships"):
            many_relationships = await self.retrieve_many_to_many_relationships(node_schema_map, branch)

        schema_batch = await self.client.create_batch()
        for node_schema in node_schema_map.values():
            schema_batch.add(node_schema.kind, task=self.client.all, branch=branch)

        all_nodes: list[InfrahubNode] = []
        if self.console:
            progress = Progress()
            progress.start()
            progress_task = progress.add_task("Retrieving nodes...", total=schema_batch.num_tasks)
        async for _, schema_nodes in schema_batch.execute():
            all_nodes.extend(schema_nodes)
            if self.console:
                progress.update(progress_task, advance=1)
        if self.console:
            progress.stop()

        with self.wrapped_task_output("Writing export"):
            json_lines = [
                ujson.dumps(
                    {
                        "id": n.id,
                        "kind": n.get_kind(),
                        "graphql_json": ujson.dumps(n.get_raw_graphql_data()),
                    }
                )
                for n in all_nodes
            ]
            file_content = "\n".join(json_lines)

            if not export_directory.exists():
                export_directory.mkdir()

            node_file.write_text(file_content)
            relationship_file.write_text(ujson.dumps(many_relationships))

        if self.console:
            self.console.print(f"Export directory - {export_directory}")
