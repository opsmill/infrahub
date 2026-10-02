"""Node-level schema migrations leave branch-agnostic data readable by every branch that still declares it.

A kind update or a node removal is a schema change scoped to the branch it runs on. When that branch is
a user branch, the default branch and any sibling forked before the change still declare the old schema,
so they must go on reading the old kind, its branch-agnostic attribute values and its branch-agnostic
relationship peers exactly as before. The branch the change ran on reads the migrated data.

Every scenario creates the same data set (an agnostic kind with an agnostic peer, and an aware kind with
an agnostic attribute and an agnostic relationship to an aware peer), snapshots it through the node
manager on every branch, runs one migration, and compares the snapshots again.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import (
    BranchSupportType,
    RelationshipCardinality,
    RelationshipKind,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.schema.tasks import get_derived_schema_pairs
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

NAMESPACE = "Agnosticnode"

KEEPER_KIND = f"{NAMESPACE}Keeper"
BEACON_KIND = f"{NAMESPACE}Beacon"
GADGET_KIND = f"{NAMESPACE}Gadget"
WIDGET_KIND = f"{NAMESPACE}Widget"
AWARE_LABELLED_KIND = f"{NAMESPACE}LabelledAware"
AGNOSTIC_LABELLED_KIND = f"{NAMESPACE}LabelledAgnostic"

BEACON_RENAMED = "Signal"
WIDGET_RENAMED = "Gizmo"

BEACON_KEEPER_IDENTIFIER = "agnosticnode_beacon__agnosticnode_keeper"
WIDGET_GADGET_IDENTIFIER = "agnosticnode_widget__agnosticnode_gadget"

READ_ATTRIBUTES = ("name", "serial", "label")
READ_RELATIONSHIPS = ("keeper", "gadget")
LABEL_DEFAULT = "unset"

KEEPER = NodeSchema(
    name="Keeper",
    namespace=NAMESPACE,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

BEACON = NodeSchema(
    name="Beacon",
    namespace=NAMESPACE,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="keeper",
            kind=RelationshipKind.GENERIC,
            peer=KEEPER_KIND,
            identifier=BEACON_KEEPER_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
    ],
)

GADGET = NodeSchema(
    name="Gadget",
    namespace=NAMESPACE,
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

WIDGET = NodeSchema(
    name="Widget",
    namespace=NAMESPACE,
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", optional=True, branch=BranchSupportType.AGNOSTIC),
    ],
    relationships=[
        RelationshipSchema(
            name="gadget",
            kind=RelationshipKind.GENERIC,
            peer=GADGET_KIND,
            identifier=WIDGET_GADGET_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

AWARE_LABELLED = GenericSchema(
    name="LabelledAware",
    namespace=NAMESPACE,
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(
            name="label", kind="Text", optional=True, default_value=LABEL_DEFAULT, branch=BranchSupportType.AGNOSTIC
        )
    ],
)

AGNOSTIC_LABELLED = GenericSchema(
    name="LabelledAgnostic",
    namespace=NAMESPACE,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[AttributeSchema(name="label", kind="Text", optional=True, default_value=LABEL_DEFAULT)],
)

AGNOSTIC_NODE_SCHEMA = SchemaRoot(generics=[AWARE_LABELLED, AGNOSTIC_LABELLED], nodes=[KEEPER, BEACON, GADGET, WIDGET])


class Shape(Enum):
    AGNOSTIC_KIND = "agnostic-kind"
    AWARE_KIND_WITH_AGNOSTIC_FIELDS = "aware-kind-with-agnostic-fields"
    AWARE_PEER_OF_AGNOSTIC_RELATIONSHIP = "aware-peer-of-agnostic-relationship"


class KindChange(Enum):
    RENAME = "rename"
    INHERIT_FROM = "inherit-from"


@dataclass
class ShapeSpec:
    kind: str
    renamed_name: str | None = None
    generic_kind: str | None = None

    @property
    def renamed_kind(self) -> str:
        return f"{NAMESPACE}{self.renamed_name}"


SHAPES = {
    Shape.AGNOSTIC_KIND: ShapeSpec(kind=BEACON_KIND, renamed_name=BEACON_RENAMED, generic_kind=AGNOSTIC_LABELLED_KIND),
    Shape.AWARE_KIND_WITH_AGNOSTIC_FIELDS: ShapeSpec(
        kind=WIDGET_KIND, renamed_name=WIDGET_RENAMED, generic_kind=AWARE_LABELLED_KIND
    ),
    Shape.AWARE_PEER_OF_AGNOSTIC_RELATIONSHIP: ShapeSpec(kind=GADGET_KIND),
}

ALL_READ_KINDS = (
    KEEPER_KIND,
    BEACON_KIND,
    GADGET_KIND,
    WIDGET_KIND,
    f"{NAMESPACE}{BEACON_RENAMED}",
    f"{NAMESPACE}{WIDGET_RENAMED}",
)

Snapshot = dict[str, dict[str, dict[str, Any]]]


@dataclass
class DataSet:
    keeper_id: str
    beacon_id: str
    gadget_id: str
    widget_id: str


@dataclass
class Scenario:
    data: DataSet
    migration_branch: Branch
    forked_before: Branch
    result: MigrationResult
    before: dict[str, Snapshot] = field(default_factory=dict)
    forked_after: Branch | None = None


@pytest.fixture
async def agnostic_node_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The core models are registered because the GraphQL schema of a branch cannot be generated without them."""
    registry.schema.register_schema(schema=AGNOSTIC_NODE_SCHEMA, branch=default_branch.name)
    default_branch.update_schema_hash()


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, **values: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **values)
    await node.save(db=db)
    return node


