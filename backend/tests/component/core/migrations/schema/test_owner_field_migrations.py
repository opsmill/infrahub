from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, HashableModelState, InfrahubKind, SchemaPathType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.fields import stored_holder_field_name
from infrahub.core.ownership.models import HolderKey, HolderKind, StoredOwnerState, field_holder
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import GraphCheck, collect_graph_violations, verify_graph
from infrahub.dependencies.registry import get_component_registry
from tests.component.core.diff.merge.conftest import get_diff_coordinator, get_diff_merger
from tests.conftest import do_car_person_schema_unregistered
from tests.helpers.ownership import USER_ID, set_owners

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.migrations.shared import SchemaMigration
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CAR_KIND = "TestCar"
ATTRIBUTE = "nbr_seats"
NEW_ATTRIBUTE = "seats"
RELATIONSHIP = "owner"
NEW_RELATIONSHIP = "keeper"

Holders = dict[str, dict[HolderKey, tuple[tuple[str, ...] | None, str | None]]]
"""The owners that each holder stores and the template that they are a copy from, by node name."""

COPY_FROM_TEMPLATE = "car-from-template"
FIELD_GROUPS: dict[str, tuple[bool, str | None, str | None]] = {
    "car": (False, None, None),
    "profile": (True, None, "network-emea"),
    "template": (True, "security", "dc-emea"),
    COPY_FROM_TEMPLATE: (False, "security", "dc-emea"),
}
"""For each node: whether it gives owners to other nodes, then the group of the attribute and of the relationship.

None is "no owner". The car made from the template holds a copy of the owners that the template gives.
"""


@pytest.fixture
def car_person_schema_unregistered(db: InfrahubDatabase, node_group_schema: None, data_schema: None) -> SchemaRoot:
    schema = do_car_person_schema_unregistered()
    # The template of a car needs the template of its parent kind.
    for node in schema.nodes:
        node.generate_template = True
    return schema


@dataclass
class FieldOwners:
    """A car, a car profile, a car template and a car made from the template, with owners for two fields of each.

    The fields are the attribute `nbr_seats` and the relationship `owner`.
    """

    group_ids: dict[str, str]
    node_ids: dict[str, str]
    """The ID of each node, by name."""

    def holders(
        self, branch: Branch, attribute: str | None = ATTRIBUTE, relationship: str | None = RELATIONSHIP
    ) -> Holders:
        """Return the owners that the fields hold when the schema of the branch names them so. None is a removed field."""
        schema = registry.schema.get(name=CAR_KIND, branch=branch, duplicate=False)
        expected: Holders = {name: {} for name in FIELD_GROUPS}
        for name, (target, attribute_group, relationship_group) in FIELD_GROUPS.items():
            template_id = self.node_ids["template"] if name == COPY_FROM_TEMPLATE else None
            for field_name, group in ((attribute, attribute_group), (relationship, relationship_group)):
                if field_name is None:
                    continue
                holder = field_holder(schema=schema, field_name=field_name, target=target)
                assert holder is not None
                expected[name][holder] = (() if group is None else (self.group_ids[group],), template_id)
        return expected


async def _write(db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey, owner_id: str) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=holder, state=StoredOwnerState(owner_ids=(owner_id,)), at=Timestamp(), user_id=USER_ID
    )


async def _read(db: InfrahubDatabase, branch: Branch, field_owners: FieldOwners) -> Holders:
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(
        node_ids=list(field_owners.node_ids.values()), attributes=True
    )
    return {
        name: {holder: (state.owner_ids, state.template_id) for holder, state in stored[node_id].holders.items()}
        for name, node_id in field_owners.node_ids.items()
    }


async def _open_edges_of_removed_attributes(db: InfrahubDatabase) -> int:
    """Count the open owner edges and template marks of the attributes that their node no longer holds."""
    query = """
    MATCH ()-[held:HAS_ATTRIBUTE]->(a:Attribute)
    WITH a, held
    ORDER BY held.from DESC
    WITH a, head(collect(held.status)) AS latest_status
    WHERE latest_status = "deleted"
    MATCH (a)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->()
    WHERE r.status = "active" AND r.to IS NULL
    RETURN count(r) AS total
    """
    results = await db.execute_query(query=query)
    return results[0]["total"]


