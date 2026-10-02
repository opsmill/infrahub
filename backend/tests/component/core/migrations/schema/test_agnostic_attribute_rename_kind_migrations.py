"""Renaming a branch-agnostic attribute, or changing its kind, keeps every branch reading its value.

A branch-agnostic value lives on the global branch, which every branch reads, while the schema
change that renames the attribute or changes its kind belongs to one branch. Every other branch must
go on reading the value under its own schema, the migrating branch must read it under the new one,
and a later update of the value must stay visible from every branch that declares the attribute.

Each scenario runs for a branch-agnostic attribute of a branch-aware kind and for an attribute of a
branch-agnostic kind, on the default branch and on a user branch.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.attribute_kind_update import AttributeKindUpdateMigration
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.agnostic_edges import TEST_ACTOR_ID
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

WIDGET_KIND = "AgnosticrenWidget"
BEACON_KIND = "AgnosticrenBeacon"
OLD_NAME = "note"
NEW_NAME = "remark"

AGNOSTICREN_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Widget",
            namespace="Agnosticren",
            branch=BranchSupportType.AWARE,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name=OLD_NAME, kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
            ],
        ),
        # The attribute inherits branch-agnostic support from its kind.
        NodeSchema(
            name="Beacon",
            namespace="Agnosticren",
            branch=BranchSupportType.AGNOSTIC,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name=OLD_NAME, kind="Text", optional=True),
            ],
        ),
    ]
)


@dataclass(frozen=True)
class FieldEdge:
    edge_type: str
    branch: str
    status: str
    is_open: bool
    attribute_uuid: str
    value: Any
    indexed: bool | None


@dataclass(frozen=True)
class EntityShape:
    name: str
    kind: str


SHAPES = [
    EntityShape(name="agnostic-attribute-of-aware-kind", kind=WIDGET_KIND),
    EntityShape(name="attribute-of-agnostic-kind", kind=BEACON_KIND),
]


@pytest.fixture
async def agnosticren_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Registered over the core models so the GraphQL schema the read matrix queries can be built."""
    registry.schema.register_schema(schema=AGNOSTICREN_SCHEMA, branch=default_branch.name)


@pytest.fixture(autouse=True)
async def verify_graph_invariants(db: InfrahubDatabase, default_branch: Branch) -> AsyncIterator[None]:
    """Check the whole-graph invariants after every test in this module."""
    yield
    await verify_graph(db=db)


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, name: str, note: str) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    values: dict[str, Any] = {"name": name, OLD_NAME: note}
    await node.new(db=db, **values)
    await node.save(db=db)
    return node


async def _read(db: InfrahubDatabase, node_id: str, branch: Branch, attribute_name: str) -> Any:
    """The value `branch` reads for the attribute through the node manager, or a marker when it cannot."""
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
    if node is None:
        return "<node missing>"
    if attribute_name not in node.get_schema().attribute_names:
        return "<attribute not in schema>"
    return node.get_attribute(name=attribute_name).value


async def _update(db: InfrahubDatabase, node_id: str, branch: Branch, attribute_name: str, value: str) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    node.get_attribute(name=attribute_name).value = value
    await node.save(db=db, user_id=TEST_ACTOR_ID)


async def _field_edges(db: InfrahubDatabase, node_id: str) -> list[FieldEdge]:
    """Every owning and value edge of the node's old- and new-named attribute vertices, on any branch."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute)
        WHERE a.name IN $names
        WITH DISTINCT a
        MATCH (n:Node)-[e:HAS_ATTRIBUTE]->(a)
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status, e.to IS NULL AS is_open,
               a.name + ":" + a.uuid AS attribute_uuid, NULL AS value, NULL AS indexed
        UNION ALL
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute)
        WHERE a.name IN $names
        WITH DISTINCT a
        MATCH (a)-[e:HAS_VALUE]->(av:AttributeValue)
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status, e.to IS NULL AS is_open,
               a.name + ":" + a.uuid AS attribute_uuid, av.value AS value,
               "AttributeValueIndexed" IN labels(av) AS indexed
        """,
        params={"node_id": node_id, "names": [OLD_NAME, NEW_NAME]},
    )
    return sorted(
        (FieldEdge(**dict(result)) for result in results),
        key=lambda edge: (edge.attribute_uuid, edge.edge_type, edge.branch, edge.status),
    )


