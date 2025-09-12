from uuid import uuid4

from infrahub.actions.gather import gather_trigger_action_rules
from infrahub.core.node import Node
from infrahub.core.protocols import (
    CoreGeneratorAction,
    CoreGeneratorDefinition,
    CoreGraphQLQuery,
    CoreGroupAction,
    CoreGroupTriggerRule,
    CoreNodeTriggerAttributeMatch,
    CoreNodeTriggerRelationshipMatch,
    CoreNodeTriggerRule,
    CoreRepository,
    CoreStandardGroup,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.trigger.models import EventTrigger


async def test_gather_trigger_gather_trigger_action_rules_empty(
    register_core_models_schema: SchemaBranch, db: InfrahubDatabase
) -> None:
    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 0


async def test_gather_trigger_gather_trigger_action_rules_node_attribute(
    register_core_models_schema: SchemaBranch, db: InfrahubDatabase
) -> None:
    group_action_target = await Node.init(db=db, schema=CoreStandardGroup)
    await group_action_target.new(db=db, name="GroupActionTarget")
    await group_action_target.save(db=db)

    group_action = await Node.init(db=db, schema=CoreGroupAction)
    await group_action.new(db=db, name="MainGroupAction", group=group_action_target)
    await group_action.save(db=db)

    main_node_trigger_rule = await Node.init(db=db, schema=CoreNodeTriggerRule)
    await main_node_trigger_rule.new(
        db=db,
        name="main_node_trigger",
        node_kind="BuiltinTag",
        mutation_action="updated",
        action=group_action,
        branch_scope="default_branch",
    )
    await main_node_trigger_rule.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "main"},
        match_related={},
    )

    attribute_match = await Node.init(db=db, schema=CoreNodeTriggerAttributeMatch)
    await attribute_match.new(
        db=db,
        attribute_name="description",
        value="something_new",
        value_previous="something_old",
        value_match="value",
        trigger=main_node_trigger_rule,
    )
    await attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]
    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value": "something_new",
            }
        ],
    )

    attribute_match.value_match.value = "value_previous"
    await attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]
    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value_previous": "something_old",
            }
        ],
    )

    attribute_match.value_match.value = "value_full"
    await attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value": "something_new",
                "infrahub.attribute.value_previous": "something_old",
            }
        ],
    )

    attribute_match.value_match.value = "any"
    await attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
            }
        ],
    )

    main_node_trigger_rule.branch_scope.value = "other_branches"
    await main_node_trigger_rule.save(db=db)

    attribute_match.value_match.value = "value_full"
    await attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "!main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value": "something_new",
                "infrahub.attribute.value_previous": "something_old",
            }
        ],
    )

    second_attribute_match = await Node.init(db=db, schema=CoreNodeTriggerAttributeMatch)
    await second_attribute_match.new(
        db=db,
        attribute_name="another_attribute",
        value="the-new-value",
        value_previous="the-old-value",
        value_match="value_full",
        trigger=main_node_trigger_rule,
    )
    await second_attribute_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "BuiltinTag", "infrahub.branch.name": "!main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "description",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value": "something_new",
                "infrahub.attribute.value_previous": "something_old",
            },
            {
                "prefect.resource.role": "infrahub.node.attribute_update",
                "infrahub.field.name": "another_attribute",
                "infrahub.attribute.action": ["added", "updated", "removed"],
                "infrahub.attribute.value": "the-new-value",
                "infrahub.attribute.value_previous": "the-old-value",
            },
        ],
    )

    main_node_trigger_rule.active.value = False
    await main_node_trigger_rule.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 0


