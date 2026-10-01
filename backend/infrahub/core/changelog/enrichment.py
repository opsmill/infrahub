from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from opentelemetry import trace

from infrahub import config
from infrahub.core.constants.schema import DISPLAY_LABEL_ATTRIBUTE_NAME, HFID_ATTRIBUTE_NAME
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger
from infrahub.utilities.chunks import chunked
from infrahub.utils import log_exception_guard

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Mapping

    from infrahub.core.branch import Branch
    from infrahub.core.query.node import NodeStoredLabels
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
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
"""Labels of a changelog whose node cannot be resolved (for instance a peer deleted in a cascade).

A changelog always names its node, so this stands in for the node's own labels only; an unresolved
relationship peer keeps its optional labels unset instead.
"""


LABEL_FIELDS: dict[str, Any] = {DISPLAY_LABEL_ATTRIBUTE_NAME: None, HFID_ATTRIBUTE_NAME: None}
"""The only node fields a label read needs: both labels are materialized as attributes on the node."""

HFID_FIELDS: dict[str, Any] = {HFID_ATTRIBUTE_NAME: None}
"""The only node field an HFID read needs."""


class LabeledNode(Protocol):
    """What the label reader needs from a loaded node: its two labels and whether each is stored."""

    def display_label_needs_read(self) -> bool: ...

    def hfid_needs_read(self) -> bool: ...

    async def get_display_label(self, db: InfrahubDatabase) -> str: ...

    async def get_hfid(self, db: InfrahubDatabase) -> list[str] | None: ...


def _lacks_stored_labels(node: LabeledNode) -> bool:
    return node.display_label_needs_read() or node.hfid_needs_read()


def _lacks_stored_hfid(node: LabeledNode) -> bool:
    return node.hfid_needs_read()


class NodeLoader(Protocol):
    """Loads nodes by ID, letting the label reader read the graph without importing concrete implementations.

    ``fields`` restricts the attributes and relationships read from the graph, in the shape the node
    manager accepts; ``None`` loads the whole node.
    """

    async def __call__(
        self, *, db: InfrahubDatabase, ids: list[str], branch: Branch, fields: dict[str, Any] | None
    ) -> Mapping[str, LabeledNode]: ...


@dataclass(frozen=True)
class LabelsFromStorage:
    """A node's stored labels read with its schema, to tell which ones are the node's own labels."""

    stored: NodeStoredLabels
    """The labels read from storage."""

    schema: MainSchemaTypes
    """The schema of the node's kind on the branch."""

    def knows_hfid(self) -> bool:
        """Whether storage alone gives the node's HFID: its kind has no HFID, or one is stored."""
        return not self.schema.human_friendly_id or bool(self.stored.hfid)

    def knows_labels(self) -> bool:
        """Whether storage alone gives both the display label and the HFID."""
        return self.stored.display_label is not None and self.knows_hfid()

    @property
    def hfid(self) -> list[str] | None:
        """The node's HFID, None for a kind without an HFID.

        Raises:
            ValueError: When storage does not give the node's HFID.

        """
        if not self.knows_hfid():
            raise ValueError(f"the stored labels of this {self.stored.kind} do not give its HFID")
        return self.stored.hfid if self.schema.human_friendly_id else None

    @property
    def display_label(self) -> str:
        """The node's display label.

        Raises:
            ValueError: When storage does not give the node's display label.

        """
        if self.stored.display_label is None:
            raise ValueError(f"the stored labels of this {self.stored.kind} do not give its display label")
        return self.stored.display_label


class StoredLabelLoader(Protocol):
    """Reads the labels stored on nodes by ID without instantiating the nodes.

    Only the ``label_names`` attributes are read; a node that is not active on the branch is absent
    from the result.
    """

    async def __call__(
        self, *, db: InfrahubDatabase, ids: list[str], branch: Branch, label_names: list[str]
    ) -> Mapping[str, NodeStoredLabels]: ...