def _dump(label: str, edges: list[FieldEdge]) -> None:
    print(f"--- {label}")
    for edge in edges:
        print(f"    {edge}")


async def _rename_on(db: InfrahubDatabase, branch: Branch, kind: str) -> MigrationResult:
    """Rename the attribute in `branch`'s registered schema, then run the rename migration there."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    attribute_id = str(uuid.uuid4())
    previous_node = schema_branch.get(name=kind)
    previous_node.get_attribute(name=OLD_NAME).id = attribute_id

    candidate = schema_branch.duplicate()
    node_schema = candidate.get(name=kind)
    renamed = node_schema.get_attribute(name=OLD_NAME)
    renamed.id = attribute_id
    renamed.name = NEW_NAME
    candidate.set(name=kind, schema=node_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()

    migration = AttributeNameUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=node_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=NEW_NAME),
    )
    return await migration.execute(
        migration_input=MigrationInput(db=db, at=Timestamp(), user_id=TEST_ACTOR_ID), branch=branch
    )


async def _change_kind_on(db: InfrahubDatabase, branch: Branch, kind: str) -> MigrationResult:
    """Turn the indexed Text attribute into a non-indexed TextArea on `branch`, then run its migration."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema_branch.get(name=kind)

    candidate = schema_branch.duplicate()
    node_schema = candidate.get(name=kind)
    node_schema.get_attribute(name=OLD_NAME).kind = "TextArea"
    candidate.set(name=kind, schema=node_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()

    migration = AttributeKindUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=node_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=OLD_NAME),
    )
    return await migration.execute(
        migration_input=MigrationInput(db=db, at=Timestamp(), user_id=TEST_ACTOR_ID), branch=branch
    )


def _raised(exc: Exception) -> str:
    return f"raised {type(exc).__name__}: {exc}"


def _logged_errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    messages = []
    for record in caplog.records:
        if record.levelno < logging.ERROR:
            continue
        message = record.msg.get("event", record.msg) if isinstance(record.msg, dict) else record.getMessage()
        messages.append(str(message))
    return messages


async def _user_view(
    db: InfrahubDatabase, branch: Branch, node_id: str, kind: str, caplog: pytest.LogCaptureFixture
) -> dict[str, Any]:
    """What a user on `branch` gets for the object through the manager and GraphQL, failures included."""
    attribute_names = registry.schema.get_schema_branch(name=branch.name).get(name=kind).attribute_names
    view: dict[str, Any] = {}
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        # Any failure is part of what the user sees, so it is recorded rather than raised.
        try:
            node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
            if node is None:
                view["get_one"] = None
            else:
                view["get_one"] = {
                    "kind": node.get_kind(),
                    **{name: node.get_attribute(name=name).value for name in attribute_names},
                }
        except Exception as exc:
            view["get_one"] = _raised(exc)

        try:
            listed = [item for item in await NodeManager.query(db=db, schema=kind, branch=branch) if item.id == node_id]
            view["query"] = (
                "not listed"
                if not listed
                else [{name: item.get_attribute(name=name).value for name in attribute_names} for item in listed]
            )
        except Exception as exc:
            view["query"] = _raised(exc)

        fields = " ".join(f"{name} {{ value }}" for name in attribute_names)
        source = f"query ($ids: [ID]) {{ {kind}(ids: $ids) {{ count edges {{ node {{ id {fields} }} }} }} }}"
        try:
            gql_params = await prepare_graphql_params(db=db, branch=branch)
            result = await graphql(
                schema=gql_params.schema,
                source=source,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"ids": [node_id]},
            )
            view["graphql"] = {
                "data": result.data,
                "errors": [error.message for error in result.errors] if result.errors else None,
            }
        except Exception as exc:
            view["graphql"] = _raised(exc)

    view["logged_errors"] = _logged_errors(caplog)
    return view


async def _read_matrix(
    db: InfrahubDatabase, readers: dict[str, Branch], node_id: str, kind: str, caplog: pytest.LogCaptureFixture
) -> dict[str, dict[str, Any]]:
    return {
        label: await _user_view(db=db, branch=branch, node_id=node_id, kind=kind, caplog=caplog)
        for label, branch in readers.items()
    }


