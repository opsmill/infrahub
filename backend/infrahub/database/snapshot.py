"""Portable, dump-free database snapshots of the initialized graph.

Instead of running the full ``first_time_initialization`` (which writes thousands of nodes one at
a time), a snapshot captures the initialized graph as plain data and replays it with bulk
``CREATE`` statements. This is much faster and, unlike ``neo4j-admin`` dumps, is portable Cypher
with no binary/version coupling and an inspectable JSON artifact.

The replay is a pure ``CREATE`` (no ``MERGE``/dedup): the snapshot already encodes the final,
deduplicated graph, so shared value nodes are recreated exactly once and linked verbatim.

Generation is deterministic (see ``deterministic_generation``) so the committed snapshot is
byte-stable across regenerations and a CI job can validate its freshness with a plain diff.
"""

from __future__ import annotations

import gzip
import json
import pathlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.query import QueryType

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.database import InfrahubDatabase

# A fixed instant and secrets used only while generating a snapshot, so the output is reproducible.
# These become the credentials baked into the seed, so CI must authenticate with them.
DETERMINISTIC_TIMESTAMP = "2024-01-01T00:00:00.000000+00:00"
DETERMINISTIC_BCRYPT_SALT = b"$2b$12$KIXQ0Z5oL2pRz3oQwG3nE."  # a fixed, valid bcrypt salt for reproducible hashes
DETERMINISTIC_DEFAULT_BRANCH = "main"
DETERMINISTIC_ADMIN_PASSWORD = "infrahub"
DETERMINISTIC_ADMIN_TOKEN = "06438eb2-8019-4776-878c-0941b1f1d1ec"
DETERMINISTIC_AGENT_PASSWORD = "infrahub"
DETERMINISTIC_AGENT_TOKEN = "44af444d-3b26-410d-9546-b758657e026c"

RESTORE_CHUNK_SIZE = 5000
_JSON_SCALARS = (str, int, float, bool, type(None))


@dataclass
class GraphSnapshot:
    """A serialisable capture of every node and edge in the database."""

    graph_version: int
    nodes: list[dict[str, Any]]  # {"labels": [...], "properties": {...}} — index in list is the node id
    edges: list[dict[str, Any]]  # {"from": <idx>, "to": <idx>, "type": str, "properties": {...}}

    def to_dict(self) -> dict[str, Any]:
        return {"graph_version": self.graph_version, "nodes": self.nodes, "edges": self.edges}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphSnapshot:
        return cls(graph_version=data["graph_version"], nodes=data["nodes"], edges=data["edges"])


def _assert_json_safe(value: Any, context: str) -> None:
    """Guard against property types that would not survive a JSON round-trip (e.g. neo4j temporal/spatial).

    Raises:
        TypeError: When a property value is not a JSON scalar or list of scalars.

    """
    if isinstance(value, list):
        for item in value:
            _assert_json_safe(item, context)
        return
    if not isinstance(value, _JSON_SCALARS):
        raise TypeError(
            f"Property {context} has non-JSON-serialisable type {type(value).__name__!r}; "
            "the snapshot format only supports scalar/list properties."
        )


