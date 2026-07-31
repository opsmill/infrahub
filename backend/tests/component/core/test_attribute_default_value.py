"""Tests for how an attribute resolves its schema default value and maintains the ``is_default`` flag.

The inherited-attribute cases frame the materialisation behaviour along every sub-case that matters:

- whether the node predates the inheritance (no row) or was created while already inheriting (row at creation);
- whether the inherited attribute carries a schema default or not;
- whether the written value diverges from the default (materialise) or not (stay virtual);
- the indexed vs large (non-indexed) attribute-value path;
- branch scoping and attribute-value filtering, including a value filter over a still-virtual default.
"""

from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@dataclass
class UnmaterialisedInheritedStatus:
    """A node that predates an inherited ``status`` attribute, with the schema before and after inheritance."""

    node_id: str
    schema_before: NodeSchema
    schema_after: NodeSchema


async def _node_with_unmaterialised_inherited_status(
    db: InfrahubDatabase,
    branch: Branch,
    namespace: str,
    default_value: str | None,
    kind: str = "Dropdown",
) -> UnmaterialisedInheritedStatus:
    """Persist a node before an inherited ``status`` attribute exists, then evolve the schema to add it.

    The node predates the attribute and the add-attribute migration skips inherited attributes, so it keeps no
    database row for ``status`` until a value is explicitly written. Returns the node id together with the schema
    before and after the attribute was inherited.
    """
    schema_before = NodeSchema(
        name="Server",
        namespace=namespace,
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[schema_before]), branch=branch.name)

    server = await Node.init(db=db, schema=f"{namespace}Server", branch=branch)
    await server.new(db=db, name="server-1")
    await server.save(db=db)

    status_definition: dict = {"name": "status", "kind": kind, "optional": True}
    if kind == "Dropdown":
        status_definition["choices"] = [{"name": "active"}, {"name": "planned"}]
    if default_value is not None:
        status_definition["default_value"] = default_value

    tracked_thing = GenericSchema(
        name="TrackedThing",
        namespace=namespace,
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(**status_definition)],
    )
    server_with_inheritance = NodeSchema(
        name="Server",
        namespace=namespace,
        branch=BranchSupportType.AWARE,
        inherit_from=[f"{namespace}TrackedThing"],
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    registry.schema.set(name=tracked_thing.kind, schema=tracked_thing, branch=branch.name)
    registry.schema.set(name=server_with_inheritance.kind, schema=server_with_inheritance, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)

    schema_after = registry.schema.get_node_schema(name=f"{namespace}Server", branch=branch.name, duplicate=False)
    return UnmaterialisedInheritedStatus(node_id=server.id, schema_before=schema_before, schema_after=schema_after)


@pytest.mark.parametrize("updated_status,expected_is_default", [(None, True), ("online", True), ("offline", False)])
async def test_enum_with_default_preserves_is_default(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data_simple: dict[str, Node],
    updated_status: str | None,
    expected_is_default: bool,
) -> None:
    site = hierarchical_location_data_simple["paris"]
    rack = await Node.init(db=db, schema="LocationRack")
    await rack.new(db=db, name="new-rack", parent=site)
    await rack.save(db=db)
    status_enum_by_value = {
        "online": rack.status.value.ONLINE,
        "offline": rack.status.value.OFFLINE,
    }
    assert rack.status.is_default
    assert rack.status.value.value == "online"

    retrieved_rack = await NodeManager.get_one(db=db, id=rack.id)
    assert retrieved_rack.status.value.value == "online"
    assert retrieved_rack.status.is_default
    retrieved_rack.name.value = "updated-rack"
    expected_status = "online"
    if updated_status:
        retrieved_rack.status.value = status_enum_by_value[updated_status]
        expected_status = updated_status
    await retrieved_rack.save(db=db)
    assert retrieved_rack.status.value.value == expected_status
    assert retrieved_rack.status.is_default is expected_is_default

    updated_rack = await NodeManager.get_one(db=db, id=rack.id)
    assert updated_rack.name.value == "updated-rack"
    assert updated_rack.status.value.value == expected_status
    assert updated_rack.status.is_default is expected_is_default


async def test_update_inherited_default_backed_attribute_persists(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """End-to-end reproduction: the add migration is a no-op, and a following non-default save materialises the row.

    A node created before a generic contributes a default-backed attribute has no database row for that attribute.
    Setting the attribute to a non-default value and saving must materialise the row so the value survives a reload,
    gains a real id, and is no longer the default.
    """
    setup = await _node_with_unmaterialised_inherited_status(
        db=db, branch=default_branch, namespace="Bugtest", default_value="active"
    )
    assert setup.schema_after.get_attribute("status").inherited is True

    # The add-attribute migration is a no-op for inherited attributes, leaving existing nodes without a status row.
    migration = NodeAttributeAddMigration(
        previous_node_schema=setup.schema_before,
        new_node_schema=setup.schema_after,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="BugtestServer", field_name="status"),
    )
    migration_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert migration_result.errors == []
    assert migration_result.nbr_migrations_executed == 0

    # Reading the pre-existing node yields the schema default, backed by no attribute row.
    loaded = await NodeManager.get_one(db=db, id=setup.node_id, branch=default_branch)
    assert loaded.status.value == "active"
    assert loaded.status.id is None
    assert loaded.status.is_default is True

    # Update the attribute to a non-default value and save.
    loaded.status.value = "planned"
    await loaded.save(db=db)

    # A subsequent read must return the persisted value, with a real attribute id and is_default False.
    reloaded = await NodeManager.get_one(db=db, id=setup.node_id, branch=default_branch)
    assert reloaded.status.value == "planned"
    assert reloaded.status.id is not None
    assert reloaded.status.is_default is False


@dataclass
class MaterialisationCase:
    name: str
    namespace: str
    default_value: str | None
    written_value: str | None
    expected_value: str | None
    expected_materialised: bool


MATERIALISATION_CASES = [
    MaterialisationCase(
        name="default-diverges",
        namespace="Bugmxa",
        default_value="active",
        written_value="planned",
        expected_value="planned",
        expected_materialised=True,
    ),
    MaterialisationCase(
        name="default-unchanged",
        namespace="Bugmxb",
        default_value="active",
        written_value="active",
        expected_value="active",
        expected_materialised=False,
    ),
    MaterialisationCase(
        name="no-default-assigned",
        namespace="Bugmxc",
        default_value=None,
        written_value="planned",
        expected_value="planned",
        expected_materialised=True,
    ),
    MaterialisationCase(
        name="no-default-unassigned",
        namespace="Bugmxd",
        default_value=None,
        written_value=None,
        expected_value=None,
        expected_materialised=False,
    ),
]


@pytest.mark.parametrize("case", MATERIALISATION_CASES, ids=[c.name for c in MATERIALISATION_CASES])
async def test_predating_node_save_materialises_by_value_divergence(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    case: MaterialisationCase,
) -> None:
    """Saving a predating node creates a row only when the written value diverges from the schema default."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace=case.namespace, default_value=case.default_value
        )
    ).node_id

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    if case.written_value is not None:
        loaded.status.value = case.written_value
    await loaded.save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    assert reloaded.status.value == case.expected_value
    if case.expected_materialised:
        assert reloaded.status.id is not None
        assert reloaded.status.is_default is False
    else:
        assert reloaded.status.id is None
        assert reloaded.status.is_default is True


async def test_predating_node_materialises_large_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A large (non-indexed) inherited attribute is materialised on first non-default write, like an indexed one."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace="Buglarge", default_value=None, kind="TextArea"
        )
    ).node_id

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    assert loaded.status.value is None
    assert loaded.status.id is None

    loaded.status.value = "a long free-form note that is stored without an index"
    await loaded.save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    assert reloaded.status.value == "a long free-form note that is stored without an index"
    assert reloaded.status.id is not None
    assert reloaded.status.is_default is False


async def test_node_created_while_inheriting_has_row_and_persists(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A node created after the inheritance already exists carries a real row from creation and persists updates.

    This frames the boundary of the bug: only nodes that predate the inheritance lack a row.
    """
    tracked_thing = GenericSchema(
        name="TrackedThing",
        namespace="Bugnew",
        branch=BranchSupportType.AWARE,
        attributes=[
            AttributeSchema(
                name="status",
                kind="Dropdown",
                default_value="active",
                optional=True,
                choices=[{"name": "active"}, {"name": "planned"}],
            )
        ],
    )
    server_schema = NodeSchema(
        name="Server",
        namespace="Bugnew",
        branch=BranchSupportType.AWARE,
        inherit_from=["BugnewTrackedThing"],
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[tracked_thing], nodes=[server_schema]), branch=default_branch.name
    )

    server = await Node.init(db=db, schema="BugnewServer", branch=default_branch)
    await server.new(db=db, name="server-1")
    await server.save(db=db)

    # Created while inheriting: the default-backed attribute already has a real row.
    loaded = await NodeManager.get_one(db=db, id=server.id, branch=default_branch)
    assert loaded.status.value == "active"
    assert loaded.status.id is not None
    assert loaded.status.is_default is True

    loaded.status.value = "planned"
    await loaded.save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=server.id, branch=default_branch)
    assert reloaded.status.value == "planned"
    assert reloaded.status.id is not None
    assert reloaded.status.is_default is False


