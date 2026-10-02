"""Additive schema migrations on branch-agnostic attributes, run on the default branch and on a user branch.

A schema change made on a user branch exists only on that branch until it is merged, so the data a
migration writes for it must stay readable from that branch alone: the default branch and any sibling
branch keep reading exactly what they read before, and no edge the migration wrote is visible from them.
A schema change made on the default branch is read by the default branch and by every branch forked
after it.

The tests prefixed `test_characterize_` assert nothing about the outcome; they print what the graph and
the node manager return for a case whose expected semantics are still open.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
)
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.schema.node_uniqueness_constraints_update import (
    NodeUniquenessConstraintsUpdateMigration,
)
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, SchemaMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.helpers.agnostic_edges import TEST_ACTOR_ID
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

WIDGET_KIND = "AgnosticaddWidget"
BEACON_KIND = "AgnosticaddBeacon"
WIDGET_PROFILE_KIND = f"Profile{WIDGET_KIND}"
WIDGET_TEMPLATE_KIND = f"Template{WIDGET_KIND}"
BEACON_PROFILE_KIND = f"Profile{BEACON_KIND}"

COLOR_ATTRIBUTE_ID = "1f0a6c1e-0000-4000-8000-00000000c010"
CODE_ATTRIBUTE_ID = "1f0a6c1e-0000-4000-8000-00000000c0de"

WIDGET = NodeSchema(
    name="Widget",
    namespace="Agnosticadd",
    branch=BranchSupportType.AWARE,
    generate_profile=True,
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(
            id=COLOR_ATTRIBUTE_ID,
            name="color",
            kind="Text",
            optional=True,
            default_value="blue",
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

# A kind that is itself branch-agnostic, so every attribute it declares is branch-agnostic too.
BEACON = NodeSchema(
    name="Beacon",
    namespace="Agnosticadd",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(id=CODE_ATTRIBUTE_ID, name="code", kind="Text", optional=True, default_value="B-0"),
    ],
)


def _register_schema(
    default_branch: Branch,
    color_read_only: bool = False,
    code_unique: bool = False,
    widget_uniqueness_constraints: list[list[str]] | None = None,
) -> None:
    widget = deepcopy(WIDGET)
    widget.get_attribute(name="color").read_only = color_read_only
    widget.uniqueness_constraints = widget_uniqueness_constraints
    beacon = deepcopy(BEACON)
    beacon.get_attribute(name="code").unique = code_unique
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
        branch=default_branch.name,
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[widget, beacon]), branch=default_branch.name)


@pytest.fixture(autouse=True)
async def core_models(register_core_models_schema: SchemaBranch) -> None:
    """The core models carry the generics the GraphQL schema of a profile or template is built from."""


@pytest.fixture(autouse=True)
async def verify_graph_invariants(db: InfrahubDatabase, default_branch: Branch) -> AsyncIterator[None]:
    """Check the whole-graph invariants after every test in this module."""
    yield
    await verify_graph(db=db)


# -----------------------------------------------------------------------------
# Builders and readers
# -----------------------------------------------------------------------------


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, **values: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **values)
    await node.save(db=db)
    return node


async def _read(db: InfrahubDatabase, node_id: str, branch: Branch) -> dict[str, Any]:
    """Every attribute value the node manager returns for the node under the branch's own schema."""
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
    assert node is not None, f"{node_id} is not readable on {branch.name}"
    return {name: node.get_attribute(name=name).value for name in node.get_schema().attribute_names}


@dataclass(frozen=True, order=True)
class TouchedEdge:
    edge_type: str
    branch: str
    status: str
    change: str


async def _edges_touched_at(db: InfrahubDatabase, at: Timestamp) -> list[TouchedEdge]:
    """Every edge in the graph opened or closed at `at`, which is the migration's own write time."""
    results = await db.execute_query(
        query="""
        MATCH ()-[e]->()
        WHERE e.from = $at OR e.to = $at
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               CASE WHEN e.from = $at THEN "opened" ELSE "closed" END AS change
        """,
        params={"at": at.to_string()},
    )
    return sorted(TouchedEdge(**dict(result)) for result in results)


def _visible_from(edges: list[TouchedEdge], branch: Branch) -> list[TouchedEdge]:
    return [edge for edge in edges if edge.branch in {branch.name, GLOBAL_BRANCH_NAME}]