async def capture_graph(db: InfrahubDatabase) -> GraphSnapshot:
    """Read every node and edge into a deterministic, serialisable snapshot."""
    node_records = await db.execute_query(
        query="MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props",
        params={},
        name="snapshot_capture_nodes",
        type=QueryType.READ,
    )
    edge_records = await db.execute_query(
        query=(
            "MATCH (a)-[e]->(b) "
            "RETURN elementId(a) AS from_eid, elementId(b) AS to_eid, type(e) AS etype, properties(e) AS props"
        ),
        params={},
        name="snapshot_capture_edges",
        type=QueryType.READ,
    )

    nodes: list[dict[str, Any]] = []
    element_ids: list[str] = []
    for record in node_records:
        labels = sorted(record.get("labels"))
        props = dict(record.get("props"))
        for key, value in props.items():
            _assert_json_safe(value, context=f"{labels}.{key}")
        nodes.append({"labels": labels, "properties": props})
        element_ids.append(record.get("eid"))

    # Sort nodes into a canonical order so the artifact is stable regardless of scan order.
    order = sorted(range(len(nodes)), key=lambda i: json.dumps(nodes[i], sort_keys=True))
    new_index = {old: new for new, old in enumerate(order)}
    sorted_nodes = [nodes[old] for old in order]
    eid_to_index = {element_ids[old]: new for old, new in new_index.items()}

    edges: list[dict[str, Any]] = []
    for record in edge_records:
        props = dict(record.get("props"))
        for key, value in props.items():
            _assert_json_safe(value, context=f"[{record.get('etype')}].{key}")
        edges.append(
            {
                "from": eid_to_index[record.get("from_eid")],
                "to": eid_to_index[record.get("to_eid")],
                "type": record.get("etype"),
                "properties": props,
            }
        )
    edges.sort(key=lambda e: json.dumps(e, sort_keys=True))

    return GraphSnapshot(graph_version=GRAPH_VERSION, nodes=sorted_nodes, edges=edges)


async def restore_graph(db: InfrahubDatabase, snapshot: GraphSnapshot) -> None:
    """Recreate a captured graph with bulk CREATE queries (pure create, no MERGE/dedup).

    Raises:
        ValueError: When the snapshot's graph_version does not match the code's GRAPH_VERSION.

    """
    if snapshot.graph_version != GRAPH_VERSION:
        raise ValueError(
            f"Snapshot graph_version {snapshot.graph_version} does not match the code's GRAPH_VERSION "
            f"{GRAPH_VERSION}; regenerate the snapshot."
        )

    # Tag every node with a temporary index so edges can be matched without relying on uuids.
    await db.execute_query(
        query="CREATE INDEX snapshot_restore_idx IF NOT EXISTS FOR (n:`_SnapshotNode`) ON (n._snapshot_idx)",
        params={},
        name="snapshot_restore_index",
    )
    await db.execute_query(query="CALL db.awaitIndexes(300)", params={}, name="snapshot_restore_await_index")

    # Group nodes by their label set so each bulk CREATE uses a single static label list.
    by_labels: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for index, node in enumerate(snapshot.nodes):
        by_labels.setdefault(tuple(node["labels"]), []).append({"idx": index, "props": node["properties"]})

    for labels, rows in by_labels.items():
        label_str = ":".join(["`_SnapshotNode`", *[f"`{label}`" for label in labels]])
        query = f"UNWIND $rows AS row CREATE (n:{label_str}) SET n = row.props SET n._snapshot_idx = row.idx"
        for start in range(0, len(rows), RESTORE_CHUNK_SIZE):
            await db.execute_query(
                query=query,
                params={"rows": rows[start : start + RESTORE_CHUNK_SIZE]},
                name="snapshot_restore_nodes",
                type=QueryType.WRITE,
            )

    by_type: dict[str, list[dict[str, Any]]] = {}
    for edge in snapshot.edges:
        by_type.setdefault(edge["type"], []).append(
            {"from": edge["from"], "to": edge["to"], "props": edge["properties"]}
        )

    for edge_type, rows in by_type.items():
        query = (
            "UNWIND $rows AS row "
            "MATCH (a:`_SnapshotNode` {_snapshot_idx: row.from}), (b:`_SnapshotNode` {_snapshot_idx: row.to}) "
            f"CREATE (a)-[r:`{edge_type}`]->(b) SET r = row.props"
        )
        for start in range(0, len(rows), RESTORE_CHUNK_SIZE):
            await db.execute_query(
                query=query,
                params={"rows": rows[start : start + RESTORE_CHUNK_SIZE]},
                name="snapshot_restore_edges",
                type=QueryType.WRITE,
            )

    await db.execute_query(
        query="MATCH (n:`_SnapshotNode`) CALL (n) { REMOVE n:`_SnapshotNode` REMOVE n._snapshot_idx } IN TRANSACTIONS OF 10000 ROWS",
        params={},
        name="snapshot_restore_cleanup",
        type=QueryType.WRITE,
    )
    await db.execute_query(
        query="DROP INDEX snapshot_restore_idx IF EXISTS", params={}, name="snapshot_restore_drop_index"
    )