async def test_filter_matches_persisted_inherited_default_backed_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Once an inherited default-backed attribute is materialised, attribute-value filters match its new value."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace="Bugfilter", default_value="active"
        )
    ).node_id

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    loaded.status.value = "planned"
    await loaded.save(db=db)

    matches = await NodeManager.query(
        db=db, schema="BugfilterServer", filters={"status__value": "planned"}, branch=default_branch
    )
    assert [node.id for node in matches] == [server_id]

    non_matches = await NodeManager.query(
        db=db, schema="BugfilterServer", filters={"status__value": "active"}, branch=default_branch
    )
    assert non_matches == []


@pytest.mark.xfail(
    reason="A predating node still at its default has no value row, so a value filter does not match it until the "
    "attribute is materialised by an explicit write. The save-side fix does not close this read-side gap.",
    strict=True,
)
async def test_value_filter_matches_virtual_default_on_predating_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A value filter on the schema default matches a predating node that still resolves to that default."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace="Bugvirtualfilter", default_value="active"
        )
    ).node_id

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    assert loaded.status.value == "active"
    assert loaded.status.id is None

    matches = await NodeManager.query(
        db=db, schema="BugvirtualfilterServer", filters={"status__value": "active"}, branch=default_branch
    )
    assert [node.id for node in matches] == [server_id]


async def test_update_inherited_default_backed_attribute_persists_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Materialising an inherited default-backed attribute on a branch is scoped to that branch."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace="Bugbranch", default_value="active"
        )
    ).node_id
    branch = await create_branch(branch_name="bug-branch", db=db)

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=branch)
    loaded.status.value = "planned"
    await loaded.save(db=db)

    on_branch = await NodeManager.get_one(db=db, id=server_id, branch=branch)
    assert on_branch.status.value == "planned"
    assert on_branch.status.id is not None
    assert on_branch.status.is_default is False

    on_default = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    assert on_default.status.value == "active"
    assert on_default.status.id is None
    assert on_default.status.is_default is True


async def test_materialising_save_reports_default_as_previous_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Materialising a predating default-backed attribute records the schema default as the changelog previous value."""
    server_id = (
        await _node_with_unmaterialised_inherited_status(
            db=db, branch=default_branch, namespace="Bugchangelog", default_value="active"
        )
    ).node_id

    loaded = await NodeManager.get_one(db=db, id=server_id, branch=default_branch)
    loaded.status.value = "planned"
    changelog = await loaded.status.save(db=db)

    assert changelog is not None
    assert changelog.value == "planned"
    assert changelog.value_previous == "active"
