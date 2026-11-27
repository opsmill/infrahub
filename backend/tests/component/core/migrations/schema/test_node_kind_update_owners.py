import uuid
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.tasks import get_derived_schema_pairs
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    StoredNodeOwnership,
    StoredOwnerState,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.path import SchemaPath
from infrahub.core.query import QueryType
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.dependencies.registry import get_component_registry
from tests.component.core.diff.merge._ownership import merge, update_diff
from tests.helpers.ownership import create_groups, read_owners, set_owners

PREVIOUS_KIND = "TestPerson"
NEW_KIND = "Test2NewPerson"


async def _create_person(db: InfrahubDatabase) -> Node:
    person = await Node.init(db=db, schema=PREVIOUS_KIND)
    await person.new(db=db, name="John")
    await person.save(db=db)
    return person


async def _change_kind(db: InfrahubDatabase, branch: Branch) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    person_schema = schema.duplicate().get(name=PREVIOUS_KIND)
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    assert person_schema.kind == NEW_KIND
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name=PREVIOUS_KIND),
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=PREVIOUS_KIND, field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1


def _stored(node_id: str, kind: str, owner_ids: tuple[str, ...]) -> dict[str, StoredNodeOwnership]:
    return {
        node_id: StoredNodeOwnership(
            node_id=node_id, kind=kind, holders={NODE_HOLDER: StoredOwnerState(owner_ids=tuple(sorted(owner_ids)))}
        )
    }


@dataclass
class KindChangeTestCase:
    name: str
    default_branch_owners: tuple[str, ...]
    """Group names. An empty tuple is "no owner"."""

    on_branch: bool = False
    """The kind changes on a branch that starts after the write on the default branch."""

    branch_owners: tuple[str, ...] | None = None
    """Group names that the branch writes before the kind changes. None is no write on the branch."""


KIND_CHANGE_TEST_CASES: list[KindChangeTestCase] = [
    KindChangeTestCase(name="owners_on_default_branch", default_branch_owners=("dc-emea", "network-emea")),
    KindChangeTestCase(name="no_owner_on_default_branch", default_branch_owners=()),
    KindChangeTestCase(name="owners_of_default_branch_on_branch", default_branch_owners=("dc-emea",), on_branch=True),
    KindChangeTestCase(
        name="owners_replaced_on_branch",
        default_branch_owners=("dc-emea", "network-emea"),
        on_branch=True,
        branch_owners=("network-emea", "security"),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in KIND_CHANGE_TEST_CASES])
async def test_node_keeps_its_owners_when_its_kind_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    test_case: KindChangeTestCase,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db)
    default_owner_ids = tuple(group_ids[name] for name in test_case.default_branch_owners)
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=default_owner_ids)
    branch = default_branch
    owner_ids = default_owner_ids
    if test_case.on_branch:
        branch = await create_branch(branch_name="branch2", db=db)
    if test_case.branch_owners is not None:
        owner_ids = tuple(group_ids[name] for name in test_case.branch_owners)
        await set_owners(db=db, branch=branch, node_id=person.id, owner_ids=owner_ids)
    repository = OwnershipRepository(db=db, branch=branch, at=None)
    assert await repository.read(node_ids=[person.id]) == _stored(
        node_id=person.id, kind=PREVIOUS_KIND, owner_ids=owner_ids
    )

    await _change_kind(db=db, branch=branch)

    assert await repository.read(node_ids=[person.id]) == _stored(node_id=person.id, kind=NEW_KIND, owner_ids=owner_ids)
    if test_case.on_branch:
        default_repository = OwnershipRepository(db=db, branch=default_branch, at=None)
        assert await default_repository.read(node_ids=[person.id]) == _stored(
            node_id=person.id, kind=PREVIOUS_KIND, owner_ids=default_owner_ids
        )
    await verify_graph(db=db, kinds=[PREVIOUS_KIND, NEW_KIND])


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
async def test_node_with_the_same_account_group_as_owner_and_as_source_keeps_both_edges_when_its_kind_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    on_branch: bool,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db)
    sources = tuple(sorted([group_ids["security"], group_ids["dc-emea"]]))
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=(group_ids["security"],))
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=sources, holder=NODE_SOURCES_HOLDER)
    holders = {
        NODE_HOLDER: StoredOwnerState(owner_ids=(group_ids["security"],)),
        NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=sources),
    }
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch

    await _change_kind(db=db, branch=branch)

    assert await _read_holders(db=db, branch=branch, node_ids={"person": person.id}) == {"person": (NEW_KIND, holders)}
    if on_branch:
        assert await _read_holders(db=db, branch=default_branch, node_ids={"person": person.id}) == {
            "person": (PREVIOUS_KIND, holders)
        }
    rows = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})-[r]->(:Node {uuid: $group_id})