async def _raw_attribute_edges(db: InfrahubDatabase, node_id: str, attribute_name: str) -> list[tuple]:
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[owning:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        OPTIONAL MATCH (a)-[e:HAS_VALUE]->(v:AttributeValue)
        RETURN owning.branch AS owning_branch, owning.status AS owning_status, owning.to IS NULL AS owning_open,
               e.branch AS value_branch, e.status AS value_status, e.to IS NULL AS value_open, v.value AS value
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return sorted(tuple(result.values()) for result in results)


def _print(label: str, value: Any) -> None:
    print(f"[characterization] {label}: {value}")


# -----------------------------------------------------------------------------
# Schema change and migration drivers
# -----------------------------------------------------------------------------


def _stage_schema_change(
    branch: Branch, kind: str, change: Callable[[MainSchemaTypes], None]
) -> tuple[MainSchemaTypes, MainSchemaTypes]:
    """Register the changed schema on `branch` alone, with its profiles and templates regenerated."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get(name=kind)
    candidate = schema_branch.duplicate()
    changed = candidate.get(name=kind)
    change(changed)
    candidate.set(name=kind, schema=changed)
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    # The GraphQL schema is cached by the branch's recorded schema hash, which a schema update refreshes.
    for registered in {id(branch): branch, id(registry.branch[branch.name]): registry.branch[branch.name]}.values():
        registered.update_schema_hash()
    return previous, candidate.get(name=kind)


async def _execute(
    db: InfrahubDatabase, branch: Branch, migration: SchemaMigration
) -> tuple[Timestamp, MigrationResult]:
    at = Timestamp()
    result = await migration.execute(migration_input=MigrationInput(db=db, at=at, user_id=TEST_ACTOR_ID), branch=branch)
    assert not result.errors
    return at, result


def _append_attribute(attribute: AttributeSchema) -> Callable[[MainSchemaTypes], None]:
    def change(schema: MainSchemaTypes) -> None:
        schema.attributes.append(deepcopy(attribute))

    return change


def _set_attribute_property(attribute_name: str, **properties: Any) -> Callable[[MainSchemaTypes], None]:
    def change(schema: MainSchemaTypes) -> None:
        attribute = schema.get_attribute(name=attribute_name)
        for name, value in properties.items():
            setattr(attribute, name, value)
        if properties.get("unique") is False and schema.uniqueness_constraints:
            # Processing turns a unique attribute into a single-field constraint that would otherwise restore it.
            schema.uniqueness_constraints = [
                constraint for constraint in schema.uniqueness_constraints if constraint != [f"{attribute_name}__value"]
            ] or None

    return change


def _set_uniqueness_constraints(constraints: list[list[str]] | None) -> Callable[[MainSchemaTypes], None]:
    def change(schema: MainSchemaTypes) -> None:
        schema.uniqueness_constraints = constraints

    return change


async def _add_attribute(
    db: InfrahubDatabase, branch: Branch, kind: str, attribute: AttributeSchema
) -> tuple[Timestamp, MigrationResult]:
    previous, new = _stage_schema_change(branch=branch, kind=kind, change=_append_attribute(attribute))
    migration = NodeAttributeAddMigration(
        previous_node_schema=previous,
        new_node_schema=new,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=attribute.name),
    )
    return await _execute(db=db, branch=branch, migration=migration)


async def _update_attribute(
    db: InfrahubDatabase, branch: Branch, kind: str, attribute_name: str, **properties: Any
) -> tuple[Timestamp, MigrationResult]:
    previous, new = _stage_schema_change(
        branch=branch, kind=kind, change=_set_attribute_property(attribute_name, **properties)
    )
    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=previous,
        new_node_schema=new,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=attribute_name),
    )
    return await _execute(db=db, branch=branch, migration=migration)


async def _update_uniqueness_constraints(
    db: InfrahubDatabase, branch: Branch, kind: str, constraints: list[list[str]] | None
) -> tuple[Timestamp, MigrationResult]:
    previous, new = _stage_schema_change(branch=branch, kind=kind, change=_set_uniqueness_constraints(constraints))
    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=new,
        schema_path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind=kind,
            field_name="uniqueness_constraints",
            property_name="uniqueness_constraints",
        ),
    )
    return await _execute(db=db, branch=branch, migration=migration)


# -----------------------------------------------------------------------------
# Shared scenario assertions
# -----------------------------------------------------------------------------


@dataclass
class Forks:
    """The branches around a user-branch migration: the one migrating and a sibling forked alongside it."""

    migrating: Branch
    sibling: Branch


async def _fork(db: InfrahubDatabase) -> Forks:
    sibling = await create_branch(db=db, branch_name="agnostic-add-sibling")
    migrating = await create_branch(db=db, branch_name="agnostic-add-migrating")
    return Forks(migrating=migrating, sibling=sibling)


async def _snapshot(db: InfrahubDatabase, node_ids: list[str], branches: list[Branch]) -> dict[tuple[str, str], dict]:
    return {
        (branch.name, node_id): await _read(db=db, node_id=node_id, branch=branch)
        for branch in branches
        for node_id in node_ids
    }


async def _assert_unchanged_outside(
    db: InfrahubDatabase,
    before: dict[tuple[str, str], dict],
    node_ids: list[str],
    branches: list[Branch],
    attribute_name: str,
    at: Timestamp,
    default_branch: Branch,
) -> None:
    """The branches that did not migrate read what they read before, and no migrated edge reaches them."""
    after = await _snapshot(db=db, node_ids=node_ids, branches=branches)
    assert after == before
    for values in after.values():
        assert attribute_name not in values

    touched = await _edges_touched_at(db=db, at=at)
    assert touched, "the migration wrote nothing at its own timestamp"
    assert _visible_from(touched, default_branch) == [], (
        "an edge the user-branch migration wrote or closed is visible from the default branch before any merge"
    )


async def _print_old_branch(
    db: InfrahubDatabase, label: str, branch: Branch, node_ids: list[str], attribute_name: str, at: Timestamp
) -> None:
    for node_id in node_ids:
        _print(
            f"{label}: NodeManager on pre-migration branch {branch.name} for {node_id}",
            await _read(db, node_id, branch),
        )
        _print(
            f"{label}: raw {attribute_name} edges of {node_id}", await _raw_attribute_edges(db, node_id, attribute_name)
        )
    _print(f"{label}: edges touched at the migration time", await _edges_touched_at(db=db, at=at))


# -----------------------------------------------------------------------------
# End-user read matrix
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Subject:
    """One object a user might read: its role in the scenario, its kind, and whether a profile is applied to it."""

    role: str
    kind: str
    node_id: str
    profiled: bool = False


async def _record(read: Awaitable[str]) -> str:
    try:
        return await read
    # The matrix records every read outcome, so any failure is kept as a cell value rather than raised.
    except Exception as exc:
        return f"raised {type(exc).__name__}: {exc}"


def _logged_errors(caplog: pytest.LogCaptureFixture, since: int) -> list[str]:
    events = []
    for record in caplog.records[since:]:
        if record.levelno < logging.ERROR:
            continue
        message = record.msg
        events.append(str(message.get("event")) if isinstance(message, dict) else record.getMessage())
    return events


async def _get_one_cell(db: InfrahubDatabase, branch: Branch, subject: Subject) -> str:
    node = await NodeManager.get_one(db=db, id=subject.node_id, branch=branch)
    if node is None:
        return "None"
    return repr({name: node.get_attribute(name=name).value for name in node.get_schema().attribute_names})


async def _query_cell(db: InfrahubDatabase, branch: Branch, subject: Subject) -> str:
    nodes = await NodeManager.query(db=db, schema=subject.kind, branch=branch)
    matches = [node for node in nodes if node.id == subject.node_id]
    if not matches:
        return f"listed=False (of {len(nodes)})"
    node = matches[0]
    values = {name: node.get_attribute(name=name).value for name in node.get_schema().attribute_names}
    return f"listed=True {values}"


def _attribute_state(node: Node, attribute_name: str) -> tuple[Any, bool | None, bool]:
    attribute = node.get_attribute(name=attribute_name)
    return (attribute.value, attribute.is_default, attribute.is_from_profile)


async def _profile_applied_cell(db: InfrahubDatabase, branch: Branch, subject: Subject, attribute_name: str) -> str:
    if not subject.profiled:
        return "n/a"
    node = await NodeManager.get_one(db=db, id=subject.node_id, branch=branch)
    if node is None:
        return "node not readable"
    if attribute_name not in node.get_schema().attribute_names:
        return f"{attribute_name} not in schema"
    stored = _attribute_state(node=node, attribute_name=attribute_name)
    changed = await NodeProfilesApplier(db=db, branch=branch).apply_profiles(node=node)
    reapplied = _attribute_state(node=node, attribute_name=attribute_name)
    return f"stored(value,is_default,from_profile)={stored} on_reapply={reapplied} reapply_changes={changed}"


async def _graphql_cell(db: InfrahubDatabase, branch: Branch, subject: Subject) -> str:
    schema = registry.schema.get_schema_branch(name=branch.name).get(name=subject.kind, duplicate=False)
    fields = " ".join(f"{name} {{ value }}" for name in schema.attribute_names)
    query = f'query {{ {subject.kind}(ids: ["{subject.node_id}"]) {{ count edges {{ node {{ id {fields} }} }} }} }}'
    params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(schema=params.schema, source=query, context_value=params.context, root_value=None)
    errors = [error.message for error in result.errors or []]
    return f"data={result.data} errors={errors}"


async def _read_matrix(
    db: InfrahubDatabase,
    caplog: pytest.LogCaptureFixture,
    label: str,
    branches: list[tuple[str, Branch]],
    subjects: list[Subject],
    attribute_name: str,
) -> None:
    """Print what a user reading each object gets on each branch, through every read path."""
    for role, branch in branches:
        for subject in subjects:
            since = len(caplog.records)
            get_one = await _record(_get_one_cell(db=db, branch=branch, subject=subject))
            query = await _record(_query_cell(db=db, branch=branch, subject=subject))
            applied = await _record(
                _profile_applied_cell(db=db, branch=branch, subject=subject, attribute_name=attribute_name)
            )
            gql = await _record(_graphql_cell(db=db, branch=branch, subject=subject))
            logged = _logged_errors(caplog=caplog, since=since)
            print(
                f"[matrix] {label} | {role}={branch.name} | {subject.role} {subject.kind}\n"
                f"    get_one: {get_one}\n    query: {query}\n    profile_applied: {applied}\n"
                f"    graphql: {gql}\n    logged_errors: {logged}"
            )


# -----------------------------------------------------------------------------
# node.attribute.add
# -----------------------------------------------------------------------------

SERIAL = AttributeSchema(
    name="serial", kind="Number", optional=True, default_value=42, branch=BranchSupportType.AGNOSTIC
)
LEVEL = AttributeSchema(name="level", kind="Number", optional=True, default_value=5)


def _user_branch_roles(default_branch: Branch, forks: Forks, later: Branch) -> list[tuple[str, Branch]]:
    return [
        ("main", default_branch),
        ("sibling", forks.sibling),
        ("migrating", forks.migrating),
        ("forked-after", later),
    ]


def _default_branch_roles(default_branch: Branch, older: Branch, newer: Branch) -> list[tuple[str, Branch]]:
    return [("main", default_branch), ("forked-before", older), ("forked-after", newer)]


async def test_agnostic_attribute_added_to_aware_node_on_user_branch_stays_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1")
    forks = await _fork(db=db)
    node_ids = [widget.id, profile.id, template.id]
    before = await _snapshot(db=db, node_ids=node_ids, branches=[default_branch, forks.sibling])

    at, result = await _add_attribute(db=db, branch=forks.migrating, kind=WIDGET_KIND, attribute=SERIAL)
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="attribute add / agnostic attr on aware node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=[
            Subject(role="node", kind=WIDGET_KIND, node_id=widget.id, profiled=True),
            Subject(role="profile", kind=WIDGET_PROFILE_KIND, node_id=profile.id),
            Subject(role="template", kind=WIDGET_TEMPLATE_KIND, node_id=template.id),
        ],
        attribute_name="serial",
    )

    assert result.nbr_migrations_executed == 3
    assert (await _read(db, widget.id, forks.migrating))["serial"] == 42
    assert (await _read(db, template.id, forks.migrating))["serial"] == 42
    await _assert_unchanged_outside(
        db=db,
        before=before,
        node_ids=node_ids,
        branches=[default_branch, forks.sibling],
        attribute_name="serial",
        at=at,
        default_branch=default_branch,
    )


async def test_attribute_added_to_agnostic_node_on_user_branch_stays_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch)
    profile = await _create(db, default_branch, BEACON_PROFILE_KIND, profile_name="bp1")
    beacon = await _create(db, default_branch, BEACON_KIND, name="b1", profiles=[profile])
    forks = await _fork(db=db)
    node_ids = [beacon.id, profile.id]
    before = await _snapshot(db=db, node_ids=node_ids, branches=[default_branch, forks.sibling])

    at, result = await _add_attribute(db=db, branch=forks.migrating, kind=BEACON_KIND, attribute=LEVEL)
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="attribute add / attr on agnostic node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=[
            Subject(role="node", kind=BEACON_KIND, node_id=beacon.id, profiled=True),
            Subject(role="profile", kind=BEACON_PROFILE_KIND, node_id=profile.id),
        ],
        attribute_name="level",
    )

    assert result.nbr_migrations_executed == 2
    schema_on_branch = registry.schema.get_schema_branch(name=forks.migrating.name)
    assert schema_on_branch.get(name=BEACON_KIND).get_attribute(name="level").branch is BranchSupportType.AGNOSTIC
    assert (await _read(db, beacon.id, forks.migrating))["level"] == 5
    await _assert_unchanged_outside(
        db=db,
        before=before,
        node_ids=node_ids,
        branches=[default_branch, forks.sibling],
        attribute_name="level",
        at=at,
        default_branch=default_branch,
    )


async def test_agnostic_attribute_added_to_aware_node_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch)
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1")
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1")
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _add_attribute(db=db, branch=default_branch, kind=WIDGET_KIND, attribute=SERIAL)
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="attribute add / agnostic attr on aware node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=[
            Subject(role="node", kind=WIDGET_KIND, node_id=widget.id),
            Subject(role="template", kind=WIDGET_TEMPLATE_KIND, node_id=template.id),
        ],
        attribute_name="serial",
    )
    await _print_old_branch(db, "aware add on default", older, [widget.id, template.id], "serial", at)

    assert result.nbr_migrations_executed == 2
    for branch in (default_branch, newer):
        assert (await _read(db, widget.id, branch))["serial"] == 42
        assert (await _read(db, template.id, branch))["serial"] == 42


async def test_attribute_added_to_agnostic_node_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch)
    beacon = await _create(db, default_branch, BEACON_KIND, name="b1")
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _add_attribute(db=db, branch=default_branch, kind=BEACON_KIND, attribute=LEVEL)
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="attribute add / attr on agnostic node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=[Subject(role="node", kind=BEACON_KIND, node_id=beacon.id)],
        attribute_name="level",
    )
    await _print_old_branch(db, "agnostic-node add on default", older, [beacon.id], "level", at)

    assert result.nbr_migrations_executed == 1
    for branch in (default_branch, newer):
        assert (await _read(db, beacon.id, branch))["level"] == 5


@dataclass(frozen=True)
class SameNameAddCase:
    name: str
    kind: str
    attribute: AttributeSchema


SAME_NAME_ADD_CASES = [
    SameNameAddCase(name="agnostic-attribute-on-aware-node", kind=WIDGET_KIND, attribute=SERIAL),
    SameNameAddCase(name="attribute-on-agnostic-node", kind=BEACON_KIND, attribute=LEVEL),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SAME_NAME_ADD_CASES])
async def test_characterize_same_attribute_added_on_default_branch_after_user_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture, case: SameNameAddCase
) -> None:
    _register_schema(default_branch=default_branch)
    node = await _create(db, default_branch, case.kind, name="n1")
    forks = await _fork(db=db)

    await _add_attribute(db=db, branch=forks.migrating, kind=case.kind, attribute=case.attribute)
    on_default = deepcopy(case.attribute)
    on_default.default_value = 7
    _, result = await _add_attribute(db=db, branch=default_branch, kind=case.kind, attribute=on_default)
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label=f"same name added on main after user branch / {case.name}",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=[Subject(role="node", kind=case.kind, node_id=node.id)],
        attribute_name=case.attribute.name,
    )

    label = f"{case.name}: {case.attribute.name}"
    _print(f"{label}: nodes migrated by the default-branch add", result.nbr_migrations_executed)
    _print(f"{label} raw edges", await _raw_attribute_edges(db, node.id, case.attribute.name))


# -----------------------------------------------------------------------------
# attribute.supports_generated_schema.update
# -----------------------------------------------------------------------------


def _widget_subjects(widget: Node, profile: Node, template: Node | None = None) -> list[Subject]:
    subjects = [
        Subject(role="node", kind=WIDGET_KIND, node_id=widget.id, profiled=True),
        Subject(role="profile", kind=WIDGET_PROFILE_KIND, node_id=profile.id),
    ]
    if template is not None:
        subjects.append(Subject(role="template", kind=WIDGET_TEMPLATE_KIND, node_id=template.id))
    return subjects


async def test_profile_and_template_support_enabled_on_user_branch_stays_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    """A read-only branch-agnostic attribute becoming writable adds it to the profile and the template."""
    _register_schema(default_branch=default_branch, color_read_only=True)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1")
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    forks = await _fork(db=db)
    node_ids = [profile.id, template.id]
    before = await _snapshot(db=db, node_ids=node_ids, branches=[default_branch, forks.sibling])

    at, result = await _update_attribute(
        db=db, branch=forks.migrating, kind=WIDGET_KIND, attribute_name="color", read_only=False
    )
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated enable (read_only) / agnostic attr on aware node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=_widget_subjects(widget=widget, profile=profile, template=template),
        attribute_name="color",
    )

    assert result.nbr_migrations_executed == 2
    assert (await _read(db, template.id, forks.migrating))["color"] == "blue"
    await _assert_unchanged_outside(
        db=db,
        before=before,
        node_ids=node_ids,
        branches=[default_branch, forks.sibling],
        attribute_name="color",
        at=at,
        default_branch=default_branch,
    )


async def test_profile_and_template_support_enabled_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch, color_read_only=True)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1")
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _update_attribute(
        db=db, branch=default_branch, kind=WIDGET_KIND, attribute_name="color", read_only=False
    )
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated enable (read_only) / agnostic attr on aware node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=_widget_subjects(widget=widget, profile=profile, template=template),
        attribute_name="color",
    )
    await _print_old_branch(db, "support enabled on default", older, [profile.id, template.id], "color", at)

    assert result.nbr_migrations_executed == 2
    for branch in (default_branch, newer):
        assert (await _read(db, template.id, branch))["color"] == "blue"
        assert "color" in await _read(db, profile.id, branch)


async def test_profile_support_enabled_for_agnostic_node_on_user_branch_stays_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    """A unique attribute of a branch-agnostic kind becoming non-unique adds it to the kind's profile."""
    _register_schema(default_branch=default_branch, code_unique=True)
    profile = await _create(db, default_branch, BEACON_PROFILE_KIND, profile_name="bp1")
    beacon = await _create(db, default_branch, BEACON_KIND, name="b1", profiles=[profile])
    forks = await _fork(db=db)
    node_ids = [profile.id]
    before = await _snapshot(db=db, node_ids=node_ids, branches=[default_branch, forks.sibling])

    at, result = await _update_attribute(
        db=db, branch=forks.migrating, kind=BEACON_KIND, attribute_name="code", unique=False
    )
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated enable (unique) / agnostic node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=[
            Subject(role="node", kind=BEACON_KIND, node_id=beacon.id, profiled=True),
            Subject(role="profile", kind=BEACON_PROFILE_KIND, node_id=profile.id),
        ],
        attribute_name="code",
    )

    assert result.nbr_migrations_executed == 1
    assert "code" in await _read(db, profile.id, forks.migrating)
    await _assert_unchanged_outside(
        db=db,
        before=before,
        node_ids=node_ids,
        branches=[default_branch, forks.sibling],
        attribute_name="code",
        at=at,
        default_branch=default_branch,
    )