async def _create_data(db: InfrahubDatabase, branch: Branch) -> DataSet:
    keeper = await _create(db=db, branch=branch, kind=KEEPER_KIND, name="keeper-1")
    beacon = await _create(db=db, branch=branch, kind=BEACON_KIND, name="beacon-1", serial=11, keeper=keeper)
    gadget = await _create(db=db, branch=branch, kind=GADGET_KIND, name="gadget-1")
    widget = await _create(db=db, branch=branch, kind=WIDGET_KIND, name="widget-1", serial=22, gadget=gadget)
    return DataSet(keeper_id=keeper.id, beacon_id=beacon.id, gadget_id=gadget.id, widget_id=widget.id)


async def _read_all(db: InfrahubDatabase, branch: Branch) -> Snapshot:
    """Read every node of every test kind the branch's schema declares, through the node manager."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    snapshot: Snapshot = {}
    for kind in ALL_READ_KINDS:
        if not schema_branch.has(name=kind):
            continue
        schema = schema_branch.get(name=kind, duplicate=False)
        nodes = await NodeManager.query(db=db, schema=kind, branch=branch)
        by_id: dict[str, dict[str, Any]] = {}
        for node in nodes:
            fields: dict[str, Any] = {
                name: node.get_attribute(name=name).value for name in READ_ATTRIBUTES if name in schema.attribute_names
            }
            for rel_name in READ_RELATIONSHIPS:
                if rel_name in schema.relationship_names:
                    peer = await node.get_relationship(name=rel_name).get_peer(db=db)
                    fields[rel_name] = peer.id if peer else None
            by_id[node.id] = fields
        snapshot[kind] = by_id
    return snapshot


async def _edge_report(db: InfrahubDatabase, data: DataSet, title: str) -> None:
    """Print the node-level edges of every vertex carrying one of the data set's uuids."""
    query = """
    MATCH (n:Node)-[r:IS_PART_OF|HAS_ATTRIBUTE|IS_RELATED]-(peer)
    WHERE n.uuid IN $uuids
    RETURN n.uuid AS uuid, n.kind AS kind, labels(n) AS labels, elementId(n) AS vertex,
        type(r) AS edge_type, coalesce(peer.name, labels(peer)[0]) AS peer_name,
        r.branch AS branch, r.status AS status, r.from AS from_time, r.to AS to_time
    ORDER BY uuid, vertex, edge_type, peer_name, from_time
    """
    uuids = [data.keeper_id, data.beacon_id, data.gadget_id, data.widget_id]
    rows = await db.execute_query(query=query, params={"uuids": uuids})
    names = {data.keeper_id: "keeper", data.beacon_id: "beacon", data.gadget_id: "gadget", data.widget_id: "widget"}
    print(f"\n----- edges: {title} -----")
    vertex_index: dict[str, int] = {}
    for row in rows:
        vertex_number = vertex_index.setdefault(row["vertex"], len(vertex_index))
        closed = "closed" if row["to_time"] else "open"
        print(
            f"  {names[row['uuid']]:<7} v{vertex_number} {row['kind']:<26} {row['edge_type']:<13} "
            f"-> {row['peer_name']:<45} branch={row['branch']:<28} {row['status']:<8} {closed}"
        )


