import re
from collections.abc import Generator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from fast_depends import Provider

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MigrationError, ValidationError
from infrahub.workers.dependencies import build_cache, build_database
from infrahub.workflows.catalogue import SCHEMA_APPLY_MIGRATION
from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.schema import load_schema


async def test_rebase_graph(
    db: InfrahubDatabase, base_dataset_02: dict, register_core_models_schema: SchemaBranch
) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)
    cached_branched_from = registry.branch[branch1.name].branched_from
    await branch1.rebase(db=db)

    # Rebasing mutates the instance it is given but must not publish it to the branch cache
    assert branch1.branched_from != cached_branched_from
    assert registry.branch[branch1.name].branched_from == cached_branched_from

    # Query all cars in MAIN, AFTER the rebase
    cars = sorted(await NodeManager.query(schema="TestCar", db=db), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected is False

    # Query all cars in BRANCH1, AFTER the REBASE
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, db=db), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected is True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"


async def test_rebase_graph_delete(
    db: InfrahubDatabase, base_dataset_02: dict, register_core_models_schema: SchemaBranch
) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    persons = sorted(await NodeManager.query(schema="TestPerson", db=db), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, db=db)
    await p3.delete(db=db)

    await branch1.rebase(db=db)

    # Query all cars in BRANCH1, AFTER the REBASE
    persons = sorted(await NodeManager.query(schema="TestPerson", branch=branch1, db=db), key=lambda p: p.id)
    assert len(persons) == 2


async def test_merge_relationship_many(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_organization_schema: SchemaBranch,
) -> None:
    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db)

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="red", description="The red tag")
    await red.save(db=db)

    yellow = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await yellow.new(db=db, name="yellow", description="The yellow tag")
    await yellow.save(db=db)

    org1 = await Node.init(db=db, schema="CoreOrganization", branch=default_branch)
    await org1.new(db=db, name="org1", tags=[blue])
    await org1.save(db=db)

    branch1 = await create_branch(branch_name="branch1", db=db)

    # Update the relationships for ORG1 >> TAGS in BRANCH1
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, db=db)
    await org1_branch.tags.update(data=[blue, red], db=db)
    await org1_branch.save(db=db)

    # Update the relationships for ORG1 >> TAGS in MAIN
    org1_main = await NodeManager.get_one(id=org1.id, db=db)
    await org1_main.tags.update(data=[blue, yellow], db=db)
    await org1_main.save(db=db)

    await branch1.rebase(db=db)

    # All Relationship are in BRANCH1 after the REBASE
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, db=db)
    assert len(await org1_branch.tags.get(db=db)) == 3


async def _change_car_on_both_branches(
    db: InfrahubDatabase, branch: Branch, car_id: str, field_names: list[str], main_owner: Node, branch_owner: Node
) -> None:
    car_main = await NodeManager.get_one(db=db, id=car_id)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_id)
    if "name" in field_names:
        car_main.name.value = "camry-main"
        car_branch.name.value = "camry-branch"
    if "owner" in field_names:
        await car_main.owner.update(db=db, data=main_owner)
        await car_branch.owner.update(db=db, data=branch_owner)
    await car_main.save(db=db)
    await car_branch.save(db=db)


async def _select_every_conflict(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, selection: ConflictSelection | None
) -> list[str]:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    branch_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    conflicts = [
        (conflict_path, conflict)
        async for conflict_path, conflict in diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=branch.name, diff_id=branch_diff.uuid
        )
    ]
    if selection:
        for _, conflict in conflicts:
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)
    return sorted(conflict_path for conflict_path, _ in conflicts)


@pytest.fixture
def memory_cache(dependency_provider: Provider) -> Generator[None, None, None]:
    """Serve the rebase flow's cache from memory rather than from a cache another module's app left running."""
    # A lambda rather than the bare class: fast_depends reads the callable's return annotation.
    with override_dependency(build_cache, lambda: MemoryCache(), dependency_provider=dependency_provider):  # noqa: PLW0108
        yield


