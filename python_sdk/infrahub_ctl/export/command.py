import asyncio
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Any, Dict, List

import typer
from rich.console import Console

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.node.deduplicator import NodeDeduplicator
from infrahub_sdk.transfer.export.interface import ExporterInterface

if TYPE_CHECKING:
    from infrahub_sdk.schema import BaseNodeSchema

from .constants import ILLEGAL_KINDS, ILLEGAL_NAMESPACES


async def do_export(
    exporter: ExporterInterface,
    client: InfrahubClient,
    deduplicator: NodeDeduplicator,
    namespaces: List[str],
    branch: str,
) -> List[Dict[str, Any]]:
    console = Console()
    node_schema_map = await client.schema.all(branch=branch)
    node_schema_by_namespace: Dict[str, List[BaseNodeSchema]] = defaultdict(list)
    for node_schema in node_schema_map.values():
        if node_schema.kind.lower() in ILLEGAL_KINDS:
            continue
        node_schema_by_namespace[node_schema.namespace.lower()].append(node_schema)

    if namespaces:
        invalid_namespaces = [ns for ns in namespaces if ns not in node_schema_by_namespace]
        if invalid_namespaces:
            console.print(f"[red]these namespaces do not exist: {invalid_namespaces}")
            raise typer.Exit(1)
    else:
        namespaces = [ns for ns in node_schema_by_namespace if ns not in ILLEGAL_NAMESPACES]

    tasks = []
    for namespace in namespaces:
        tasks.extend(
            [client.all(node_schema.kind, branch=branch) for node_schema in node_schema_by_namespace[namespace]]
        )

    all_nodes = chain(*await asyncio.gather(*tasks))
    unique_nodes = await deduplicator.deduplicate(all_nodes)
    return await exporter.export(unique_nodes)
