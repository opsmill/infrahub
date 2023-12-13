from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Union

import ujson

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.schema import GenericSchema

from ..exceptions import FileAlreadyExistsError, InvalidNamespaceError
from .interface import ExporterInterface

if TYPE_CHECKING:
    from infrahub_sdk.schema import NodeSchema, GenericSchema

from ..constants import ILLEGAL_NAMESPACES


class LineDelimitedJSONExporter(ExporterInterface):
    def __init__(self, client: InfrahubClient):
        self.client = client

    async def export(
        self,
        export_directory: Path,
        namespaces: List[str],
        branch: str,
    ) -> None:
        node_file = export_directory / Path("nodes.json")
        if node_file.exists():
            raise FileAlreadyExistsError(f"{node_file.absolute()} already exists")
        if set(namespaces) & ILLEGAL_NAMESPACES:
            raise InvalidNamespaceError(f"namespaces cannot include {ILLEGAL_NAMESPACES}")

        node_schema_map = await self.client.schema.all(branch=branch)
        node_schema_by_namespace: Dict[str, List[Union[NodeSchema, GenericSchema]]] = defaultdict(list)
        for node_schema in node_schema_map.values():
            if isinstance(node_schema, GenericSchema):
                continue
            node_schema_by_namespace[node_schema.namespace.lower()].append(node_schema)

        if namespaces:
            invalid_namespaces = [ns for ns in namespaces if ns not in node_schema_by_namespace]
            if invalid_namespaces:
                raise InvalidNamespaceError(f"these namespaces do not exist: {invalid_namespaces}")
        else:
            namespaces = [ns for ns in node_schema_by_namespace if ns not in ILLEGAL_NAMESPACES]

        schema_batch = await self.client.create_batch()
        for namespace in namespaces:
            for node_schema in node_schema_by_namespace[namespace]:
                schema_batch.add(node_schema.kind, task=self.client.all, branch=branch)
        all_nodes = []

        async for _, schema_nodes in schema_batch.execute():
            all_nodes.extend(schema_nodes)

        timestamp = datetime.now(timezone.utc).astimezone().isoformat()
        json_lines = [
            ujson.dumps(
                {
                    "id": n.id,
                    "kind": n.get_kind(),
                    "timestamp": timestamp,
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