async def _rebase(db: InfrahubDatabase, default_branch: Branch, branch: Branch, dependency_provider: Provider) -> None:
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider):  # noqa: ARG005
        await rebase_branch(branch=branch.name, context=context)


@dataclass
class UnrebasableConflictCase:
    name: str
    field_names: list[str]
    selection: ConflictSelection | None
    conflict_path_suffixes: list[str]
    expected_message: str
    """The rebase error, with `{car_id}` standing for the id of the conflicting car."""


NAME_CONFLICT_PATH_SUFFIXES = ["display_label/value", "human_friendly_id/value", "name/value"]
UNREBASABLE_CONFLICT_MESSAGE_START = (
    "Branch branch2 contains conflicts with the default branch that must be addressed before rebasing."
)
RESOLVE_NAME_CONFLICTS_INSTRUCTION = (
    " Resolve these conflicts in favor of the branch, in a proposed change or with the ResolveDiffConflict mutation,"
    " or update the data so that both branches agree: data/{car_id}/display_label/value,"
    " data/{car_id}/human_friendly_id/value, data/{car_id}/name/value."
)
UPDATE_OWNER_CONFLICT_INSTRUCTION = (
    " Update the data so that both branches agree on these conflicts: data/{car_id}/owner/peer."
)
UNREBASABLE_CONFLICT_CASES = [
    UnrebasableConflictCase(
        name="unresolved_attribute",
        field_names=["name"],
        selection=None,
        conflict_path_suffixes=NAME_CONFLICT_PATH_SUFFIXES,
        expected_message=UNREBASABLE_CONFLICT_MESSAGE_START + RESOLVE_NAME_CONFLICTS_INSTRUCTION,
    ),
    UnrebasableConflictCase(
        name="attribute_resolved_for_the_default_branch",
        field_names=["name"],
        selection=ConflictSelection.BASE_BRANCH,
        conflict_path_suffixes=NAME_CONFLICT_PATH_SUFFIXES,
        expected_message=UNREBASABLE_CONFLICT_MESSAGE_START + RESOLVE_NAME_CONFLICTS_INSTRUCTION,
    ),
    # the rebased branch would see the default branch's peer next to its own
    UnrebasableConflictCase(
        name="cardinality_one_peer_resolved_for_the_branch",
        field_names=["owner"],
        selection=ConflictSelection.DIFF_BRANCH,
        conflict_path_suffixes=["owner/peer"],
        expected_message=UNREBASABLE_CONFLICT_MESSAGE_START + UPDATE_OWNER_CONFLICT_INSTRUCTION,
    ),
    UnrebasableConflictCase(
        name="unresolved_attribute_and_cardinality_one_peer",
        field_names=["name", "owner"],
        selection=None,
        conflict_path_suffixes=[*NAME_CONFLICT_PATH_SUFFIXES, "owner/peer"],
        expected_message=UNREBASABLE_CONFLICT_MESSAGE_START
        + RESOLVE_NAME_CONFLICTS_INSTRUCTION
        + UPDATE_OWNER_CONFLICT_INSTRUCTION,
    ),
]


@pytest.mark.parametrize("case", UNREBASABLE_CONFLICT_CASES, ids=lambda case: case.name)
async def test_branch_rebase_rejects_a_conflict_it_cannot_apply(
    case: UnrebasableConflictCase,
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    memory_cache: None,
    workflow_recorder: WorkflowRecorder,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    car_camry_main: Node,
    person_john_main: Node,
    person_albert_main: Node,
) -> None:
    branch2 = await create_branch(db=db, branch_name="branch2")
    await _change_car_on_both_branches(
        db=db,
        branch=branch2,
        car_id=car_camry_main.id,
        field_names=case.field_names,
        main_owner=person_albert_main,
        branch_owner=person_john_main,
    )
    conflict_paths = await _select_every_conflict(
        db=db, default_branch=default_branch, branch=branch2, selection=case.selection
    )
    assert conflict_paths == [f"data/{car_camry_main.id}/{suffix}" for suffix in case.conflict_path_suffixes]

    expected_message = case.expected_message.format(car_id=car_camry_main.id)
    with pytest.raises(ValidationError, match=f"^{re.escape(expected_message)}$"):
        await _rebase(db=db, default_branch=default_branch, branch=branch2, dependency_provider=dependency_provider)

    rejected_branch = await Branch.get_by_name(db=db, name=branch2.name)
    assert rejected_branch.branched_from == branch2.branched_from