async def _open_edges_of_detached_sets(db: InfrahubDatabase) -> int:
    """Count the open owner edges and template marks of the sets of owners that no node holds."""
    query = """
    MATCH (s:OwnerSet)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->()
    WHERE r.status = "active" AND r.to IS NULL
    AND NOT EXISTS {
        MATCH (:Node)-[held:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(s)
        WHERE held.status = "active" AND held.to IS NULL
    }
    RETURN count(r) AS total
    """
    results = await db.execute_query(query=query)
    return results[0]["total"]


@pytest.fixture
async def field_owners(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    person_john_main: Node,
    car_accord_main: Node,
    car_profile1_main: Node,
) -> FieldOwners:
    group_ids: dict[str, str] = {}
    for name in ("dc-emea", "network-emea", "security"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        group_ids[name] = group.id
    person_template = await Node.init(db=db, schema="TemplateTestPerson")
    await person_template.new(db=db, template_name="person-template")
    await person_template.save(db=db)
    template = await Node.init(db=db, schema=f"Template{CAR_KIND}")
    await template.new(db=db, template_name="car-template", owner=person_template)
    await template.save(db=db)
    data = FieldOwners(
        group_ids=group_ids,
        node_ids={"car": car_accord_main.id, "profile": car_profile1_main.id, "template": template.id},
    )
    for name, holders in data.holders(branch=default_branch).items():
        if name == COPY_FROM_TEMPLATE:
            continue
        for holder, (owner_ids, _) in holders.items():
            await set_owners(
                db=db, branch=default_branch, node_id=data.node_ids[name], owner_ids=owner_ids, holder=holder
            )
    copy = await create_node(
        data={"name": COPY_FROM_TEMPLATE, "owner": {"id": person_john_main.id}, "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name=CAR_KIND, branch=default_branch),
    )
    data.node_ids[COPY_FROM_TEMPLATE] = copy.id
    assert await _read(db=db, branch=default_branch, field_owners=data) == data.holders(branch=default_branch)
    return data


def _rename_attribute(branch: Branch) -> SchemaMigration:
    """Give the attribute its new name in the schema of the branch, and return the migration of the rename."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=CAR_KIND)
    previous_node.get_attribute(name=ATTRIBUTE).id = str(uuid.uuid4())
    candidate = schema.duplicate()
    new_node = candidate.get(name=CAR_KIND)
    new_attribute = new_node.get_attribute(name=ATTRIBUTE)
    new_attribute.name = NEW_ATTRIBUTE
    new_attribute.id = previous_node.get_attribute(name=ATTRIBUTE).id
    candidate.set(name=CAR_KIND, schema=new_node)
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    return AttributeNameUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=CAR_KIND, field_name=NEW_ATTRIBUTE),
    )


def _remove_attribute(branch: Branch) -> SchemaMigration:
    """Remove the attribute from the schema of the branch, and return the migration of the removal."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=CAR_KIND)
    candidate = schema.duplicate()
    new_node = candidate.get(name=CAR_KIND)
    new_node.attributes = [attribute for attribute in new_node.attributes if attribute.name != ATTRIBUTE]
    candidate.set(name=CAR_KIND, schema=new_node)
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    migration_node = previous_node.duplicate()
    migration_node.get_attribute(name=ATTRIBUTE).state = HashableModelState.ABSENT
    return NodeAttributeRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=migration_node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=CAR_KIND, field_name=ATTRIBUTE),
    )


def _remove_relationship(branch: Branch, other_side: bool = True) -> SchemaMigration:
    """Remove the relationship from the schema of the branch, and return the migration of the removal.

    Set `other_side` to False to keep the relationship of the person in the schema.
    """
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=CAR_KIND)
    identifier = previous_node.get_relationship(name=RELATIONSHIP).get_identifier()
    candidate = schema.duplicate()
    for sharing_schema in candidate.get_schemas_by_rel_identifier(identifier=identifier):
        if not other_side and sharing_schema.kind != CAR_KIND:
            continue
        node = candidate.get(name=sharing_schema.kind)
        node.relationships = [rel for rel in node.relationships if rel.identifier != identifier]
        candidate.set(name=sharing_schema.kind, schema=node)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    return NodeRelationshipRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=candidate.get(name=CAR_KIND),
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=CAR_KIND, field_name=RELATIONSHIP),
    )