def _print_reads(title: str, reads: dict[str, Any]) -> None:
    print(f"\n----- reads: {title} -----")
    for branch_name, snapshot in reads.items():
        print(f"  [{branch_name}] {snapshot}")


async def _safe_read(db: InfrahubDatabase, branch: Branch) -> Snapshot | str:
    try:
        return await _read_all(db=db, branch=branch)
    except Exception as exc:
        return f"read raised {type(exc).__name__}: {exc}"


SIGNAL_KIND = f"{NAMESPACE}{BEACON_RENAMED}"
GIZMO_KIND = f"{NAMESPACE}{WIDGET_RENAMED}"
MATRIX_KINDS = (*ALL_READ_KINDS, AWARE_LABELLED_KIND, AGNOSTIC_LABELLED_KIND)


@dataclass
class ObjectProbe:
    """How an object of the data set is found, and how its relationship is seen from the far side."""

    name: str
    candidate_kinds: tuple[str, ...]
    reverse_source_kind: str | None = None
    reverse_peer_kinds: tuple[str, ...] = ()
    reverse_identifier: str | None = None


def _object_probes(data: DataSet) -> dict[str, ObjectProbe]:
    return {
        data.keeper_id: ObjectProbe(
            name="keeper",
            candidate_kinds=(KEEPER_KIND,),
            reverse_source_kind=KEEPER_KIND,
            reverse_peer_kinds=(BEACON_KIND, SIGNAL_KIND),
            reverse_identifier=BEACON_KEEPER_IDENTIFIER,
        ),
        data.beacon_id: ObjectProbe(name="beacon", candidate_kinds=(BEACON_KIND, SIGNAL_KIND, AGNOSTIC_LABELLED_KIND)),
        data.gadget_id: ObjectProbe(
            name="gadget",
            candidate_kinds=(GADGET_KIND,),
            reverse_source_kind=GADGET_KIND,
            reverse_peer_kinds=(WIDGET_KIND, GIZMO_KIND),
            reverse_identifier=WIDGET_GADGET_IDENTIFIER,
        ),
        data.widget_id: ObjectProbe(name="widget", candidate_kinds=(WIDGET_KIND, GIZMO_KIND, AWARE_LABELLED_KIND)),
    }


class _ErrorCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.msg.get("event", record.msg) if isinstance(record.msg, dict) else record.getMessage()
        self.messages.append(str(message))


@contextmanager
def _collect_errors() -> Iterator[_ErrorCollector]:
    collector = _ErrorCollector()
    logger = logging.getLogger("infrahub")
    logger.addHandler(collector)
    try:
        yield collector
    finally:
        logger.removeHandler(collector)


def _raised(exc: Exception) -> str:
    return f"raised {type(exc).__name__}: {exc}"


async def _node_fields(db: InfrahubDatabase, node: Node) -> dict[str, Any]:
    schema = node.get_schema()
    fields: dict[str, Any] = {
        name: node.get_attribute(name=name).value for name in READ_ATTRIBUTES if name in schema.attribute_names
    }
    for rel_name in READ_RELATIONSHIPS:
        if rel_name in schema.relationship_names:
            peer = await node.get_relationship(name=rel_name).get_peer(db=db)
            fields[rel_name] = peer.id if peer else None
    return fields


def _graphql_selection(schema_branch: SchemaBranch, kind: str) -> str:
    schema = schema_branch.get(name=kind, duplicate=False)
    parts = ["id", "__typename"]
    parts.extend(f"{name} {{ value }}" for name in READ_ATTRIBUTES if name in schema.attribute_names)
    parts.extend(f"{name} {{ node {{ id }} }}" for name in READ_RELATIONSHIPS if name in schema.relationship_names)
    return " ".join(parts)


async def _graphql_read(db: InfrahubDatabase, branch: Branch, kind: str, node_id: str) -> dict[str, Any]:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    query = 'query { %(kind)s(ids: ["%(node_id)s"]) { edges { node { %(selection)s } } } }' % {
        "kind": kind,
        "node_id": node_id,
        "selection": _graphql_selection(schema_branch=schema_branch, kind=kind),
    }
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None)
    data = [edge["node"] for edge in result.data[kind]["edges"]] if result.data and result.data.get(kind) else None
    errors = [error.message for error in result.errors] if result.errors else None
    return {"data": data, "errors": errors}