async def test_profile_support_enabled_for_agnostic_node_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch, code_unique=True)
    profile = await _create(db, default_branch, BEACON_PROFILE_KIND, profile_name="bp1")
    beacon = await _create(db, default_branch, BEACON_KIND, name="b1", profiles=[profile])
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _update_attribute(
        db=db, branch=default_branch, kind=BEACON_KIND, attribute_name="code", unique=False
    )
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated enable (unique) / agnostic node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=[
            Subject(role="node", kind=BEACON_KIND, node_id=beacon.id, profiled=True),
            Subject(role="profile", kind=BEACON_PROFILE_KIND, node_id=profile.id),
        ],
        attribute_name="code",
    )
    await _print_old_branch(db, "agnostic-node support enabled on default", older, [profile.id], "code", at)

    assert result.nbr_migrations_executed == 1
    for branch in (default_branch, newer):
        assert "code" in await _read(db, profile.id, branch)


async def test_profile_and_template_support_disabled_on_user_branch_keeps_the_default_branch_value(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    """A branch-agnostic attribute turned read-only on a user branch leaves it on the default branch's profile."""
    _register_schema(default_branch=default_branch)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1", color="red")
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1", color="green")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    forks = await _fork(db=db)

    at, result = await _update_attribute(
        db=db, branch=forks.migrating, kind=WIDGET_KIND, attribute_name="color", read_only=True
    )
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated disable (read_only) / agnostic attr on aware node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=_widget_subjects(widget=widget, profile=profile, template=template),
        attribute_name="color",
    )

    assert result.nbr_migrations_executed == 2
    assert "color" not in await _read(db, profile.id, forks.migrating)
    assert "color" not in await _read(db, template.id, forks.migrating)
    for branch in (default_branch, forks.sibling):
        assert (await _read(db, profile.id, branch))["color"] == "red"
        assert (await _read(db, template.id, branch))["color"] == "green"
    assert _visible_from(await _edges_touched_at(db=db, at=at), default_branch) == []