def _rename_relationship(branch: Branch) -> None:
    """Give the relationship its new name in the schema of the branch. The rename has no migration."""
    candidate = registry.schema.get_schema_branch(name=branch.name).duplicate()
    node = candidate.get(name=CAR_KIND)
    node.get_relationship(name=RELATIONSHIP).name = NEW_RELATIONSHIP
    candidate.set(name=CAR_KIND, schema=node)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)


async def _merge(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> None:
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())


@dataclass
class FieldMigrationTestCase:
    name: str
    migrate: str
    attribute: str | None = ATTRIBUTE
    """The name of the attribute after the migration. None is a removed attribute."""

    relationship: str | None = RELATIONSHIP
    on_branch: bool = False
    """The migration runs on a branch, which is then merged."""


MIGRATIONS = {
    "rename_attribute": _rename_attribute,
    "remove_attribute": _remove_attribute,
    "remove_relationship": _remove_relationship,
}
FIELD_MIGRATION_TEST_CASES = [
    FieldMigrationTestCase(
        name=f"{migrate}_{'on_branch' if on_branch else 'on_default_branch'}", on_branch=on_branch, **fields
    )
    for migrate, fields in (
        ("rename_attribute", {"migrate": "rename_attribute", "attribute": NEW_ATTRIBUTE}),
        ("remove_attribute", {"migrate": "remove_attribute", "attribute": None}),
        ("remove_relationship", {"migrate": "remove_relationship", "relationship": None}),
    )
    for on_branch in (False, True)
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIELD_MIGRATION_TEST_CASES])
async def test_owners_of_a_field_follow_a_rename_and_end_with_a_removal(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners, test_case: FieldMigrationTestCase
) -> None:
    before = field_owners.holders(branch=default_branch)
    branch = await create_branch(db=db, branch_name="field-migration") if test_case.on_branch else default_branch

    migration = MIGRATIONS[test_case.migrate](branch)
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors

    after = field_owners.holders(branch=branch, attribute=test_case.attribute, relationship=test_case.relationship)
    assert await _read(db=db, branch=branch, field_owners=field_owners) == after
    if test_case.on_branch:
        assert await _read(db=db, branch=default_branch, field_owners=field_owners) == before
        await _merge(db=db, default_branch=default_branch, branch=branch)
        # The merge of a branch runs the schema migrations on the default branch after the merge of the graph.
        migration = MIGRATIONS[test_case.migrate](default_branch)
        result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
        assert not result.errors
        assert await _read(db=db, branch=default_branch, field_owners=field_owners) == after
    # A second run changes nothing.
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert await _read(db=db, branch=default_branch, field_owners=field_owners) == after
    assert await _open_edges_of_detached_sets(db=db) == 0
    assert await _open_edges_of_removed_attributes(db=db) == 0
    await verify_graph(db=db)


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="on_default_branch"), pytest.param(True, id="on_branch")])
async def test_owners_of_a_relationship_follow_its_rename(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners, on_branch: bool
) -> None:
    before = field_owners.holders(branch=default_branch)
    branch = await create_branch(db=db, branch_name="relationship-rename") if on_branch else default_branch

    _rename_relationship(branch=branch)

    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    after = field_owners.holders(branch=branch, relationship=NEW_RELATIONSHIP)
    assert after == before
    assert await _read(db=db, branch=branch, field_owners=field_owners) == after
    names = {
        name: stored_holder_field_name(
            holder=field_holder(
                schema=schema_branch.get(name=CAR_KIND, duplicate=False), field_name=NEW_RELATIONSHIP, target=target
            ),
            schema=schema_branch.get(name=kind, duplicate=False),
            schema_branch=schema_branch,
        )
        for name, kind, target in (("car", CAR_KIND, False), ("profile", f"Profile{CAR_KIND}", True))
    }
    assert names == {"car": f"{NEW_RELATIONSHIP}__owners", "profile": f"{NEW_RELATIONSHIP}__target_owners"}
    if on_branch:
        # The owners that the branch writes under the new name reach the default branch, which has the old name.
        car_holder = field_holder(schema=schema_branch.get(name=CAR_KIND, duplicate=False), field_name=NEW_RELATIONSHIP)
        assert car_holder is not None
        await _write(
            db=db,
            branch=branch,
            node_id=field_owners.node_ids["car"],
            holder=car_holder,
            owner_id=field_owners.group_ids["network-emea"],
        )
        await _merge(db=db, default_branch=default_branch, branch=branch)
        after["car"][car_holder] = ((field_owners.group_ids["network-emea"],), None)
        assert await _read(db=db, branch=default_branch, field_owners=field_owners) == after
    await verify_graph(db=db)


