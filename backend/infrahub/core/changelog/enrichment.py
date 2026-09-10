from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar

from opentelemetry import trace

from infrahub import config
from infrahub.log import get_logger
from infrahub.utilities.chunks import chunked
from infrahub.utils import log_exception_guard

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

log = get_logger()

_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True)
class NodeLabels:
    """Human-readable identifiers of a node, added to changelog payloads for external consumers."""

    display_label: str
    """The node's display label."""

    hfid: list[str] | None
    """The node's human-friendly ID, or None when the node has none."""


PLACEHOLDER_LABELS = NodeLabels(display_label="n/a", hfid=None)
"""Fallback used when a referenced node cannot be resolved (for instance a peer deleted in a cascade)."""


class NodeLoader(Protocol):
    """Loads nodes by ID, letting the label reader read the graph without importing concrete implementations."""

    async def __call__(self, *, db: InfrahubDatabase, ids: list[str], branch: Branch) -> dict[str, Node]: ...


class NodeLabelReader(Protocol):
    """Resolves the display label and human-friendly ID of nodes by ID."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]: ...

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]: ...


class DbNodeLabelReader:
    """Reads node labels from the graph through an injected node loader.

    This is the only piece that touches the database, keeping the loading logic that surrounds it
    testable without one.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, node_loader: NodeLoader) -> None:
        self._db = db
        self._branch = branch
        self._node_loader = node_loader

    async def _load_nodes(self, node_ids: list[str]) -> dict[str, Node]:
        """Load the nodes in query-size-limited pages so a large batch never issues one huge query."""
        nodes: dict[str, Node] = {}
        for page in chunked(node_ids, config.SETTINGS.database.query_size_limit):
            nodes.update(await self._node_loader(db=self._db, ids=page, branch=self._branch))
        return nodes

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        nodes = await self._load_nodes(node_ids)
        return {
            node_id: NodeLabels(
                display_label=await node.get_display_label(db=self._db),
                hfid=await node.get_hfid(db=self._db),
            )
            for node_id, node in nodes.items()
        }

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        nodes = await self._load_nodes(node_ids)
        return {node_id: await node.get_hfid(db=self._db) for node_id, node in nodes.items()}


class NodeLabelLoader:
    """Normalizes node IDs and resolves their changelog identifiers through an injected reader."""

    def __init__(self, reader: NodeLabelReader) -> None:
        self._reader = reader

    async def load_labels(self, node_ids: Iterable[str]) -> dict[str, NodeLabels]:
        """Return the display label and HFID of each node, holding only the ones that were found."""
        return await self._resolve(node_ids, self._reader.load_labels)

    async def load_hfids(self, node_ids: Iterable[str]) -> dict[str, list[str] | None]:
        """Return only the HFID of each node, without resolving the display labels it does not need."""
        return await self._resolve(node_ids, self._reader.load_hfids)

    async def _resolve(
        self, node_ids: Iterable[str], read: Callable[[list[str]], Awaitable[dict[str, _ResultT]]]
    ) -> dict[str, _ResultT]:
        """Normalize the IDs and read them, degrading to an empty mapping on failure.

        Duplicate and empty IDs are ignored, and an empty request resolves without reading. Label
        enrichment is cosmetic, so a read failure degrades rather than propagating: the operation
        that asked for the labels has already committed and must not be failed or rolled back.
        """
        unique_ids = sorted({node_id for node_id in node_ids if node_id})
        if not unique_ids:
            return {}

        with trace.get_tracer(__name__).start_as_current_span("changelog.load_node_labels") as span:
            span.set_attribute("changelog.node_count", len(unique_ids))
            # A schemaless peer or a transient read must not fail the committed operation.
            with log_exception_guard(log, "Changelog label enrichment failed; changelog will omit labels"):
                return await read(unique_ids)
            return {}


def node_label_loader(db: InfrahubDatabase, branch: Branch, node_loader: NodeLoader) -> NodeLabelLoader:
    """Build a NodeLabelLoader that reads labels from the database through the given node loader."""
    return NodeLabelLoader(reader=DbNodeLabelReader(db=db, branch=branch, node_loader=node_loader))