async def _read_object(db: InfrahubDatabase, branch: Branch, node_id: str, probe: ObjectProbe) -> dict[str, Any]:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    reads: dict[str, Any] = {}

    try:
        node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
        if node is None:
            reads["get_one"] = None
        else:
            kind = node.get_kind()
            declared = "" if schema_branch.has(name=kind) else " [UNDECLARED KIND]"
            reads["get_one"] = f"{kind}{declared} {await _node_fields(db=db, node=node)}"
    except Exception as exc:
        reads["get_one"] = _raised(exc)

    query_reads: dict[str, Any] = {}
    for kind in MATRIX_KINDS:
        if not schema_branch.has(name=kind):
            continue
        try:
            nodes = await NodeManager.query(db=db, schema=kind, branch=branch, filters={"ids": [node_id]})
            query_reads[kind] = [f"{n.get_kind()} {await _node_fields(db=db, node=n)}" for n in nodes] or "not listed"
        except Exception as exc:
            query_reads[kind] = _raised(exc)
    reads["query"] = {kind: value for kind, value in query_reads.items() if value != "not listed"}
    reads["query_not_listed"] = [kind for kind, value in query_reads.items() if value == "not listed"]

    if probe.reverse_source_kind and probe.reverse_identifier:
        reverse: dict[str, Any] = {}
        for peer_kind in probe.reverse_peer_kinds:
            if not schema_branch.has(name=peer_kind):
                continue
            rel_schema = RelationshipSchema(
                name="reverse",
                peer=peer_kind,
                identifier=probe.reverse_identifier,
                cardinality=RelationshipCardinality.MANY,
                branch=BranchSupportType.AGNOSTIC,
            )
            try:
                peers = await NodeManager.query_peers(
                    db=db,
                    ids=[node_id],
                    source_kind=probe.reverse_source_kind,
                    schema=rel_schema,
                    filters={},
                    branch=branch,
                )
                reverse[peer_kind] = [rel.get_peer_id() for rel in peers]
            except Exception as exc:
                reverse[peer_kind] = _raised(exc)
        reads["reverse_peers"] = reverse

    graphql_reads: dict[str, Any] = {}
    for kind in probe.candidate_kinds:
        if not schema_branch.has(name=kind):
            continue
        try:
            graphql_reads[kind] = await _graphql_read(db=db, branch=branch, kind=kind, node_id=node_id)
        except Exception as exc:
            graphql_reads[kind] = _raised(exc)
    reads["graphql"] = graphql_reads
    return reads


async def _read_matrix(db: InfrahubDatabase, scenario: Scenario, title: str) -> None:
    """Print every read an end user can make of every object of the data set, on every branch of the scenario."""
    default_branch = registry.get_branch_from_registry()
    branches: dict[str, Branch] = {"main": default_branch}
    if scenario.migration_branch.name != default_branch.name:
        branches["migrating"] = scenario.migration_branch
        branches["sibling"] = scenario.forked_before
    else:
        branches["forked-before"] = scenario.forked_before
    if scenario.forked_after is not None:
        branches["forked-after"] = scenario.forked_after

    print(f"\n===== READ MATRIX: {title} =====")
    for role, branch in branches.items():
        for node_id, probe in _object_probes(scenario.data).items():
            with _collect_errors() as errors:
                reads = await _read_object(db=db, branch=branch, node_id=node_id, probe=probe)
            reads["logged_errors"] = errors.messages
            print(f"  [{role}] {probe.name}:")
            for read_name, value in reads.items():
                print(f"      {read_name}: {value}")


def _schema_path(kind: str, field_name: str | None = None) -> SchemaPath:
    if field_name is None:
        return SchemaPath(path_type=SchemaPathType.NODE, schema_kind=kind)
    return SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=field_name)