def _print_matrix(label: str, matrix: dict[str, dict[str, Any]]) -> None:
    print(f"=== READ MATRIX: {label}")
    for reader, view in matrix.items():
        print(f"  [{reader}]")
        for column, cell in view.items():
            print(f"      {column}: {cell}")


async def _try_update(
    db: InfrahubDatabase, node_id: str, branch: Branch, attribute_name: str, value: str
) -> str | None:
    """Run the follow-up value update, returning the failure instead of raising so every read still runs."""
    try:
        await _update(db=db, node_id=node_id, branch=branch, attribute_name=attribute_name, value=value)
    except Exception as exc:
        return _raised(exc)
    return None


@pytest.mark.parametrize("shape", SHAPES, ids=lambda shape: shape.name)
async def test_renaming_on_a_user_branch_leaves_other_branches_reading_the_old_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnosticren_schema: None,
    shape: EntityShape,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the renaming branch sees the new name, and the shared value stays shared after an update."""
    kind = shape.kind
    node = await _create(db=db, branch=default_branch, kind=kind, name="renamed-on-a-branch", note="first")
    sibling = await create_branch(db=db, branch_name="rename-sibling")
    branch = await create_branch(db=db, branch_name="rename-branch")

    result = await _rename_on(db=db, branch=branch, kind=kind)
    forked_after = await create_branch(db=db, branch_name="rename-forked-after")
    readers = {"main": default_branch, "sibling": sibling, "branch": branch, "forked_after": forked_after}
    _dump("after rename on user branch", await _field_edges(db=db, node_id=node.id))

    matrix_after_migration = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    after_migration = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME),
        "sibling": await _read(db=db, node_id=node.id, branch=sibling, attribute_name=OLD_NAME),
        "branch": await _read(db=db, node_id=node.id, branch=branch, attribute_name=NEW_NAME),
    }

    update_error = await _try_update(db=db, node_id=node.id, branch=branch, attribute_name=NEW_NAME, value="second")
    _dump("after update from user branch", await _field_edges(db=db, node_id=node.id))

    matrix_after_update = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    after_update = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME),
        "sibling": await _read(db=db, node_id=node.id, branch=sibling, attribute_name=OLD_NAME),
        "branch": await _read(db=db, node_id=node.id, branch=branch, attribute_name=NEW_NAME),
    }

    _print_matrix("after migration", matrix_after_migration)
    _print_matrix(f"after update from branch (update error: {update_error})", matrix_after_update)
    print(f"after migration: {after_migration}")
    print(f"after update: {after_update}")

    assert not result.errors
    assert after_migration == {"main": "first", "sibling": "first", "branch": "first"}
    assert update_error is None
    assert after_update == {"main": "second", "sibling": "second", "branch": "second"}


@pytest.mark.parametrize("shape", SHAPES, ids=lambda shape: shape.name)
async def test_renaming_on_the_default_branch_keeps_the_value_readable_and_updatable(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnosticren_schema: None,
    shape: EntityShape,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The default branch and later forks read the renamed attribute and see a later update of it."""
    kind = shape.kind
    node = await _create(db=db, branch=default_branch, kind=kind, name="renamed-on-main", note="first")
    forked_before = await create_branch(db=db, branch_name="rename-forked-before")

    result = await _rename_on(db=db, branch=default_branch, kind=kind)
    forked_after_migration = await create_branch(db=db, branch_name="rename-forked-after-migration")
    readers = {"main": default_branch, "forked_before": forked_before, "forked_after_migration": forked_after_migration}
    _dump("after rename on main", await _field_edges(db=db, node_id=node.id))

    matrix_after_migration = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    on_main = await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=NEW_NAME)

    update_error = await _try_update(
        db=db, node_id=node.id, branch=default_branch, attribute_name=NEW_NAME, value="second"
    )
    forked_after = await create_branch(db=db, branch_name="rename-forked-after")
    _dump("after update from main", await _field_edges(db=db, node_id=node.id))

    matrix_after_update = await _read_matrix(
        db=db, readers={**readers, "forked_after_update": forked_after}, node_id=node.id, kind=kind, caplog=caplog
    )
    after_update = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=NEW_NAME),
        "forked_after": await _read(db=db, node_id=node.id, branch=forked_after, attribute_name=NEW_NAME),
    }

    _print_matrix("after migration", matrix_after_migration)
    _print_matrix(f"after update from main (update error: {update_error})", matrix_after_update)
    print(f"after update: {after_update}")

    assert not result.errors
    assert on_main == "first"
    assert update_error is None
    assert after_update == {"main": "second", "forked_after": "second"}