async def test_profile_and_template_support_disabled_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1", color="red")
    template = await _create(db, default_branch, WIDGET_TEMPLATE_KIND, template_name="wt1", color="green")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _update_attribute(
        db=db, branch=default_branch, kind=WIDGET_KIND, attribute_name="color", read_only=True
    )
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="supports-generated disable (read_only) / agnostic attr on aware node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=_widget_subjects(widget=widget, profile=profile, template=template),
        attribute_name="color",
    )
    await _print_old_branch(db, "support disabled on default", older, [profile.id, template.id], "color", at)

    assert result.nbr_migrations_executed == 2
    for branch in (default_branch, newer):
        assert "color" not in await _read(db, profile.id, branch)
        assert "color" not in await _read(db, template.id, branch)


# -----------------------------------------------------------------------------
# node.uniqueness_constraints.update
# -----------------------------------------------------------------------------

COLOR_CONSTRAINT = [["name__value", "color__value"]]


async def test_uniqueness_constraint_release_on_user_branch_stays_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    """Dropping a branch-agnostic attribute from a uniqueness constraint adds it to the profile."""
    _register_schema(default_branch=default_branch, widget_uniqueness_constraints=COLOR_CONSTRAINT)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    forks = await _fork(db=db)
    node_ids = [profile.id]
    before = await _snapshot(db=db, node_ids=node_ids, branches=[default_branch, forks.sibling])

    at, result = await _update_uniqueness_constraints(
        db=db, branch=forks.migrating, kind=WIDGET_KIND, constraints=[["name__value"]]
    )
    later = await create_branch(db=db, branch_name="agnostic-add-later")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="uniqueness-constraint release / agnostic attr on aware node / user branch",
        branches=_user_branch_roles(default_branch=default_branch, forks=forks, later=later),
        subjects=_widget_subjects(widget=widget, profile=profile),
        attribute_name="color",
    )

    assert result.nbr_migrations_executed == 1
    assert "color" in await _read(db, profile.id, forks.migrating)
    await _assert_unchanged_outside(
        db=db,
        before=before,
        node_ids=node_ids,
        branches=[default_branch, forks.sibling],
        attribute_name="color",
        at=at,
        default_branch=default_branch,
    )