async def test_branch_rebase_applies_a_conflict_resolved_for_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    memory_cache: None,
    workflow_recorder: WorkflowRecorder,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    car_camry_main: Node,
    person_john_main: Node,
    person_albert_main: Node,
) -> None:
    branch2 = await create_branch(db=db, branch_name="branch2")
    await _change_car_on_both_branches(
        db=db,
        branch=branch2,
        car_id=car_camry_main.id,
        field_names=["name"],
        main_owner=person_albert_main,
        branch_owner=person_john_main,
    )
    conflict_paths = await _select_every_conflict(
        db=db, default_branch=default_branch, branch=branch2, selection=ConflictSelection.DIFF_BRANCH
    )
    assert conflict_paths == [f"data/{car_camry_main.id}/{suffix}" for suffix in NAME_CONFLICT_PATH_SUFFIXES]
    # a branch an upgrade could not rebase keeps this status, which only a rebase clears
    branch2.status = BranchStatus.NEED_UPGRADE_REBASE
    await branch2.save(db=db)

    await _rebase(db=db, default_branch=default_branch, branch=branch2, dependency_provider=dependency_provider)

    rebased_branch = await Branch.get_by_name(db=db, name=branch2.name)
    assert rebased_branch.status is BranchStatus.OPEN
    assert rebased_branch.branched_from != branch2.branched_from
    car_branch = await NodeManager.get_one(db=db, branch=branch2.name, id=car_camry_main.id)
    assert car_branch.name.value == "camry-branch"
    car_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
    assert car_main.name.value == "camry-main"