class NodeLabelReader(Protocol):
    """Resolves the display label and human-friendly ID of nodes by ID."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]: ...

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]: ...


class DbNodeLabelReader:
    """Reads node labels from the graph through an injected stored-label loader and node loader.

    This is the only piece that touches the database, keeping the loading logic that surrounds it
    testable without one.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema_branch: SchemaBranch,
        stored_label_loader: StoredLabelLoader,
        node_loader: NodeLoader,
        page_size: int,
    ) -> None:
        self._db = db
        self._branch = branch
        self._schema_branch = schema_branch
        self._stored_label_loader = stored_label_loader
        self._node_loader = node_loader
        self._page_size = page_size

    async def _read_stored(self, node_ids: list[str], label_names: list[str]) -> dict[str, LabelsFromStorage]:
        """Read the stored labels of the nodes whose schema can interpret them.

        A schema node ignores its stored labels and a node whose kind is gone has no schema, so both
        are left out and go through the node loader.
        """
        stored = await self._stored_label_loader(
            db=self._db, ids=node_ids, branch=self._branch, label_names=label_names
        )
        return {
            node_id: LabelsFromStorage(stored=labels, schema=schema)
            for node_id, labels in stored.items()
            if (schema := self._schema_of(labels.kind)) is not None and not schema.is_schema_node
        }

    def _schema_of(self, kind: str) -> MainSchemaTypes | None:
        try:
            return self._schema_branch.get(name=kind, duplicate=False)
        except SchemaNotFoundError:
            return None

    async def _load_nodes(
        self, node_ids: list[str], fields: dict[str, Any], lacks_stored_value: Callable[[LabeledNode], bool]
    ) -> dict[str, LabeledNode]:
        """Load the nodes in pages of at most ``page_size`` ids so a large batch never issues one huge query.

        Only the requested label attributes are read, since the labels are materialized on the node
        and the rest of its fields would be loaded to be discarded. A node whose label is not
        materialized is reloaded whole, so the label can be computed from its fields as a full load
        would.
        """
        nodes: dict[str, LabeledNode] = {}
        for page in chunked(node_ids, self._page_size):
            nodes.update(await self._node_loader(db=self._db, ids=page, branch=self._branch, fields=fields))
        unmaterialized = [node_id for node_id, node in nodes.items() if lacks_stored_value(node)]
        for page in chunked(unmaterialized, self._page_size):
            nodes.update(await self._node_loader(db=self._db, ids=page, branch=self._branch, fields=None))
        return nodes

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        """Read the labels from storage, loading through the node loader only the nodes storage does not give."""
        labels: dict[str, NodeLabels] = {}
        stored = await self._read_stored(node_ids, label_names=[DISPLAY_LABEL_ATTRIBUTE_NAME, HFID_ATTRIBUTE_NAME])
        for node_id, from_storage in stored.items():
            if from_storage.knows_labels():
                labels[node_id] = NodeLabels(display_label=from_storage.display_label, hfid=from_storage.hfid)

        to_load = [node_id for node_id in node_ids if node_id not in labels]
        nodes = await self._load_nodes(to_load, fields=LABEL_FIELDS, lacks_stored_value=_lacks_stored_labels)
        for node_id, node in nodes.items():
            labels[node_id] = NodeLabels(
                display_label=await node.get_display_label(db=self._db), hfid=await node.get_hfid(db=self._db)
            )
        return labels

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        """Read the HFIDs from storage, loading through the node loader only the nodes storage does not give."""
        hfids: dict[str, list[str] | None] = {}
        stored = await self._read_stored(node_ids, label_names=[HFID_ATTRIBUTE_NAME])
        for node_id, from_storage in stored.items():
            if from_storage.knows_hfid():
                hfids[node_id] = from_storage.hfid

        to_load = [node_id for node_id in node_ids if node_id not in hfids]
        nodes = await self._load_nodes(to_load, fields=HFID_FIELDS, lacks_stored_value=_lacks_stored_hfid)
        for node_id, node in nodes.items():
            hfids[node_id] = await node.get_hfid(db=self._db)
        return hfids


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


def node_label_loader(
    db: InfrahubDatabase,
    branch: Branch,
    schema_branch: SchemaBranch,
    stored_label_loader: StoredLabelLoader,
    node_loader: NodeLoader,
) -> NodeLabelLoader:
    """Build a NodeLabelLoader that reads labels from the database through the given loaders."""
    return NodeLabelLoader(
        reader=DbNodeLabelReader(
            db=db,
            branch=branch,
            schema_branch=schema_branch,
            stored_label_loader=stored_label_loader,
            node_loader=node_loader,
            page_size=config.SETTINGS.database.query_size_limit,
        )
    )