@pytest.mark.parametrize(
    "selection",
    [
        pytest.param(ConflictSelection.DIFF_BRANCH, id="branch_selected"),
        pytest.param(ConflictSelection.BASE_BRANCH, id="default_branch_selected"),
    ],
)
async def test_merge_skips_a_resolved_owner_conflict_of_a_relationship_that_the_branch_removed_later(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners, selection: ConflictSelection
) -> None:
    car_id = field_owners.node_ids["car"]
    holder = field_holder(
        schema=registry.schema.get(name=CAR_KIND, branch=default_branch, duplicate=False), field_name=RELATIONSHIP
    )
    assert holder is not None
    branch = await create_branch(db=db, branch_name="relationship-removed")
    await _write(
        db=db, branch=default_branch, node_id=car_id, holder=holder, owner_id=field_owners.group_ids["network-emea"]
    )
    await _write(db=db, branch=branch, node_id=car_id, holder=holder, owner_id=field_owners.group_ids["dc-emea"])
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    metadata = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=default_branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name, diff_id=metadata.uuid)
    conflict_path = f"data/{car_id}/{RELATIONSHIP}__owners/property/HAS_OWNER"
    conflicts = diff.get_all_conflicts()
    assert list(conflicts) == [conflict_path]
    await diff_repository.update_conflict_by_id(conflict_id=conflicts[conflict_path].uuid, selection=selection)
    result = await _remove_relationship(branch).execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors

    await _merge(db=db, default_branch=default_branch, branch=branch)

    # The merge carries the hide of the relationship owners, and applies no side of the conflict.
    assert await _read(db=db, branch=default_branch, field_owners=field_owners) == field_owners.holders(
        branch=default_branch, relationship=None
    )

    result = await _remove_relationship(default_branch).execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )
    assert not result.errors
    assert await _read(db=db, branch=default_branch, field_owners=field_owners) == field_owners.holders(
        branch=default_branch, relationship=None
    )
    await verify_graph(db=db)


async def test_removal_of_one_side_of_a_relationship_ends_the_owners_of_that_side_only(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners, person_john_main: Node
) -> None:
    person_holder = field_holder(
        schema=registry.schema.get(name="TestPerson", branch=default_branch, duplicate=False), field_name="cars"
    )
    assert person_holder is not None
    security_id = field_owners.group_ids["security"]
    await _write(db=db, branch=default_branch, node_id=person_john_main.id, holder=person_holder, owner_id=security_id)

    result = await _remove_relationship(default_branch, other_side=False).execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )

    assert not result.errors
    assert await _read(db=db, branch=default_branch, field_owners=field_owners) == field_owners.holders(
        branch=default_branch, relationship=None
    )
    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(
        node_ids=[person_john_main.id], attributes=True
    )
    assert {holder: state.owner_ids for holder, state in stored[person_john_main.id].holders.items()} == {
        person_holder: (security_id,)
    }
    await verify_graph(db=db)


