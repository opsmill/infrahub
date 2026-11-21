from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.database import InfrahubDatabase
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD


async def test_gather_trigger_gather_trigger_display_labels_jinja2_default(
    register_core_models_schema: None, default_branch: Branch
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.process()
    triggers = await gather_trigger_display_labels_jinja2()

    expected_names = {
        f"{target_kind}::by::{related_kind}"
        for related_kind, relationship_trigger in schema_branch.display_labels.get_related_trigger_nodes().items()
        for identifiers in relationship_trigger.attributes.values()
        for target_kind in {identifier.kind for identifier in identifiers}
    }

    assert {trigger.name for trigger in triggers} == expected_names
    assert all(
        trigger.trigger.match_related["infrahub.field.name"] != [TRIGGER_PLACEHOLDER_FIELD] for trigger in triggers
    )


async def test_gather_trigger_gather_trigger_display_labels_jinja2_custom_schema(
    register_core_models_schema: None, default_branch: Branch, db: InfrahubDatabase
) -> None:
    SCHEMA = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Car",
                namespace="Test",
                display_label="{{ name__value }}: {{ owner__name__value }}",
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        unique=True,
                    ),
                    AttributeSchema(
                        name="nbr_seats",
                        kind="Number",
                    ),
                ],
                relationships=[
                    RelationshipSchema(
                        name="owner",
                        peer="TestPerson",
                        optional=False,
                        cardinality=RelationshipCardinality.ONE,
                    ),
                ],
            ),
            NodeSchema(
                name="Person",
                namespace="Test",
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        unique=True,
                    ),
                ],
                relationships=[
                    RelationshipSchema(
                        name="cars",
                        peer="TestCar",
                        cardinality=RelationshipCardinality.MANY,
                    ),
                ],
            ),
        ]
    )

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    triggers = await gather_trigger_display_labels_jinja2()
    test_car_triggers = [trigger for trigger in triggers if trigger.name.startswith("TestCar::")]
    test_person_triggers = [trigger for trigger in triggers if trigger.name == "TestCar::by::TestPerson"]

    assert test_car_triggers == test_person_triggers
    assert len(test_person_triggers) == 1
    test_person_trigger = test_person_triggers[0]

    assert not test_person_trigger.target_kind  # Related triggers doesn't have a target_kind defined
    assert test_person_trigger.trigger.events == {NodeUpdatedEvent.event_name}
    assert test_person_trigger.trigger.match == {"infrahub.node.kind": "TestPerson", "infrahub.node.origin": "live"}
    assert isinstance(test_person_trigger.trigger.match_related, dict)
    assert "infrahub.field.name" in test_person_trigger.trigger.match_related
    assert test_person_trigger.trigger.match_related["infrahub.field.name"] == ["name"]