@pytest.mark.parametrize("shape", SHAPES, ids=lambda shape: shape.name)
async def test_changing_the_kind_on_a_user_branch_leaves_other_branches_reading_the_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnosticren_schema: None,
    shape: EntityShape,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Moving the value to a non-indexed vertex on one branch must not hide it from any other branch."""
    kind = shape.kind
    node = await _create(db=db, branch=default_branch, kind=kind, name="rekinded-on-a-branch", note="first")
    sibling = await create_branch(db=db, branch_name="kind-sibling")
    branch = await create_branch(db=db, branch_name="kind-branch")

    result = await _change_kind_on(db=db, branch=branch, kind=kind)
    forked_after = await create_branch(db=db, branch_name="kind-forked-after")
    readers = {"main": default_branch, "sibling": sibling, "branch": branch, "forked_after": forked_after}
    _dump("after kind change on user branch", await _field_edges(db=db, node_id=node.id))

    matrix_after_migration = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    after_migration = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME),
        "sibling": await _read(db=db, node_id=node.id, branch=sibling, attribute_name=OLD_NAME),
        "branch": await _read(db=db, node_id=node.id, branch=branch, attribute_name=OLD_NAME),
    }

    update_error = await _try_update(db=db, node_id=node.id, branch=branch, attribute_name=OLD_NAME, value="second")
    _dump("after update from user branch", await _field_edges(db=db, node_id=node.id))

    matrix_after_update = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    after_update = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME),
        "sibling": await _read(db=db, node_id=node.id, branch=sibling, attribute_name=OLD_NAME),
        "branch": await _read(db=db, node_id=node.id, branch=branch, attribute_name=OLD_NAME),
    }

    _print_matrix("after migration", matrix_after_migration)
    _print_matrix(f"after update from branch (update error: {update_error})", matrix_after_update)
    print(f"after migration: {after_migration}")
    print(f"after update: {after_update}")

    assert not result.errors
    assert after_migration == {"main": "first", "sibling": "first", "branch": "first"}
    assert update_error is None
    assert after_update == {"main": "second", "sibling": "second", "branch": "second"}


@pytest.mark.parametrize("shape", SHAPES, ids=lambda shape: shape.name)
async def test_changing_the_kind_on_the_default_branch_keeps_the_value_readable_and_updatable(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnosticren_schema: None,
    shape: EntityShape,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The default branch and later forks read the value after the kind change and see a later update."""
    kind = shape.kind
    node = await _create(db=db, branch=default_branch, kind=kind, name="rekinded-on-main", note="first")
    forked_before = await create_branch(db=db, branch_name="kind-forked-before")

    result = await _change_kind_on(db=db, branch=default_branch, kind=kind)
    forked_after_migration = await create_branch(db=db, branch_name="kind-forked-after-migration")
    readers = {"main": default_branch, "forked_before": forked_before, "forked_after_migration": forked_after_migration}
    _dump("after kind change on main", await _field_edges(db=db, node_id=node.id))

    matrix_after_migration = await _read_matrix(db=db, readers=readers, node_id=node.id, kind=kind, caplog=caplog)
    on_main = await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME)

    update_error = await _try_update(
        db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME, value="second"
    )
    forked_after = await create_branch(db=db, branch_name="kind-forked-after")
    _dump("after update from main", await _field_edges(db=db, node_id=node.id))

    matrix_after_update = await _read_matrix(
        db=db, readers={**readers, "forked_after_update": forked_after}, node_id=node.id, kind=kind, caplog=caplog
    )
    after_update = {
        "main": await _read(db=db, node_id=node.id, branch=default_branch, attribute_name=OLD_NAME),
        "forked_after": await _read(db=db, node_id=node.id, branch=forked_after, attribute_name=OLD_NAME),
    }

    _print_matrix("after migration", matrix_after_migration)
    _print_matrix(f"after update from main (update error: {update_error})", matrix_after_update)
    print(f"after update: {after_update}")

    assert not result.errors
    assert on_main == "first"
    assert update_error is None
    assert after_update == {"main": "second", "forked_after": "second"}