async def test_merge_closes_the_owner_that_the_default_branch_gave_to_an_attribute_that_the_branch_removed(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners
) -> None:
    car_id = field_owners.node_ids["car"]
    branch = await create_branch(db=db, branch_name="attribute-removed")
    await _write(
        db=db,
        branch=default_branch,
        node_id=car_id,
        holder=HolderKey(kind=HolderKind.ATTRIBUTE, attribute=ATTRIBUTE),
        owner_id=field_owners.group_ids["network-emea"],
    )
    result = await _remove_attribute(branch).execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors

    await _merge(db=db, default_branch=default_branch, branch=branch)

    result = await _remove_attribute(default_branch).execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )
    assert not result.errors
    assert await _read(db=db, branch=default_branch, field_owners=field_owners) == field_owners.holders(
        branch=default_branch, attribute=None
    )
    assert await _open_edges_of_removed_attributes(db=db) == 0
    await verify_graph(db=db)


async def test_attribute_rename_keeps_the_source_and_the_owner_that_are_the_same_node(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners
) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="lineage-account", password="unused-password")
    await account.save(db=db)
    car_id = field_owners.node_ids["car"]
    car = await NodeManager.get_one(db=db, branch=default_branch, id=car_id, raise_on_error=True)
    car.get_attribute(name=ATTRIBUTE).source = account.id
    await car.save(db=db)
    await _write(
        db=db,
        branch=default_branch,
        node_id=car_id,
        holder=HolderKey(kind=HolderKind.ATTRIBUTE, attribute=ATTRIBUTE),
        owner_id=account.id,
    )

    migration = _rename_attribute(branch=default_branch)
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not result.errors
    query = """
    MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: $name})-[r:HAS_SOURCE|HAS_OWNER]->(peer)
    WHERE r.status = "active" AND r.to IS NULL
    RETURN type(r) AS edge_type, peer.uuid AS peer_id
    """
    edges = await db.execute_query(query=query, params={"node_id": car_id, "name": NEW_ATTRIBUTE})
    assert sorted((edge["edge_type"], edge["peer_id"]) for edge in edges) == [
        ("HAS_OWNER", account.id),
        ("HAS_SOURCE", account.id),
    ]


@pytest.mark.parametrize("new_name", [pytest.param(None, id="removal"), pytest.param("colour", id="rename")])
async def test_owners_that_a_profile_or_a_template_of_an_inheriting_kind_gives_follow_the_attribute_of_the_generic(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics_unregistered: dict[str, Any],
    new_name: str | None,
) -> None:
    raw_schema = deepcopy(car_person_schema_generics_unregistered)
    for node in raw_schema["nodes"]:
        if node["name"] in {"ElectricCar", "GazCar"}:
            node["generate_template"] = True
        if node["name"] == "GazCar":
            node["attributes"].append({"name": "color", "kind": "Text", "optional": True})
    registry.schema.register_schema(schema=SchemaRoot(**raw_schema), branch=default_branch.name)
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    node_ids: dict[str, str] = {}
    for kind, name_attribute in (
        ("ProfileTestElectricCar", "profile_name"),
        ("TemplateTestElectricCar", "template_name"),
        ("TemplateTestGazCar", "template_name"),
    ):
        node = await Node.init(db=db, schema=kind, branch=default_branch)
        await node.new(db=db, **{name_attribute: kind})
        await node.save(db=db)
        await _write(
            db=db,
            branch=default_branch,
            node_id=node.id,
            holder=HolderKey(kind=HolderKind.TARGET_SET, attribute="color"),
            owner_id=group.id,
        )
        node_ids[kind] = node.id
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    previous_generic = schema.get(name="TestCar")
    previous_generic.get_attribute(name="color").id = str(uuid.uuid4())
    new_generic = previous_generic.duplicate()
    migration: SchemaMigration
    if new_name is None:
        new_generic.get_attribute(name="color").state = HashableModelState.ABSENT
        migration = NodeAttributeRemoveMigration(
            previous_node_schema=previous_generic,
            new_node_schema=new_generic,
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
        )
    else:
        new_generic.get_attribute(name="color").name = new_name
        migration = AttributeNameUpdateMigration(
            previous_node_schema=previous_generic,
            new_node_schema=new_generic,
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name=new_name),
        )

    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not result.errors
    inherited = {new_name: (group.id,)} if new_name else {}
    assert {
        kind: await _target_owners(db=db, branch=default_branch, node_id=node_id) for kind, node_id in node_ids.items()
    } == {
        "ProfileTestElectricCar": inherited,
        "TemplateTestElectricCar": inherited,
        # The kind declares its own attribute, so the change of the attribute of the generic does not apply to it.
        "TemplateTestGazCar": {"color": (group.id,)},
    }


