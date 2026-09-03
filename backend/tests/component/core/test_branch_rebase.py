import re
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
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import MigrationError, ValidationError
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database
from infrahub.workflows.catalogue import SCHEMA_APPLY_MIGRATION
from tests.adapters.workflow import WorkflowRecorder
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


async def test_branch_rebase_diff_conflict(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    dependency_provider: Provider,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    car_camry_main: Node,
) -> None:
    # NOTE: Ideally, this should be somewhere else for all tests to benefit from it
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
        car_main.name.value += "-main"
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        car_branch.name.value += "-branch"
        await car_branch.save(db=db)

        with pytest.raises(ValidationError, match="contains conflicts with the default branch that must be addressed"):
            await rebase_branch(
                branch=branch2.name,
                context=InfrahubContext.init(
                    branch=default_branch,
                    account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
                ),
            )


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

    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
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
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        workflow_recorder.execute_results[SCHEMA_APPLY_MIGRATION.name] = ["migration failed on purpose"]
        with pytest.raises(MigrationError):
            await rebase_branch(branch=branch.name, context=context)

    rolled_back_branch = await Branch.get_by_name(db=db, name=branch.name)
    widgets = await NodeManager.query(db=db, schema=widget_kind, branch=rolled_back_branch)
    assert sorted(str(node.get_attribute("name").value) for node in widgets) == ["widget-on-branch", "widget-on-main"]


def _widget_with_code_regex(code_regex: str | None) -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace="Testing",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="code", kind="Text", optional=True, parameters=TextAttributeParameters(regex=code_regex)
            ),
        ],
    )


def _widget_with_code(code_kind: str = "Text", code_optional: bool = True, code_unique: bool = False) -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace="Testing",
        default_filter="name__value",
        # The label must not read `code`, whose stored value stops parsing once the kind is narrowed
        display_labels=["name__value"],
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(name="code", kind=code_kind, optional=code_optional, unique=code_unique),
        ],
    )


async def test_rebase_reports_a_narrowed_attribute_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """An attribute kind the stored data no longer satisfies stops the rebase.

    The kind is gated on a migration rather than on a constraint, so both producers have to be
    combined before the check reaches the rebase.
    """
    widget_kind = "TestingWidget"
    await load_schema(db=db, schema=SchemaRoot(nodes=[_widget_with_code()]), update_db=True)

    widget = await Node.init(db=db, schema=widget_kind)
    await widget.new(db=db, name="widget", code="not-a-number")
    await widget.save(db=db)

    branch = await create_branch(db=db, branch_name="narrowed-kind-branch")

    widget_on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch, raise_on_error=True)
    widget_on_branch.code.value = "still-not-a-number"
    await widget_on_branch.save(db=db)

    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[_widget_with_code(code_kind="Number")]),
        branch_name=branch.name,
        update_db=True,
        limit=[widget_kind],
    )

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        with pytest.raises(ValidationError) as exc_info:
            await rebase_branch(branch=branch.name, context=context)

    assert exc_info.value.message == (
        f"Attribute-level 'kind' constraint violation on schema '{widget_kind}'."
        f" Node ({widget_kind}: {widget.id}) is not compliant."
        " The error relates to field code='still-not-a-number'."
        " for constraint attribute.kind.update code kind"
        f" and node {widget.id} {widget_kind}"
    )


async def test_rebase_reports_a_newly_mandatory_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """An attribute turned mandatory while a node still has no value for it stops the rebase.

    The node that still has no value is one the branch never edited, so the check only reaches it
    because the schema comparison contributes the constraint at unrestricted scope.
    """
    widget_kind = "TestingWidget"
    await load_schema(db=db, schema=SchemaRoot(nodes=[_widget_with_code()]), update_db=True)

    empty_widget = await Node.init(db=db, schema=widget_kind)
    await empty_widget.new(db=db, name="widget-without-code")
    await empty_widget.save(db=db)

    filled_widget = await Node.init(db=db, schema=widget_kind)
    await filled_widget.new(db=db, name="widget-with-code", code="filled")
    await filled_widget.save(db=db)

    branch = await create_branch(db=db, branch_name="newly-mandatory-branch")

    filled_on_branch = await NodeManager.get_one(db=db, id=filled_widget.id, branch=branch, raise_on_error=True)
    filled_on_branch.code.value = "refilled"
    await filled_on_branch.save(db=db)

    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[_widget_with_code(code_optional=False)]),
        branch_name=branch.name,
        update_db=True,
        limit=[widget_kind],
    )

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        with pytest.raises(ValidationError) as exc_info:
            await rebase_branch(branch=branch.name, context=context)

    assert exc_info.value.message == (
        f"Attribute-level 'optional' constraint violation on schema '{widget_kind}'."
        " Node (widget-without-code) is not compliant."
        " for constraint attribute.optional.update code optional"
        f" and node {empty_widget.id} {widget_kind}"
    )


async def test_rebase_reports_duplicates_when_an_attribute_becomes_unique(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Turning an attribute unique must be checked against nodes the branch never touched.

    The branch carries no data change whatsoever, so the duplicates already sitting on the
    destination are reachable only through the schema comparison between the two branches.
    """
    widget_kind = "TestingWidget"
    await load_schema(db=db, schema=SchemaRoot(nodes=[_widget_with_code()]), update_db=True)

    first_widget = await Node.init(db=db, schema=widget_kind)
    await first_widget.new(db=db, name="widget-one", code="same-code")
    await first_widget.save(db=db)

    second_widget = await Node.init(db=db, schema=widget_kind)
    await second_widget.new(db=db, name="widget-two", code="same-code")
    await second_widget.save(db=db)

    branch = await create_branch(db=db, branch_name="newly-unique-branch")

    await load_schema(
        db=db,
        schema=SchemaRoot(nodes=[_widget_with_code(code_unique=True)]),
        branch_name=branch.name,
        update_db=True,
        limit=[widget_kind],
    )

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        with pytest.raises(ValidationError) as exc_info:
            await rebase_branch(branch=branch.name, context=context)

    message = exc_info.value.message
    assert set(re.findall(r"and node (\S+) ", message)) == {first_widget.id, second_widget.id}
    assert set(re.findall(r"for constraint (\S+) ", message)) == {
        "attribute.unique.update",
        ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value,
    }
