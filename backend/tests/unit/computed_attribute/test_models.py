import uuid
from datetime import timedelta

import pytest
from prefect.events.schemas.automations import Automation, EventTrigger, Posture

from infrahub.computed_attribute.constants import (
    PROCESS_AUTOMATION_NAME,
    PROCESS_AUTOMATION_NAME_PREFIX,
    QUERY_AUTOMATION_NAME,
    QUERY_AUTOMATION_NAME_PREFIX,
)
from infrahub.computed_attribute.models import ComputedAttributeAutomations, ComputedAttrJinja2GraphQL
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema


def generate_automation(
    name: str, description: str = "", trigger: EventTrigger | None = None, actions: list | None = None
) -> Automation:
    default_trigger = EventTrigger(
        posture=Posture.Reactive,
        expect={"infrahub.node.*"},
        within=timedelta(0),
        threshold=1,
    )

    return Automation(
        id=uuid.uuid4(),
        name=name,
        description=description,
        enabled=True,
        trigger=trigger or default_trigger,
        actions=actions or [],
    )


async def test_load_from_prefect() -> None:
    automations: list[Automation] = [
        generate_automation(
            name=PROCESS_AUTOMATION_NAME.format(
                prefix=PROCESS_AUTOMATION_NAME_PREFIX, identifier="AAAAA", scope="default"
            )
        ),
        generate_automation(
            name=PROCESS_AUTOMATION_NAME.format(prefix=PROCESS_AUTOMATION_NAME_PREFIX, identifier="AAAAA", scope="yyyy")
        ),
        generate_automation(
            name=PROCESS_AUTOMATION_NAME.format(
                prefix=PROCESS_AUTOMATION_NAME_PREFIX, identifier="BBBBB", scope="default"
            )
        ),
        generate_automation(
            name=QUERY_AUTOMATION_NAME.format(prefix=QUERY_AUTOMATION_NAME_PREFIX, identifier="CCCCC", scope="default")
        ),
        generate_automation(name="anothername"),
    ]

    obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=PROCESS_AUTOMATION_NAME_PREFIX)
    query_obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=QUERY_AUTOMATION_NAME_PREFIX)

    assert obj.has(identifier="AAAAA", scope="default")
    assert obj.has(identifier="AAAAA", scope="yyyy")
    assert obj.has(identifier="BBBBB", scope="default")
    assert not obj.has(identifier="CCCCC", scope="default")

    query_obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=QUERY_AUTOMATION_NAME_PREFIX)
    assert not query_obj.has(identifier="AAAAA", scope="default")
    assert query_obj.has(identifier="CCCCC", scope="default")


def test_query_fields_uses_inline_fragment_for_hierarchical_relationship() -> None:
    """query_fields wraps peer-only attributes in an inline fragment when the relationship is hierarchical."""
    site_schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="shortname", kind="Text"),
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="parent",
                peer="TestingCountry",
                hierarchical="TestingLocation",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = ComputedAttrJinja2GraphQL(
        node_schema=site_schema,
        attribute_schema=site_schema.get_attribute(name="slug"),
        variables=["parent__slug__value", "shortname__value"],
    )

    fields = graphql_obj.query_fields

    # shortname is a direct attribute — should be at the top level
    assert fields["shortname"] == {"value": None}

    # parent.node must use an inline fragment for the concrete peer type
    parent_node = fields["parent"]["node"]
    assert "... on TestingCountry" in parent_node, (
        f"Expected inline fragment '... on TestingCountry' in parent node fields, got: {parent_node}"
    )
    assert parent_node["... on TestingCountry"]["slug"] == {"value": None}

    # The rendered query must contain the inline fragment syntax
    rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
    assert "... on TestingCountry" in rendered


def test_query_fields_no_fragment_for_non_hierarchical_relationship() -> None:
    """query_fields places attributes directly under node when the relationship is not hierarchical."""
    schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestingCountry",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = ComputedAttrJinja2GraphQL(
        node_schema=schema,
        attribute_schema=schema.get_attribute(name="slug"),
        variables=["owner__name__value"],
    )

    fields = graphql_obj.query_fields
    parent_node = fields["owner"]["node"]

    assert "name" in parent_node
    assert parent_node["name"] == {"value": None}
    assert not any(k.startswith("... on") for k in parent_node)

    rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
    assert "... on" not in rendered


def test_query_fields_no_fragment_when_peer_equals_hierarchical() -> None:
    """query_fields places attributes directly under node when peer is the hierarchy generic itself."""
    schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="parent",
                peer="TestingLocation",
                hierarchical="TestingLocation",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = ComputedAttrJinja2GraphQL(
        node_schema=schema,
        attribute_schema=schema.get_attribute(name="slug"),
        variables=["parent__name__value"],
    )

    fields = graphql_obj.query_fields
    parent_node = fields["parent"]["node"]

    assert "name" in parent_node
    assert parent_node["name"] == {"value": None}
    assert not any(k.startswith("... on") for k in parent_node)

    rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
    assert "... on" not in rendered
