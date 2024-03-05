from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional

import ujson
from rich.console import Console
from rich.progress import Progress

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.schema import NodeSchema

from ..constants import ILLEGAL_NAMESPACES
from ..exceptions import FileAlreadyExistsError, InvalidNamespaceError
from .interface import ExporterInterface


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

    async def export(
        self, export_directory: Path, namespaces: List[str], branch: str, exclude: Optional[List[str]] = None
    ) -> None:
        illegal_namespaces = set(ILLEGAL_NAMESPACES)
        node_file = export_directory / Path("nodes.json")
        if node_file.exists():
            raise FileAlreadyExistsError(f"{node_file.absolute()} already exists")
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

        schema_batch = await self.client.create_batch()
        for node_schema in node_schema_map.values():
            schema_batch.add(node_schema.kind, task=self.client.all, branch=branch)

        all_nodes = []
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
            node_file.touch()
            node_file.write_text(file_content)
        if self.console:
            self.console.print(f"Export directory - {export_directory}")