WHERE r.status = "active" AND r.to IS NULL AND r.branch = $branch
RETURN n.kind AS kind, type(r) AS edge_type
ORDER BY edge_type
        """,
        params={"node_id": person.id, "group_id": group_ids["security"], "branch": branch.name},
        type=QueryType.READ,
    )
    assert [(row["kind"], row["edge_type"]) for row in rows] == [(NEW_KIND, "HAS_OWNER"), (NEW_KIND, "HAS_SOURCE")]
    await verify_graph(db=db, kinds=[PREVIOUS_KIND, NEW_KIND])


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
async def test_owners_of_a_relationship_field_follow_the_node_when_its_kind_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    on_branch: bool,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db)
    cars_holder = field_holder(
        schema=registry.schema.get(name=PREVIOUS_KIND, branch=default_branch, duplicate=False), field_name="cars"
    )
    assert cars_holder is not None
    node_owners = tuple(sorted([group_ids["dc-emea"], group_ids["security"]]))
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=node_owners)
    await set_owners(
        db=db, branch=default_branch, node_id=person.id, owner_ids=(group_ids["network-emea"],), holder=cars_holder
    )
    holders = {
        NODE_HOLDER: StoredOwnerState(owner_ids=node_owners),
        cars_holder: StoredOwnerState(owner_ids=(group_ids["network-emea"],)),
    }
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch
    assert await _read_holders(db=db, branch=branch, node_ids={"person": person.id}) == {
        "person": (PREVIOUS_KIND, holders)
    }

    await _change_kind(db=db, branch=branch)

    assert await _read_holders(db=db, branch=branch, node_ids={"person": person.id}) == {"person": (NEW_KIND, holders)}
    if on_branch:
        assert await _read_holders(db=db, branch=default_branch, node_ids={"person": person.id}) == {
            "person": (PREVIOUS_KIND, holders)
        }
    rows = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})-[r:HAS_OWNER|HAS_OWNER_SET]->(peer)
WHERE r.status = "active" AND r.to IS NULL AND r.branch = $branch
OPTIONAL MATCH (peer:OwnerSet)-[set_edge:HAS_OWNER]->(owner:Node)
WHERE set_edge.status = "active" AND set_edge.to IS NULL
RETURN n.kind AS kind, type(r) AS edge_type, coalesce(peer.uuid, owner.uuid) AS owner_id
ORDER BY edge_type, owner_id
        """,
        params={"node_id": person.id, "branch": branch.name},
        type=QueryType.READ,
    )
    assert [(row["kind"], row["edge_type"], row["owner_id"]) for row in rows] == [
        *[(NEW_KIND, "HAS_OWNER", owner_id) for owner_id in node_owners],
        (NEW_KIND, "HAS_OWNER_SET", group_ids["network-emea"]),
    ]
    sets = await db.execute_query(
        query="MATCH (:Node {uuid: $node_id})-[:HAS_OWNER_SET]->(s:OwnerSet) RETURN count(DISTINCT s) AS sets",
        params={"node_id": person.id},
        type=QueryType.READ,
    )
    assert sets[0]["sets"] == 1
    await verify_graph(db=db, kinds=[PREVIOUS_KIND, NEW_KIND])


GADGET = NodeSchema(
    name="Gadget",
    namespace="Testing",
    generate_template=True,
    attributes=[AttributeSchema(name="name", kind="Text")],
)