async def _update_kind(
    db: InfrahubDatabase, branch: Branch, spec: ShapeSpec, change: KindChange, at: Timestamp
) -> MigrationResult:
    """Apply the kind change to the branch's registered schema, then run its migration on the branch."""
    previous_branch_schema = registry.schema.get_schema_branch(name=branch.name)
    previous_schema = previous_branch_schema.get(name=spec.kind, duplicate=True)
    candidate = previous_branch_schema.duplicate()
    node_schema = candidate.get_node(name=spec.kind)

    if change is KindChange.RENAME:
        assert spec.renamed_name is not None
        candidate.delete(name=spec.kind)
        node_schema.name = spec.renamed_name
        field_name = "name"
    else:
        assert spec.generic_kind is not None
        node_schema.inherit_from = [*node_schema.inherit_from, spec.generic_kind]
        field_name = "inherit_from"

    candidate.set(name=node_schema.kind, schema=node_schema)
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()
    new_schema = candidate.get(name=node_schema.kind, duplicate=False)

    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=_schema_path(kind=new_schema.kind, field_name=field_name),
        derived_schemas=get_derived_schema_pairs(
            previous_schema_branch=previous_branch_schema,
            new_schema_branch=candidate,
            previous_node_schema=previous_schema,
            new_node_schema=new_schema,
        ),
    )
    return await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=branch)


async def _remove_kind(db: InfrahubDatabase, branch: Branch, spec: ShapeSpec, at: Timestamp) -> MigrationResult:
    """Drop the kind (and any relationship that points at it) from the branch's schema, then migrate."""
    previous_branch_schema: SchemaBranch = registry.schema.get_schema_branch(name=branch.name)
    previous_schema = previous_branch_schema.get(name=spec.kind, duplicate=True)
    candidate = previous_branch_schema.duplicate()
    candidate.delete(name=spec.kind)

    dropped_relationships: list[tuple[str, str]] = []
    for kind in candidate.node_names:
        node_schema = candidate.get(name=kind)
        pointing = [rel for rel in node_schema.relationships if rel.peer == spec.kind]
        if not pointing:
            continue
        dropped_relationships.extend((kind, rel.name) for rel in pointing)
        node_schema.relationships = [rel for rel in node_schema.relationships if rel.peer != spec.kind]
        candidate.set(name=kind, schema=node_schema)

    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()

    migration_input = MigrationInput(db=db, at=at)
    result = await NodeRemoveMigration(
        previous_node_schema=previous_schema, new_node_schema=None, schema_path=_schema_path(kind=spec.kind)
    ).execute(migration_input=migration_input, branch=branch)

    # The schema update pipeline pairs a peer-kind removal with the removal of every relationship to it.
    for kind, rel_name in dropped_relationships:
        rel_result = await NodeRelationshipRemoveMigration(
            previous_node_schema=previous_branch_schema.get(name=kind, duplicate=True),
            new_node_schema=candidate.get(name=kind, duplicate=True),
            schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=kind, field_name=rel_name),
        ).execute(migration_input=migration_input, branch=branch)
        result.errors.extend(rel_result.errors)
        result.nbr_migrations_executed += rel_result.nbr_migrations_executed
    return result


def _expected_after_kind_change(before: Snapshot, spec: ShapeSpec, change: KindChange) -> Snapshot:
    expected = {kind: {node_id: dict(fields) for node_id, fields in nodes.items()} for kind, nodes in before.items()}
    if change is KindChange.RENAME:
        expected[spec.renamed_kind] = expected.pop(spec.kind)
    else:
        for fields in expected[spec.kind].values():
            fields["label"] = LABEL_DEFAULT
    return expected


def _expected_after_removal(before: Snapshot, spec: ShapeSpec) -> Snapshot:
    expected = {kind: {node_id: dict(fields) for node_id, fields in nodes.items()} for kind, nodes in before.items()}
    expected.pop(spec.kind)
    if spec.kind == GADGET_KIND:
        for fields in expected[WIDGET_KIND].values():
            fields.pop("gadget")
    return expected


async def _kind_change_on_user_branch(db: InfrahubDatabase, shape: Shape, change: KindChange) -> Scenario:
    default_branch = registry.get_branch_from_registry()
    data = await _create_data(db=db, branch=default_branch)
    migration_branch = await create_branch(db=db, branch_name="runs-the-migration")
    sibling = await create_branch(db=db, branch_name="sibling-of-the-migration")
    before = {b.name: await _read_all(db=db, branch=b) for b in (default_branch, migration_branch, sibling)}
    await _edge_report(db=db, data=data, title=f"before {change.value} on user branch")

    result = await _update_kind(db=db, branch=migration_branch, spec=SHAPES[shape], change=change, at=Timestamp())
    await _edge_report(db=db, data=data, title=f"after {change.value} of {shape.value} on user branch")
    scenario = Scenario(
        data=data, migration_branch=migration_branch, forked_before=sibling, result=result, before=before
    )
    await _read_matrix(db=db, scenario=scenario, title=f"{change.value} of {shape.value} on user branch")
    return scenario