def write_snapshot_file(snapshot: GraphSnapshot, path: str) -> None:
    """Serialise a snapshot to a gzip-compressed JSON file, deterministically (stable bytes)."""
    payload = json.dumps(snapshot.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    # mtime=0 keeps the gzip header (and therefore the file bytes) stable for identical input.
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    pathlib.Path(path).write_bytes(compressed)


def read_snapshot_file(path: str) -> GraphSnapshot:
    payload = gzip.decompress(pathlib.Path(path).read_bytes())
    return GraphSnapshot.from_dict(json.loads(payload))


@contextmanager
def deterministic_generation() -> Iterator[None]:
    """Patch the volatile inputs of a bootstrap (uuids, time, password salt) so the resulting graph is reproducible.

    Only affects the current process for the duration of the context; intended for snapshot generation, never
    for a live server.
    """
    import importlib
    import itertools
    import uuid as uuid_module

    import infrahub.core.timestamp as timestamp_module
    from infrahub import config, helpers

    # Every module that imports UUIDT and generates a node/attribute/relationship id during bootstrap.
    uuidt_modules = [
        importlib.import_module(name)
        for name in (
            "infrahub.core.node",
            "infrahub.core.node.standard",
            "infrahub.core.attribute",
            "infrahub.core.relationship.model",
            "infrahub.core.query.relationship",
            "infrahub.core.initialization",
        )
    ]

    counter = itertools.count(1)

    initial = config.SETTINGS.initial
    saved_initial = {
        "default_branch": initial.default_branch,
        "admin_password": initial.admin_password,
        "admin_token": initial.admin_token,
        "agent_password": initial.agent_password,
        "agent_token": initial.agent_token,
    }
    initial.default_branch = DETERMINISTIC_DEFAULT_BRANCH
    initial.admin_password = DETERMINISTIC_ADMIN_PASSWORD
    initial.admin_token = DETERMINISTIC_ADMIN_TOKEN
    initial.agent_password = DETERMINISTIC_AGENT_PASSWORD
    initial.agent_token = DETERMINISTIC_AGENT_TOKEN

    class _DeterministicUUIDT:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            self._value = str(uuid_module.UUID(int=next(counter)))

        def __str__(self) -> str:
            return self._value

        def short(self) -> str:
            return self._value[-8:]

        @classmethod
        def new(cls, *args: Any, **kwargs: Any) -> uuid_module.UUID:  # noqa: ARG003
            return uuid_module.UUID(str(cls()))

    original_base_init = timestamp_module.Timestamp.__bases__[0].__init__

    def _fixed_init(self: Any, value: Any = None) -> None:
        original_base_init(self, value if value is not None else DETERMINISTIC_TIMESTAMP)

    saved_uuidt = {module: getattr(module, "UUIDT", None) for module in uuidt_modules}
    saved_gensalt = helpers.bcrypt.gensalt
    saved_ts_init = timestamp_module.Timestamp.__bases__[0].__init__

    for module in uuidt_modules:
        if hasattr(module, "UUIDT"):
            module.UUIDT = _DeterministicUUIDT  # type: ignore[assignment,misc]
    helpers.bcrypt.gensalt = lambda *_args, **_kwargs: DETERMINISTIC_BCRYPT_SALT  # type: ignore[assignment]
    timestamp_module.Timestamp.__bases__[0].__init__ = _fixed_init  # type: ignore[assignment]
    try:
        yield
    finally:
        for module, value in saved_uuidt.items():
            if value is not None:
                module.UUIDT = value  # type: ignore[assignment,misc]
        helpers.bcrypt.gensalt = saved_gensalt  # type: ignore[assignment]
        timestamp_module.Timestamp.__bases__[0].__init__ = saved_ts_init  # type: ignore[assignment]
        for key, value in saved_initial.items():
            setattr(initial, key, value)
