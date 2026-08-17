import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from prefect.events.schemas.automations import Automation, Posture
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger

from infrahub import config
from infrahub.computed_attribute.constants import (
    PROCESS_AUTOMATION_NAME,
    PROCESS_AUTOMATION_NAME_PREFIX,
    QUERY_AUTOMATION_NAME,
    QUERY_AUTOMATION_NAME_PREFIX,
)
from infrahub.computed_attribute.models import (
    ComputedAttributeAutomations,
    ComputedAttrJinja2GraphQL,
    _restrict_to_live_origin,
)
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.trigger.models import EventTrigger


@pytest.fixture
def coalescing_disabled() -> Iterator[None]:
    original = config.SETTINGS.main.coalesce_python_recompute_after_merge
    config.SETTINGS.main.coalesce_python_recompute_after_merge = False
    yield
    config.SETTINGS.main.coalesce_python_recompute_after_merge = original


def test_python_automations_ignore_a_merge_when_the_pass_covers_it() -> None:
    """A merge writes with its own origin, and the coalesced pass is what refreshes those nodes.

    Leaving the automation open to them is the per-node fan-out this feature removes.
    """
    event_trigger = EventTrigger(match={"infrahub.node.kind": "TestingTShirt"})

    _restrict_to_live_origin(event_trigger)

    assert event_trigger.match[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE.value


@pytest.mark.usefixtures("coalescing_disabled")
def test_python_automations_stay_open_to_every_origin_when_the_switch_is_off() -> None:
    """Turning the switch off has to give back today's behaviour, automations included."""
    event_trigger = EventTrigger(match={"infrahub.node.kind": "TestingTShirt"})

    _restrict_to_live_origin(event_trigger)

    assert NODE_ORIGIN_LABEL not in event_trigger.match
    assert event_trigger.match == {"infrahub.node.kind": "TestingTShirt"}


def _build_schema(
    relationship_name: str = "parent",
    peer: str = "TestingCountry",
    hierarchical: str | None = "TestingLocation",
) -> NodeSchema:
    return NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="shortname", kind="Text"),
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name=relationship_name,
                peer=peer,
                hierarchical=hierarchical,
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )


def generate_automation(
    name: str, description: str = "", trigger: PrefectEventTrigger | None = None, actions: list | None = None
) -> Automation:
    default_trigger = PrefectEventTrigger(
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


class TestQueryFieldsInlineFragment:
    def test_uses_fragment_when_peer_differs_from_hierarchical(self) -> None:
        """query_fields wraps attributes in an inline fragment when peer != hierarchical."""
        schema = _build_schema(peer="TestingCountry", hierarchical="TestingLocation")
        graphql_obj = ComputedAttrJinja2GraphQL(
            node_schema=schema,
            attribute_schema=schema.get_attribute(name="slug"),
            variables=["parent__slug__value", "shortname__value"],
        )

        fields = graphql_obj.query_fields

        assert fields["shortname"] == {"value": None}
        parent_node = fields["parent"]["node"]
        assert "... on TestingCountry" in parent_node, (
            f"Expected inline fragment '... on TestingCountry' in parent node fields, got: {parent_node}"
        )
        assert parent_node["... on TestingCountry"]["slug"] == {"value": None}

        rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
        assert "... on TestingCountry" in rendered

    def test_no_fragment_for_non_hierarchical_relationship(self) -> None:
        """query_fields places attributes directly under node when relationship is not hierarchical."""
        schema = _build_schema(relationship_name="owner", peer="TestingCountry", hierarchical=None)
        graphql_obj = ComputedAttrJinja2GraphQL(
            node_schema=schema,
            attribute_schema=schema.get_attribute(name="slug"),
            variables=["owner__name__value"],
        )

        fields = graphql_obj.query_fields
        owner_node = fields["owner"]["node"]

        assert owner_node["name"] == {"value": None}
        assert not any(k.startswith("... on") for k in owner_node)

        rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
        assert "... on" not in rendered

    def test_no_fragment_when_peer_equals_hierarchical(self) -> None:
        """query_fields places attributes directly under node when peer is the hierarchy generic itself."""
        schema = _build_schema(peer="TestingLocation", hierarchical="TestingLocation")
        graphql_obj = ComputedAttrJinja2GraphQL(
            node_schema=schema,
            attribute_schema=schema.get_attribute(name="slug"),
            variables=["parent__name__value"],
        )

        fields = graphql_obj.query_fields
        parent_node = fields["parent"]["node"]

        assert parent_node["name"] == {"value": None}
        assert not any(k.startswith("... on") for k in parent_node)

        rendered = graphql_obj.render_graphql_query(query_filter="ids", filter_id="abc-123")
        assert "... on" not in rendered