async def _kind_change_on_default_branch(db: InfrahubDatabase, shape: Shape, change: KindChange) -> Scenario:
    default_branch = registry.get_branch_from_registry()
    data = await _create_data(db=db, branch=default_branch)
    forked_before = await create_branch(db=db, branch_name="forked-before-the-migration")
    before = {b.name: await _read_all(db=db, branch=b) for b in (default_branch, forked_before)}
    await _edge_report(db=db, data=data, title=f"before {change.value} on default branch")

    result = await _update_kind(db=db, branch=default_branch, spec=SHAPES[shape], change=change, at=Timestamp())
    forked_after = await create_branch(db=db, branch_name="forked-after-the-migration")
    await _edge_report(db=db, data=data, title=f"after {change.value} of {shape.value} on default branch")
    scenario = Scenario(
        data=data,
        migration_branch=default_branch,
        forked_before=forked_before,
        forked_after=forked_after,
        result=result,
        before=before,
    )
    await _read_matrix(db=db, scenario=scenario, title=f"{change.value} of {shape.value} on default branch")
    return scenario


async def _removal_on_user_branch(db: InfrahubDatabase, shape: Shape) -> Scenario:
    default_branch = registry.get_branch_from_registry()
    data = await _create_data(db=db, branch=default_branch)
    migration_branch = await create_branch(db=db, branch_name="runs-the-migration")
    sibling = await create_branch(db=db, branch_name="sibling-of-the-migration")
    before = {b.name: await _read_all(db=db, branch=b) for b in (default_branch, migration_branch, sibling)}
    await _edge_report(db=db, data=data, title="before removal on user branch")

    result = await _remove_kind(db=db, branch=migration_branch, spec=SHAPES[shape], at=Timestamp())
    await _edge_report(db=db, data=data, title=f"after removal of {shape.value} on user branch")
    scenario = Scenario(
        data=data, migration_branch=migration_branch, forked_before=sibling, result=result, before=before
    )
    await _read_matrix(db=db, scenario=scenario, title=f"removal of {shape.value} on user branch")
    return scenario


async def _removal_on_default_branch(db: InfrahubDatabase, shape: Shape) -> Scenario:
    default_branch = registry.get_branch_from_registry()
    data = await _create_data(db=db, branch=default_branch)
    forked_before = await create_branch(db=db, branch_name="forked-before-the-migration")
    before = {b.name: await _read_all(db=db, branch=b) for b in (default_branch, forked_before)}
    await _edge_report(db=db, data=data, title="before removal on default branch")

    result = await _remove_kind(db=db, branch=default_branch, spec=SHAPES[shape], at=Timestamp())
    forked_after = await create_branch(db=db, branch_name="forked-after-the-migration")
    await _edge_report(db=db, data=data, title=f"after removal of {shape.value} on default branch")
    scenario = Scenario(
        data=data,
        migration_branch=default_branch,
        forked_before=forked_before,
        forked_after=forked_after,
        result=result,
        before=before,
    )
    await _read_matrix(db=db, scenario=scenario, title=f"removal of {shape.value} on default branch")
    return scenario


KIND_UPDATE_SHAPES = [Shape.AGNOSTIC_KIND, Shape.AWARE_KIND_WITH_AGNOSTIC_FIELDS]
REMOVAL_SHAPES = list(Shape)


@dataclass
class KindChangeCase:
    name: str
    change: KindChange
    shape: Shape


@dataclass
class ShapeCase:
    name: str
    shape: Shape


KIND_CHANGE_CASES = [
    KindChangeCase(name=f"{change.value}-{shape.value}", change=change, shape=shape)
    for change in KindChange
    for shape in KIND_UPDATE_SHAPES
]
INHERIT_FROM_CASES = [ShapeCase(name=shape.value, shape=shape) for shape in KIND_UPDATE_SHAPES]
REMOVAL_CASES = [ShapeCase(name=shape.value, shape=shape) for shape in REMOVAL_SHAPES]