async def test_gather_trigger_gather_trigger_action_rules_node_relationship(
    register_core_models_schema: SchemaBranch, car_person_schema: SchemaBranch, db: InfrahubDatabase
) -> None:
    group_action_target = await Node.init(db=db, schema=CoreStandardGroup)
    await group_action_target.new(db=db, name="GroupActionTarget")
    await group_action_target.save(db=db)

    group_action = await Node.init(db=db, schema=CoreGroupAction)
    await group_action.new(db=db, name="MainGroupAction", group=group_action_target)
    await group_action.save(db=db)

    car_owner = await Node.init(db=db, schema="TestPerson")
    await car_owner.new(db=db, name="Bobby")
    await car_owner.save(db=db)

    main_node_trigger_rule = await Node.init(db=db, schema=CoreNodeTriggerRule)
    await main_node_trigger_rule.new(
        db=db,
        name="main_node_trigger",
        node_kind="TestCar",
        mutation_action="created",
        action=group_action,
        branch_scope="all_branches",
    )
    await main_node_trigger_rule.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.created"},
        match={"infrahub.node.kind": "TestCar"},
        match_related={},
    )

    relationship_match = await Node.init(db=db, schema=CoreNodeTriggerRelationshipMatch)
    await relationship_match.new(
        db=db,
        relationship_name="owner",
        peer=car_owner.id,
        trigger=main_node_trigger_rule,
    )
    await relationship_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]
    assert automation.trigger == EventTrigger(
        events={"infrahub.node.created"},
        match={"infrahub.node.kind": "TestCar"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.relationship_update",
                "infrahub.field.name": "owner",
                "infrahub.relationship.peer_id": car_owner.id,
                "infrahub.relationship.peer_status": "added",
            }
        ],
    )

    relationship_match.modification_type.value = "removed"
    await relationship_match.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]
    assert automation.trigger == EventTrigger(
        events={"infrahub.node.created"},
        match={"infrahub.node.kind": "TestCar"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.relationship_update",
                "infrahub.field.name": "owner",
                "infrahub.relationship.peer_id": car_owner.id,
                "infrahub.relationship.peer_status": "removed",
            }
        ],
    )

    main_node_trigger_rule.branch_scope.value = "other_branches"
    main_node_trigger_rule.mutation_action.value = "updated"
    await main_node_trigger_rule.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.node.updated"},
        match={"infrahub.node.kind": "TestCar", "infrahub.branch.name": "!main"},
        match_related=[
            {
                "prefect.resource.role": "infrahub.node.relationship_update",
                "infrahub.field.name": "owner",
                "infrahub.relationship.peer_id": car_owner.id,
                "infrahub.relationship.peer_status": "removed",
            }
        ],
    )

    main_node_trigger_rule.active.value = False
    await main_node_trigger_rule.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 0


async def test_gather_trigger_gather_trigger_action_rules_group_generators(
    register_core_models_schema: SchemaBranch, db: InfrahubDatabase
) -> None:
    repo = await Node.init(db=db, schema=CoreRepository)
    await repo.new(db=db, name="repo1", location=f"/tmp/{uuid4()}")
    await repo.save(db=db)

    query1 = await Node.init(db=db, schema=CoreGraphQLQuery)
    await query1.new(db=db, name="query1", repository=repo, query="{ __typename }")
    await query1.save(db=db)

    generator_target = await Node.init(db=db, schema=CoreStandardGroup)
    await generator_target.new(db=db, name="GeneratorTargets")
    await generator_target.save(db=db)

    generator_definition = await Node.init(db=db, schema=CoreGeneratorDefinition)
    await generator_definition.new(
        db=db,
        name="generator_definition",
        query=query1,
        targets=generator_target,
        repository=repo,
        file_path="generator/mygen.py",
        class_name="FakeGenerator",
        parameters="{}",
    )
    await generator_definition.save(db=db)

    generator_action = await Node.init(db=db, schema=CoreGeneratorAction)
    await generator_action.new(db=db, name="generator_action", generator=generator_definition)
    await generator_action.save(db=db)

    group_trigger = await Node.init(db=db, schema=CoreGroupTriggerRule)
    await group_trigger.new(
        db=db,
        name="group_trigger_rule",
        branch_scope="default_branch",
        members_added=True,
        group=generator_target,
        action=generator_action,
    )
    await group_trigger.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.group.member_added"},
        match={
            "infrahub.node.kind": "CoreStandardGroup",
            "infrahub.node.id": generator_target.id,
            "infrahub.branch.name": "main",
        },
        match_related={},
    )
    assert len(automation.actions) == 1
    action = automation.actions[0]
    assert action.parameters["generator_definition_id"] == generator_definition.id

    group_trigger.member_update.value = "removed"
    group_trigger.branch_scope.value = "other_branches"
    await group_trigger.save(db=db)

    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 1
    automation = triggers[0]

    assert automation.trigger == EventTrigger(
        events={"infrahub.group.member_removed"},
        match={
            "infrahub.node.kind": "CoreStandardGroup",
            "infrahub.node.id": generator_target.id,
            "infrahub.branch.name": "!main",
        },
        match_related={},
    )
    assert len(automation.actions) == 1
    action = automation.actions[0]
    assert action.parameters["generator_definition_id"] == generator_definition.id

    group_trigger.active.value = False
    await group_trigger.save(db=db)
    triggers = await gather_trigger_action_rules(db=db)
    assert len(triggers) == 0
