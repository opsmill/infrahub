import asyncio
from collections import defaultdict
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

import ujson

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.schema import GenericSchema
from infrahub_sdk.transfer.export.interface import ExporterInterface

from ..exceptions import FileAlreadyExistsError, InvalidNamespaceError
from .interface import ExporterInterface

if TYPE_CHECKING:
    from infrahub_sdk.schema import BaseNodeSchema

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
        node_schema_by_namespace: Dict[str, List[BaseNodeSchema]] = defaultdict(list)
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

        tasks = []
        for namespace in namespaces:
            tasks.extend(
                [
                    self.client.all(node_schema.kind, branch=branch)
                    for node_schema in node_schema_by_namespace[namespace]
                ]
            )

        nodes = list(chain(*await asyncio.gather(*tasks)))

        json_lines = [ujson.dumps({"kind": n.get_kind(), "graphql": n.get_raw_graphql_data()}) for n in nodes]
        file_content = "\n".join(json_lines)

        if not export_directory.exists():
            export_directory.mkdir()
        node_file.touch()
        node_file.write_text(file_content)