kind_change_params = pytest.mark.parametrize("case", KIND_CHANGE_CASES, ids=lambda case: case.name)
removal_params = pytest.mark.parametrize("case", REMOVAL_CASES, ids=lambda case: case.name)


# ---------------------------------------------------------------------------
# Kind update on a user branch
# ---------------------------------------------------------------------------


@kind_change_params
async def test_kind_update_on_user_branch_leaves_default_and_sibling_reads_unchanged(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_user_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors

    after_default = await _read_all(db=db, branch=default_branch)
    after_sibling = await _read_all(db=db, branch=scenario.forked_before)
    _print_reads("after kind update on user branch", {default_branch.name: after_default, "sibling": after_sibling})

    assert after_default == scenario.before[default_branch.name], "the default branch still reads the old schema"
    assert after_sibling == scenario.before[scenario.forked_before.name], "the sibling still reads the old schema"


@pytest.mark.parametrize("case", INHERIT_FROM_CASES, ids=lambda case: case.name)
async def test_inherit_from_update_on_user_branch_is_not_seen_through_the_generic_elsewhere(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    """The default branch and the sibling declare the generic but no kind inheriting it, so it has no members."""
    shape = case.shape
    scenario = await _kind_change_on_user_branch(db=db, shape=shape, change=KindChange.INHERIT_FROM)
    assert not scenario.result.errors
    generic_kind = SHAPES[shape].generic_kind
    assert generic_kind is not None

    on_migration_branch = await NodeManager.query(db=db, schema=generic_kind, branch=scenario.migration_branch)
    on_default = await NodeManager.query(db=db, schema=generic_kind, branch=default_branch)
    on_sibling = await NodeManager.query(db=db, schema=generic_kind, branch=scenario.forked_before)
    _print_reads(
        f"members of {generic_kind}",
        {
            scenario.migration_branch.name: [node.id for node in on_migration_branch],
            default_branch.name: [node.id for node in on_default],
            "sibling": [node.id for node in on_sibling],
        },
    )

    assert len(on_migration_branch) == 1, "the branch that made the kind inherit the generic lists its node"
    assert on_default == []
    assert on_sibling == []


@kind_change_params
async def test_kind_update_on_user_branch_is_read_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_user_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors

    after = await _read_all(db=db, branch=scenario.migration_branch)
    _print_reads("after kind update on user branch", {scenario.migration_branch.name: after})

    expected = _expected_after_kind_change(
        before=scenario.before[scenario.migration_branch.name], spec=SHAPES[shape], change=change
    )
    assert after == expected


@kind_change_params
async def test_agnostic_attribute_updated_after_kind_update_is_read_on_user_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_user_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors

    node_id = scenario.data.beacon_id if shape is Shape.AGNOSTIC_KIND else scenario.data.widget_id
    node = await NodeManager.get_one(db=db, id=node_id, branch=scenario.migration_branch, raise_on_error=True)
    node.get_attribute(name="serial").value = 999
    await node.save(db=db)

    reread = await NodeManager.get_one(db=db, id=node_id, branch=scenario.migration_branch, raise_on_error=True)
    on_default = await _safe_read(db=db, branch=default_branch)
    _print_reads(
        "after agnostic attribute update on user branch",
        {scenario.migration_branch.name: await _read_all(db=db, branch=scenario.migration_branch), "main": on_default},
    )
    assert reread.get_attribute(name="serial").value == 999


@kind_change_params
async def test_kind_update_on_user_branch_keeps_the_graph_valid(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_user_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors
    await verify_graph(db=db)


# ---------------------------------------------------------------------------
# Kind update on the default branch
# ---------------------------------------------------------------------------


@kind_change_params
async def test_kind_update_on_default_branch_is_read_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_default_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors

    after = await _read_all(db=db, branch=default_branch)
    _print_reads("after kind update on default branch", {default_branch.name: after})
    assert after == _expected_after_kind_change(
        before=scenario.before[default_branch.name], spec=SHAPES[shape], change=change
    )


@kind_change_params
async def test_kind_update_on_default_branch_is_read_on_a_later_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_default_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors
    assert scenario.forked_after is not None

    after = await _read_all(db=db, branch=scenario.forked_after)
    _print_reads("after kind update on default branch", {scenario.forked_after.name: after})
    assert after == _expected_after_kind_change(
        before=scenario.before[default_branch.name], spec=SHAPES[shape], change=change
    )


@kind_change_params
async def test_kind_update_on_default_branch_as_seen_from_an_earlier_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    """Records what a branch still declaring the old schema reads; the desired outcome is not settled."""
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_default_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors

    after = await _safe_read(db=db, branch=scenario.forked_before)
    _print_reads(
        f"CHARACTERIZATION {change.value} {shape.value}: earlier branch after default-branch kind update",
        {"before": scenario.before[scenario.forked_before.name], "after": after},
    )


@kind_change_params
async def test_kind_update_on_default_branch_keeps_the_graph_valid(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: KindChangeCase
) -> None:
    change, shape = case.change, case.shape
    scenario = await _kind_change_on_default_branch(db=db, shape=shape, change=change)
    assert not scenario.result.errors
    await verify_graph(db=db)


# ---------------------------------------------------------------------------
# Node removal on a user branch
# ---------------------------------------------------------------------------


@removal_params
async def test_removal_on_user_branch_leaves_default_and_sibling_reads_unchanged(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_user_branch(db=db, shape=shape)
    assert not scenario.result.errors

    after_default = await _read_all(db=db, branch=default_branch)
    after_sibling = await _read_all(db=db, branch=scenario.forked_before)
    _print_reads("after removal on user branch", {default_branch.name: after_default, "sibling": after_sibling})

    assert after_default == scenario.before[default_branch.name], "the default branch still reads the old schema"
    assert after_sibling == scenario.before[scenario.forked_before.name], "the sibling still reads the old schema"


@removal_params
async def test_removal_on_user_branch_is_read_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_user_branch(db=db, shape=shape)
    assert not scenario.result.errors

    after = await _read_all(db=db, branch=scenario.migration_branch)
    _print_reads("after removal on user branch", {scenario.migration_branch.name: after})
    assert after == _expected_after_removal(before=scenario.before[scenario.migration_branch.name], spec=SHAPES[shape])

    removed_id = {
        Shape.AGNOSTIC_KIND: scenario.data.beacon_id,
        Shape.AWARE_KIND_WITH_AGNOSTIC_FIELDS: scenario.data.widget_id,
        Shape.AWARE_PEER_OF_AGNOSTIC_RELATIONSHIP: scenario.data.gadget_id,
    }[shape]
    assert await NodeManager.get_one(db=db, id=removed_id, branch=scenario.migration_branch) is None


@removal_params
async def test_removal_on_user_branch_keeps_the_graph_valid(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_user_branch(db=db, shape=shape)
    assert not scenario.result.errors
    await verify_graph(db=db)


# ---------------------------------------------------------------------------
# Node removal on the default branch
# ---------------------------------------------------------------------------


@removal_params
async def test_removal_on_default_branch_is_read_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_default_branch(db=db, shape=shape)
    assert not scenario.result.errors

    after = await _read_all(db=db, branch=default_branch)
    _print_reads("after removal on default branch", {default_branch.name: after})
    assert after == _expected_after_removal(before=scenario.before[default_branch.name], spec=SHAPES[shape])


@removal_params
async def test_removal_on_default_branch_is_read_on_a_later_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_default_branch(db=db, shape=shape)
    assert not scenario.result.errors
    assert scenario.forked_after is not None

    after = await _read_all(db=db, branch=scenario.forked_after)
    _print_reads("after removal on default branch", {scenario.forked_after.name: after})
    assert after == _expected_after_removal(before=scenario.before[default_branch.name], spec=SHAPES[shape])


@removal_params
async def test_removal_on_default_branch_as_seen_from_an_earlier_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    """Records what a branch still declaring the removed kind reads; the desired outcome is not settled."""
    shape = case.shape
    scenario = await _removal_on_default_branch(db=db, shape=shape)
    assert not scenario.result.errors

    after = await _safe_read(db=db, branch=scenario.forked_before)
    _print_reads(
        f"CHARACTERIZATION remove {shape.value}: earlier branch after default-branch removal",
        {"before": scenario.before[scenario.forked_before.name], "after": after},
    )


@removal_params
async def test_removal_on_default_branch_keeps_the_graph_valid(
    db: InfrahubDatabase, default_branch: Branch, agnostic_node_schema: None, case: ShapeCase
) -> None:
    shape = case.shape
    scenario = await _removal_on_default_branch(db=db, shape=shape)
    assert not scenario.result.errors
    await verify_graph(db=db)