async def _change_gadget_namespace(db: InfrahubDatabase, branch: Branch) -> None:
    """Move the gadget kind to the namespace `Test2`, with the profile and template kinds that come from it."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name="TestingGadget")
    candidate_schema = schema.duplicate()
    new_node = candidate_schema.get(name="TestingGadget")
    candidate_schema.delete(name="TestingGadget")
    new_node.namespace = "Test2"
    candidate_schema.set(name=new_node.kind, schema=new_node)
    candidate_schema.process()
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        derived_schemas=get_derived_schema_pairs(
            previous_schema_branch=schema,
            new_schema_branch=candidate_schema,
            previous_node_schema=previous_node,
            new_node_schema=new_node,
        ),
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_node.kind, field_name="namespace"),
    )
    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors


async def _read_holders(
    db: InfrahubDatabase, branch: Branch, node_ids: dict[str, str]
) -> dict[str, tuple[str, dict[HolderKey, StoredOwnerState]]]:
    """Return the kind and the stored owner states of each node, by node name."""
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=list(node_ids.values()))
    return {name: (stored[node_id].kind, dict(stored[node_id].holders)) for name, node_id in node_ids.items()}


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
async def test_profile_template_and_template_copy_keep_their_owners_when_the_kind_changes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, on_branch: bool
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[GADGET.duplicate()]), branch=default_branch.name)
    group_ids = await create_groups(db=db)
    profile = await Node.init(db=db, schema="ProfileTestingGadget")
    await profile.new(db=db, profile_name="gadget-profile")
    await profile.save(db=db)
    template = await Node.init(db=db, schema="TemplateTestingGadget")
    await template.new(db=db, template_name="gadget-template")
    await template.save(db=db)
    profile_owners = (group_ids["dc-emea"],)
    template_owners = tuple(sorted([group_ids["network-emea"], group_ids["security"]]))
    for giver, owner_ids in ((profile, profile_owners), (template, template_owners)):
        await set_owners(db=db, branch=default_branch, node_id=giver.id, owner_ids=owner_ids, holder=NODE_TARGET_HOLDER)
    gadget = await create_node(
        data={"name": "gadget-1", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name="TestingGadget", branch=default_branch),
    )
    node_ids = {"profile": profile.id, "template": template.id, "gadget": gadget.id}
    holders: dict[str, dict[HolderKey, StoredOwnerState]] = {
        "profile": {NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=profile_owners)},
        "template": {NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=template_owners)},
        "gadget": {NODE_HOLDER: StoredOwnerState(owner_ids=template_owners, template_id=template.id)},
    }
    previous_kinds = {"profile": "ProfileTestingGadget", "template": "TemplateTestingGadget", "gadget": "TestingGadget"}
    new_kinds = {"profile": "ProfileTest2Gadget", "template": "TemplateTest2Gadget", "gadget": "Test2Gadget"}
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch
    assert await _read_holders(db=db, branch=branch, node_ids=node_ids) == {
        name: (previous_kinds[name], holders[name]) for name in node_ids
    }

    await _change_gadget_namespace(db=db, branch=branch)

    assert await _read_holders(db=db, branch=branch, node_ids=node_ids) == {
        name: (new_kinds[name], holders[name]) for name in node_ids
    }
    if on_branch:
        assert await _read_holders(db=db, branch=default_branch, node_ids=node_ids) == {
            name: (previous_kinds[name], holders[name]) for name in node_ids
        }
    rows = await db.execute_query(
        query="""