async def test_attribute_removal_closes_the_source_and_the_owner_that_are_the_same_node(
    db: InfrahubDatabase, default_branch: Branch, field_owners: FieldOwners
) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="lineage-account", password="unused-password")
    await account.save(db=db)
    car_id = field_owners.node_ids["car"]
    car = await NodeManager.get_one(db=db, branch=default_branch, id=car_id, raise_on_error=True)
    car.get_attribute(name=ATTRIBUTE).source = account.id
    await car.save(db=db)
    await _write(
        db=db,
        branch=default_branch,
        node_id=car_id,
        holder=HolderKey(kind=HolderKind.ATTRIBUTE, attribute=ATTRIBUTE),
        owner_id=account.id,
    )

    migration = _remove_attribute(branch=default_branch)
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not result.errors
    query = """
    MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: $name})-[r:HAS_SOURCE|HAS_OWNER]->(peer)
    WHERE r.status = "active" AND r.to IS NULL
    RETURN count(DISTINCT r) AS total
    """
    results = await db.execute_query(query=query, params={"node_id": car_id, "name": ATTRIBUTE})
    assert results[0]["total"] == 0


SHARED_KIND = "TestSharedThing"
SHARED_ATTRIBUTE = "serial"
SHARED_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="SharedThing",
            namespace="Test",
            branch=BranchSupportType.AGNOSTIC,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AGNOSTIC),
                AttributeSchema(name=SHARED_ATTRIBUTE, kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
            ],
        ),
    ]
)


def _shared_attribute_migration(branch: Branch, new_name: str | None) -> SchemaMigration:
    """Return the migration that renames the attribute of the kind that all branches share, or removes it for None."""
    previous = registry.schema.get_schema_branch(name=branch.name).get(name=SHARED_KIND)
    previous.get_attribute(name=SHARED_ATTRIBUTE).id = str(uuid.uuid4())
    new = previous.duplicate()
    if new_name is None:
        new.get_attribute(name=SHARED_ATTRIBUTE).state = HashableModelState.ABSENT
        return NodeAttributeRemoveMigration(
            previous_node_schema=previous,
            new_node_schema=new,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind=SHARED_KIND, field_name=SHARED_ATTRIBUTE
            ),
        )
    new.get_attribute(name=SHARED_ATTRIBUTE).name = new_name
    return AttributeNameUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=new,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=SHARED_KIND, field_name=new_name),
    )


async def _target_owners(
    db: InfrahubDatabase, branch: Branch, node_id: str
) -> dict[str | None, tuple[str, ...] | None]:
    """Return the owners that the node gives to each attribute, by attribute name, as the branch reads them."""
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id])
    return {holder.attribute: state.owner_ids for holder, state in stored[node_id].holders.items()}


async def _verify_graph_checks(db: InfrahubDatabase, expected: set[GraphCheck]) -> None:
    violations = await collect_graph_violations(db=db)
    assert {violation.check for violation in violations} == expected


@dataclass
class SharedProfile:
    """A profile that all branches share. It gives the group `dc-emea` as owner to the attribute `serial`."""

    profile_id: str
    group_ids: dict[str, str]