async def test_rebase_preserves_metadata(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """Test that rebase preserves created/updated_at/by metadata on objects, attributes, and relationships.

    Note: Rebase updates the 'from' timestamp on branch relationships to the rebase time, which affects
    how metadata timestamps are reported. The test validates that:
    1. Node-level metadata from main is preserved
    2. Attribute values are preserved
    3. updated_by is preserved
    4. Relationships are preserved with correct peers
    5. Updates on main after branch creation are visible after rebase
    """
    # Create a person in main branch
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alice", height=165)
    before_person_create = Timestamp()
    await person.save(db=db, user_id="person-create-user")
    after_person_create = Timestamp()

    # Create a car in main branch with owner relationship
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="pinto", nbr_seats=5, is_electric=True, owner=person)
    before_car_create = Timestamp()
    await car.save(db=db, user_id="car-create-user")
    after_car_create = Timestamp()

    # Create a branch
    branch1 = await create_branch(branch_name="branch1", db=db)

    # Modify the car on the branch (update attribute)
    car_branch = await NodeManager.get_one(id=car.id, branch=branch1, db=db)
    car_branch.nbr_seats.value = 4
    await car_branch.save(db=db, user_id="nbr-seats-update-user")

    # Create a new object on the branch
    new_person = await Node.init(db=db, schema="TestPerson", branch=branch1)
    await new_person.new(db=db, name="Bob", height=180)
    await new_person.save(db=db, user_id="new-person-create-user")

    # Update the person on main AFTER the branch was created (this should be visible after rebase)
    person_main = await NodeManager.get_one(id=person.id, db=db)
    person_main.height.value = 170
    before_person_update_main = Timestamp()
    await person_main.save(db=db, user_id="height-update-user")
    after_person_update_main = Timestamp()

    # Create a new car on main AFTER the branch was created
    car2 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car2.new(db=db, name="model3", nbr_seats=5, is_electric=True, owner=person)
    before_car2_create = Timestamp()
    await car2.save(db=db, user_id="car2-create-user")
    after_car2_create = Timestamp()

    # Rebase the branch
    before_rebase = Timestamp()
    await branch1.rebase(db=db)
    after_rebase = Timestamp()

    # Verify metadata on objects created on main (queried from branch after rebase)
    person_after_rebase = await NodeManager.get_one(
        id=person.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert before_person_create < person_after_rebase._get_created_at() < after_person_create
    assert person_after_rebase._get_created_by() == "person-create-user"

    # Verify that updates on main after branch creation are visible after rebase
    assert person_after_rebase.height.value == 170
    assert before_person_update_main < person_after_rebase.height._get_updated_at() < after_person_update_main
    assert person_after_rebase.height._get_updated_by() == "height-update-user"

    # Verify metadata on objects created on main (car) - node-level metadata from main branch
    car_after_rebase = await NodeManager.get_one(
        id=car.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    # Node was created on main, so created_at/by should reflect that
    assert before_car_create < car_after_rebase._get_created_at() < after_car_create
    assert car_after_rebase._get_created_by() == "car-create-user"

    # Verify attribute value and updated_by are preserved (timestamp is updated by rebase)
    assert car_after_rebase.nbr_seats.value == 4
    assert car_after_rebase.nbr_seats._get_updated_by() == "nbr-seats-update-user"
    assert before_rebase < car_after_rebase.nbr_seats._get_updated_at() < after_rebase

    # Verify attribute that was NOT updated keeps updated_by
    assert car_after_rebase.name._get_updated_by() == "car-create-user"
    assert before_car_create < car_after_rebase.name._get_updated_at() < after_car_create
    assert car_after_rebase.name.value == "pinto"

    # Verify metadata on objects created on branch
    new_person_after_rebase = await NodeManager.get_one(
        id=new_person.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert new_person_after_rebase._get_created_by() == "new-person-create-user"
    assert before_rebase < new_person_after_rebase._get_created_at() < after_rebase
    assert new_person_after_rebase._get_updated_by() == "new-person-create-user"
    assert new_person_after_rebase._get_updated_at() == new_person_after_rebase._get_created_at()
    assert new_person_after_rebase.name.value == "Bob"

    # Verify new object created on main after branch creation is visible after rebase
    car2_after_rebase = await NodeManager.get_one(
        id=car2.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert before_car2_create < car2_after_rebase._get_created_at() < after_car2_create
    assert car2_after_rebase._get_created_by() == "car2-create-user"
    assert car2_after_rebase._get_updated_at() == car2_after_rebase._get_created_at()
    assert car2_after_rebase._get_updated_by() == "car2-create-user"
    assert car2_after_rebase.name.value == "model3"

    # Verify relationship metadata (owner relationship on car created before branch)
    car_schema = car_after_rebase.get_schema()
    owner_rels = await NodeManager.query_peers(
        db=db,
        branch=branch1,
        ids=[car.id],
        source_kind="TestCar",
        schema=car_schema.get_relationship(name="owner"),
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(owner_rels) == 1
    owner_rel = owner_rels[0]
    # Relationship was created on main before branch, so created_by should reflect that
    assert owner_rel._get_created_by() == "car-create-user"
    assert before_car_create < owner_rel._get_created_at() < after_car_create
    assert owner_rel._get_updated_by() == "car-create-user"
    assert owner_rel._get_updated_at() == owner_rel._get_created_at()
    assert owner_rel.get_peer_id() == person.id
    owner_peer = await owner_rel.get_peer(db=db)
    assert before_person_create < owner_peer._get_created_at() < after_person_create
    assert owner_peer._get_created_by() == "person-create-user"
    assert before_person_update_main < owner_peer.height._get_updated_at() < after_person_update_main
    assert owner_peer.height._get_updated_by() == "height-update-user"

    # Verify relationship metadata on car2 (created on main AFTER branch creation)
    # This validates that relationships created on main after branch creation are visible after rebase
    car2_owner_rels = await NodeManager.query_peers(
        db=db,
        branch=branch1,
        ids=[car2.id],
        source_kind="TestCar",
        schema=car_schema.get_relationship(name="owner"),
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(car2_owner_rels) == 1
    car2_owner_rel = car2_owner_rels[0]
    # Relationship was created on main after branch creation
    assert before_car2_create < car2_owner_rel._get_created_at() < after_car2_create
    assert car2_owner_rel._get_created_by() == "car2-create-user"
    assert car2_owner_rel._get_updated_at() == car2_owner_rel._get_created_at()
    assert car2_owner_rel._get_created_by() == "car2-create-user"
    assert car2_owner_rel.get_peer_id() == person.id
    owner_peer = await car2_owner_rel.get_peer(db=db)
    assert owner_peer.name.value == "Alice"
    assert before_person_create < owner_peer._get_created_at() < after_person_create
    assert owner_peer._get_created_by() == "person-create-user"
    assert before_car2_create < owner_peer._get_updated_at() < after_car2_create
    assert owner_peer._get_updated_by() == "car2-create-user"


async def test_rebase_schemas_handed_to_the_update_coordinator(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    memory_cache: None,
    workflow_recorder: WorkflowRecorder,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The rebase must migrate against the branch-creation schema and roll back to the branch's own.

    Both cases share one fork-before-inheritance setup, which is the expensive part, but they need
    separate branches: observing the migration baseline needs a rebase that succeeds, observing the
    rollback needs one that fails.
    """
    widget_kind = "TestingWidget"
    gadget_kind = "TestingGadget"
    ownable_kind = "TestingOwnable"
    ownable = GenericSchema(
        name="Ownable",
        namespace="Testing",
        attributes=[AttributeSchema(name="owner_name", kind="Text", optional=True)],
    )
    widget = NodeSchema(
        name="Widget",
        namespace="Testing",
        default_filter="name__value",
        attributes=[AttributeSchema(name="name", kind="Text")],
    )
    gadget = NodeSchema(
        name="Gadget",
        namespace="Testing",
        default_filter="name__value",
        attributes=[AttributeSchema(name="name", kind="Text")],
    )
    await load_schema(db=db, schema=SchemaRoot(generics=[ownable], nodes=[widget, gadget]), update_db=True)

    baseline_branch = await create_branch(db=db, branch_name="baseline-branch")
    rollback_branch = await create_branch(db=db, branch_name="rollback-branch")
    fork_hash = baseline_branch.active_schema_hash.main

    # A schema change that exists only on the branch being rolled back, on a kind the destination
    # never touches so that the rebase does not report a conflict
    branch_gadget = gadget.duplicate()
    branch_gadget.attributes.append(AttributeSchema(name="serial", kind="Text", optional=True))
    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[branch_gadget]),
        branch_name=rollback_branch.name,
        update_db=True,
        limit=[gadget_kind],
    )
    rollback_pre_rebase_hash = registry.schema.get_schema_branch(name=rollback_branch.name).get_hash()

    # The destination branch adopts the generic only after both branches forked
    inheriting_widget = widget.duplicate()
    inheriting_widget.inherit_from = [ownable_kind]
    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[inheriting_widget]),
        update_db=True,
        limit=[widget_kind, ownable_kind],
    )
    assert set(
        registry.schema.get_schema_branch(name=default_branch.name).get_node(name=widget_kind).attribute_names
    ) == {"name", "owner_name"}

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider):  # noqa: ARG005
        await rebase_branch(branch=baseline_branch.name, context=context)

        # The flow publishes the branch it rebased, so the cache stops holding the pre-rebase instance
        rebased_baseline_branch = await Branch.get_by_name(db=db, name=baseline_branch.name)
        assert rebased_baseline_branch.branched_from != baseline_branch.branched_from
        published_baseline_branch = registry.branch[baseline_branch.name]
        assert published_baseline_branch is not baseline_branch
        assert published_baseline_branch.branched_from == rebased_baseline_branch.branched_from
        assert published_baseline_branch.status is BranchStatus.OPEN

        migration_calls = workflow_recorder.get_execute_calls_for(SCHEMA_APPLY_MIGRATION)
        assert len(migration_calls) == 1
        baseline_schema = migration_calls[0]["parameters"]["message"].previous_schema
        assert isinstance(baseline_schema, SchemaBranch)

        # The whole baseline, not just the widget, must be the schema as it stood at branch creation
        assert baseline_schema.get_hash() == fork_hash
        assert baseline_schema.get_hash() != registry.schema.get_schema_branch(name=default_branch.name).get_hash()
        assert set(baseline_schema.get_node(name=widget_kind).attribute_names) == {"name"}

        # Now make the migrations fail, on the branch that carries a schema change of its own
        workflow_recorder.execute_results[SCHEMA_APPLY_MIGRATION.name] = ["migration failed on purpose"]
        with pytest.raises(MigrationError) as exc_info:
            await rebase_branch(branch=rollback_branch.name, context=context)
    assert exc_info.value.message == "migration failed on purpose"

    # The rollback must keep the branch-only change and must not adopt the generic the destination
    # picked up after the fork
    restored_schema = registry.schema.get_schema_branch(name=rollback_branch.name)
    assert set(restored_schema.get_node(name=gadget_kind).attribute_names) == {"name", "serial"}
    assert set(restored_schema.get_node(name=widget_kind).attribute_names) == {"name"}
    assert restored_schema.get_hash() == rollback_pre_rebase_hash

    # The restored hash has to reach storage, not just the in-memory registry the rollback wrote
    reloaded_branch = await Branch.get_by_name(db=db, name=rollback_branch.name)
    assert reloaded_branch.active_schema_hash.main == rollback_pre_rebase_hash


async def test_failed_rebase_keeps_the_branch_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    memory_cache: None,
    workflow_recorder: WorkflowRecorder,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A rollback after failed migrations must not take the branch's own data with it."""
    widget_kind = "TestingWidget"
    gadget_kind = "TestingGadget"
    widget = NodeSchema(
        name="Widget",
        namespace="Testing",
        default_filter="name__value",
        attributes=[AttributeSchema(name="name", kind="Text")],
    )
    gadget = NodeSchema(
        name="Gadget",
        namespace="Testing",
        default_filter="name__value",
        attributes=[AttributeSchema(name="name", kind="Text")],
    )
    await load_schema(db=db, schema=SchemaRoot(nodes=[widget, gadget]), update_db=True)

    branch = await create_branch(db=db, branch_name="failed-rebase-branch")

    branch_widget = await Node.init(db=db, schema=widget_kind, branch=branch)
    await branch_widget.new(db=db, name="widget-on-branch")
    await branch_widget.save(db=db)

    # A schema change of the branch's own, on a kind the destination never touches, so the rebase
    # runs migrations at all without reporting a conflict
    branch_gadget = gadget.duplicate()
    branch_gadget.attributes.append(AttributeSchema(name="serial", kind="Text", optional=True))
    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[branch_gadget]),
        branch_name=branch.name,
        update_db=True,
        limit=[gadget_kind],
    )

    # A node created on the destination after the fork, so the rebase has something to pull in
    main_widget = await Node.init(db=db, schema=widget_kind)
    await main_widget.new(db=db, name="widget-on-main")
    await main_widget.save(db=db)

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider):  # noqa: ARG005
        workflow_recorder.execute_results[SCHEMA_APPLY_MIGRATION.name] = ["migration failed on purpose"]
        with pytest.raises(MigrationError):
            await rebase_branch(branch=branch.name, context=context)

    rolled_back_branch = await Branch.get_by_name(db=db, name=branch.name)
    widgets = await NodeManager.query(db=db, schema=widget_kind, branch=rolled_back_branch)
    assert sorted(str(node.get_attribute("name").value) for node in widgets) == ["widget-on-branch", "widget-on-main"]