async def test_uniqueness_constraint_release_on_default_branch_is_read_by_later_branches(
    db: InfrahubDatabase, default_branch: Branch, caplog: pytest.LogCaptureFixture
) -> None:
    _register_schema(default_branch=default_branch, widget_uniqueness_constraints=COLOR_CONSTRAINT)
    profile = await _create(db, default_branch, WIDGET_PROFILE_KIND, profile_name="wp1")
    widget = await _create(db, default_branch, WIDGET_KIND, name="w1", profiles=[profile])
    older = await create_branch(db=db, branch_name="agnostic-add-older")

    at, result = await _update_uniqueness_constraints(
        db=db, branch=default_branch, kind=WIDGET_KIND, constraints=[["name__value"]]
    )
    newer = await create_branch(db=db, branch_name="agnostic-add-newer")
    await _read_matrix(
        db=db,
        caplog=caplog,
        label="uniqueness-constraint release / agnostic attr on aware node / default branch",
        branches=_default_branch_roles(default_branch=default_branch, older=older, newer=newer),
        subjects=_widget_subjects(widget=widget, profile=profile),
        attribute_name="color",
    )
    await _print_old_branch(db, "constraint release on default", older, [profile.id], "color", at)

    assert result.nbr_migrations_executed == 1
    for branch in (default_branch, newer):
        assert "color" in await _read(db, profile.id, branch)