MATCH (n:Node)-[r:HAS_OWNER_SOURCE|HAS_TARGET_OWNER_SET]->(peer)
WHERE r.status = "active" AND r.to IS NULL AND r.branch = $branch
RETURN n.kind AS kind, type(r) AS edge_type, peer.kind AS peer_kind
ORDER BY kind
        """,
        params={"branch": branch.name},
        type=QueryType.READ,
    )
    assert [(row["kind"], row["edge_type"], row["peer_kind"]) for row in rows] == [
        ("ProfileTest2Gadget", "HAS_TARGET_OWNER_SET", None),
        ("TemplateTest2Gadget", "HAS_TARGET_OWNER_SET", None),
        ("Test2Gadget", "HAS_OWNER_SOURCE", "TemplateTest2Gadget"),
    ]
    await verify_graph(db=db, kinds=[*previous_kinds.values(), *new_kinds.values()])


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
async def test_node_whose_template_is_the_origin_of_its_owners_and_a_source_keeps_both_edges_when_the_kind_changes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, on_branch: bool
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[GADGET.duplicate()]), branch=default_branch.name)
    group_ids = await create_groups(db=db)
    template = await Node.init(db=db, schema="TemplateTestingGadget")
    await template.new(db=db, template_name="gadget-template")
    await template.save(db=db)
    template_owners = (group_ids["dc-emea"],)
    await set_owners(
        db=db, branch=default_branch, node_id=template.id, owner_ids=template_owners, holder=NODE_TARGET_HOLDER
    )
    gadget = await create_node(
        data={"name": "gadget-1", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name="TestingGadget", branch=default_branch),
    )
    sources = tuple(sorted([template.id, group_ids["security"]]))
    await set_owners(db=db, branch=default_branch, node_id=gadget.id, owner_ids=sources, holder=NODE_SOURCES_HOLDER)
    holders = {
        NODE_HOLDER: StoredOwnerState(owner_ids=template_owners, template_id=template.id),
        NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=sources),
    }
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch
    assert await _read_holders(db=db, branch=branch, node_ids={"gadget": gadget.id}) == {
        "gadget": ("TestingGadget", holders)
    }

    await _change_gadget_namespace(db=db, branch=branch)

    assert await _read_holders(db=db, branch=branch, node_ids={"gadget": gadget.id}) == {
        "gadget": ("Test2Gadget", holders)
    }
    if on_branch:
        assert await _read_holders(db=db, branch=default_branch, node_ids={"gadget": gadget.id}) == {
            "gadget": ("TestingGadget", holders)
        }
    rows = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})-[r]->(template:Node {uuid: $template_id})
WHERE r.status = "active" AND r.to IS NULL AND r.branch = $branch
RETURN n.kind AS kind, type(r) AS edge_type, template.kind AS template_kind
ORDER BY edge_type
        """,
        params={"node_id": gadget.id, "template_id": template.id, "branch": branch.name},
        type=QueryType.READ,
    )
    assert [(row["kind"], row["edge_type"], row["template_kind"]) for row in rows] == [
        ("Test2Gadget", "HAS_OWNER_SOURCE", "TemplateTest2Gadget"),
        ("Test2Gadget", "HAS_SOURCE", "TemplateTest2Gadget"),
    ]
    await verify_graph(db=db, kinds=["TestingGadget", "TemplateTestingGadget", "Test2Gadget", "TemplateTest2Gadget"])


def _rename_gadget_name(branch: Branch, kind: str) -> AttributeNameUpdateMigration:
    """Rename the attribute `name` of the gadget kind to `label` in the schema of the branch, and return the migration."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=kind)
    previous_node.get_attribute(name="name").id = str(uuid.uuid4())
    candidate = schema.duplicate()
    new_node = candidate.get(name=kind)
    new_attribute = new_node.get_attribute(name="name")
    new_attribute.name = "label"
    new_attribute.id = previous_node.get_attribute(name="name").id
    candidate.set(name=kind, schema=new_node)
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    return AttributeNameUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name="label"),
    )


async def test_attribute_rename_on_two_branches_after_a_kind_change_on_one_branch_gives_one_set(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[GADGET.duplicate()]), branch=default_branch.name)
    group_ids = await create_groups(db=db)
    profile = await Node.init(db=db, schema="ProfileTestingGadget")
    await profile.new(db=db, profile_name="gadget-profile")
    await profile.save(db=db)
    await set_owners(
        db=db,
        branch=default_branch,
        node_id=profile.id,
        owner_ids=(group_ids["dc-emea"],),
        holder=HolderKey(kind=HolderKind.TARGET_SET, attribute="name"),
    )
    branch = await create_branch(branch_name="branch2", db=db)
    await _change_gadget_namespace(db=db, branch=branch)
    # The rename of the default branch runs after the rename of the branch, so it finds the set with the new key.
    for migration_branch, kind in ((branch, "Test2Gadget"), (default_branch, "TestingGadget")):
        migration = _rename_gadget_name(branch=migration_branch, kind=kind)
        result = await migration.execute(migration_input=MigrationInput(db=db), branch=migration_branch)
        assert not result.errors
    renamed = {
        HolderKey(kind=HolderKind.TARGET_SET, attribute="label"): StoredOwnerState(owner_ids=(group_ids["dc-emea"],))
    }
    for read_branch, kind in ((branch, "ProfileTest2Gadget"), (default_branch, "ProfileTestingGadget")):
        assert await _read_holders(db=db, branch=read_branch, node_ids={"profile": profile.id}) == {
            "profile": (kind, renamed)
        }
    rows = await db.execute_query(
        query="""