@pytest.fixture
async def shared_profile(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> SharedProfile:
    registry.schema.register_schema(schema=SHARED_SCHEMA, branch=default_branch.name)
    group_ids: dict[str, str] = {}
    for name in ("dc-emea", "network-emea"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        group_ids[name] = group.id
    profile = await Node.init(db=db, schema=f"Profile{SHARED_KIND}", branch=default_branch)
    await profile.new(db=db, profile_name="shared-profile")
    await profile.save(db=db)
    await _write(
        db=db,
        branch=default_branch,
        node_id=profile.id,
        holder=HolderKey(kind=HolderKind.TARGET_SET, attribute=SHARED_ATTRIBUTE),
        owner_id=group_ids["dc-emea"],
    )
    rows = await db.execute_query(
        query="MATCH (:Node {uuid: $id})-[e]->(s:OwnerSet)-[r]->() RETURN e.branch AS eb, r.branch AS rb",
        params={"id": profile.id},
    )
    assert [(row["eb"], row["rb"]) for row in rows] == [("-global-", "-global-")]
    return SharedProfile(profile_id=profile.id, group_ids=group_ids)


@pytest.mark.parametrize("new_name", [pytest.param(None, id="removal"), pytest.param("serial_number", id="rename")])
async def test_owners_that_a_profile_that_all_branches_share_gives_follow_the_attribute(
    db: InfrahubDatabase, default_branch: Branch, shared_profile: SharedProfile, new_name: str | None
) -> None:
    profile_id, group_ids = shared_profile.profile_id, shared_profile.group_ids
    branch_with_previous_schema = await create_branch(db=db, branch_name="previous-schema")
    migration = _shared_attribute_migration(branch=default_branch, new_name=new_name)

    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not result.errors
    after = {new_name: (group_ids["dc-emea"],)} if new_name else {}
    assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == after
    # A branch reads the global edges at its start and at the current time, so it also reads the set of a new name.
    assert await _target_owners(db=db, branch=branch_with_previous_schema, node_id=profile_id) == {
        SHARED_ATTRIBUTE: (group_ids["dc-emea"],),
        **after,
    }
    # A second run changes nothing.
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == after
    if new_name:
        await _write(
            db=db,
            branch=default_branch,
            node_id=profile_id,
            holder=HolderKey(kind=HolderKind.TARGET_SET, attribute=new_name),
            owner_id=group_ids["network-emea"],
        )
        assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == {
            new_name: (group_ids["network-emea"],)
        }
    # The rename of an attribute that all branches share leaves violations that are not about owners.
    await _verify_graph_checks(
        db=db,
        expected={GraphCheck.DUPLICATE_ATTRIBUTES, GraphCheck.ATTRIBUTE_EDGE_BRANCH} if new_name else set(),
    )


@pytest.mark.parametrize("new_name", [pytest.param(None, id="removal"), pytest.param("serial_number", id="rename")])
async def test_owners_that_a_profile_that_all_branches_share_gives_follow_the_attribute_on_a_branch(
    db: InfrahubDatabase, default_branch: Branch, shared_profile: SharedProfile, new_name: str | None
) -> None:
    profile_id, group_ids = shared_profile.profile_id, shared_profile.group_ids
    before = {SHARED_ATTRIBUTE: (group_ids["dc-emea"],)}
    after = {new_name: (group_ids["dc-emea"],)} if new_name else {}
    branch = await create_branch(db=db, branch_name="field-migration")

    migration = _shared_attribute_migration(branch=branch, new_name=new_name)
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)

    assert not result.errors
    assert await _target_owners(db=db, branch=branch, node_id=profile_id) == after
    assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == before
    # The merge of a branch runs the schema migrations on the default branch after the merge of the graph.
    await _merge(db=db, default_branch=default_branch, branch=branch)
    migration = _shared_attribute_migration(branch=default_branch, new_name=new_name)
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == after
    assert await _target_owners(db=db, branch=branch, node_id=profile_id) == after
    if new_name:
        await _write(
            db=db,
            branch=default_branch,
            node_id=profile_id,
            holder=HolderKey(kind=HolderKind.TARGET_SET, attribute=new_name),
            owner_id=group_ids["network-emea"],
        )
        assert await _target_owners(db=db, branch=default_branch, node_id=profile_id) == {
            new_name: (group_ids["network-emea"],)
        }
    # The rename of an attribute that all branches share leaves violations that are not about owners.
    await _verify_graph_checks(db=db, expected={GraphCheck.ATTRIBUTE_EDGE_BRANCH} if new_name else set())