MATCH (:Node {uuid: $node_id})-[:HAS_TARGET_OWNER_SET]->(s:OwnerSet {attribute: "label"})
RETURN count(DISTINCT s) AS sets
        """,
        params={"node_id": profile.id},
        type=QueryType.READ,
    )
    assert rows[0]["sets"] == 1
    await verify_graph(db=db, kinds=["ProfileTestingGadget", "ProfileTest2Gadget"])


async def _update_diff_and_merge(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> None:
    diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=default_branch)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    await merge(db=db, branch=branch)


async def test_merge_of_a_kind_change_on_a_branch_keeps_the_owners_of_a_relationship_field(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db)
    cars_holder = field_holder(
        schema=registry.schema.get(name=PREVIOUS_KIND, branch=default_branch, duplicate=False), field_name="cars"
    )
    assert cars_holder is not None
    owners = (group_ids["network-emea"],)
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=owners, holder=cars_holder)
    branch = await create_branch(branch_name="branch2", db=db)
    await _change_kind(db=db, branch=branch)

    await _update_diff_and_merge(db=db, default_branch=default_branch, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=person.id, holder=cars_holder) == owners
    await verify_graph(db=db)


async def test_merge_of_a_kind_change_on_a_branch_keeps_the_owners_that_a_profile_and_a_template_give(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[GADGET.duplicate()]), branch=default_branch.name)
    group_ids = await create_groups(db=db)
    profile = await Node.init(db=db, schema="ProfileTestingGadget")
    await profile.new(db=db, profile_name="gadget-profile")
    await profile.save(db=db)
    template = await Node.init(db=db, schema="TemplateTestingGadget")
    await template.new(db=db, template_name="gadget-template")
    await template.save(db=db)
    profile_owners = (group_ids["dc-emea"],)
    template_owners = tuple(sorted([group_ids["network-emea"], group_ids["security"]]))
    for giver, owner_ids in ((profile, profile_owners), (template, template_owners)):
        await set_owners(db=db, branch=default_branch, node_id=giver.id, owner_ids=owner_ids, holder=NODE_TARGET_HOLDER)
    gadget = await create_node(
        data={"name": "gadget-1", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name="TestingGadget", branch=default_branch),
    )
    node_ids = {"profile": profile.id, "template": template.id, "gadget": gadget.id}
    holders = {
        "profile": {NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=profile_owners)},
        "template": {NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=template_owners)},
        "gadget": {NODE_HOLDER: StoredOwnerState(owner_ids=template_owners, template_id=template.id)},
    }
    new_kinds = {"profile": "ProfileTest2Gadget", "template": "TemplateTest2Gadget", "gadget": "Test2Gadget"}
    branch = await create_branch(branch_name="branch2", db=db)
    await _change_gadget_namespace(db=db, branch=branch)

    await _update_diff_and_merge(db=db, default_branch=default_branch, branch=branch)

    after = await _read_holders(db=db, branch=default_branch, node_ids=node_ids)
    assert after == {name: (new_kinds[name], holders[name]) for name in node_ids}
    await verify_graph(db=db)
