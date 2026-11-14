"""Schema changes that stored data breaks are refused, on a schema load, a merge and a rebase.

One dataset and one app serve every case to keep the suite fast: each refused change leaves the
schema and the data as they were, so later tests start from the same state.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
)
from tests.helpers.number_pool import provision_schema_number_pools
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


WIDGET_KIND = "TestingWidget"
TICKET_KIND = "TestingTicket"
GADGET_KIND = "TestingGadget"
BADGE_KIND = "TestingBadge"
PASS_KIND = "TestingPass"
LABEL_KIND = "TestingLabel"
PLUG_KIND = "TestingPlug"
STICKER_KIND = "TestingSticker"
FUSE_KIND = "TestingFuse"
CABLE_KIND = "TestingCable"
PORT_KIND = "TestingPort"
PORT_POOL_NAME = "port-vlan-per-role"
CHIP_KIND = "TestingChip"
SWITCH_KIND = "TestingSwitch"
RELAY_KIND = "TestingRelay"
REGEX_REFUSAL = (
    "Attribute-level 'regex' constraint violation on schema 'TestingChip'."
    " Node (TestingChip: {node_id}) is not compliant. The error relates to field code='abc'."
)
ENUM_REFUSAL = (
    "Attribute-level 'enum' constraint violation on schema '{kind}'."
    " Node ({kind}: {node_id}) is not compliant. The error relates to field level='high'."
)
COUNTRY_KIND = "LocationCountry"
SITE_KIND = "LocationSite"

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""

BRANCH_REBASE_MUTATION = """
mutation($branch: String!) {
    BranchRebase(data: { name: $branch }) {
        ok
    }
}
"""


def _number(name: str) -> AttributeSchema:
    return AttributeSchema(
        name=name, kind="Number", optional=True, parameters=NumberAttributeParameters(min_value=0, max_value=10)
    )


def _node(
    name: str, attributes: list[AttributeSchema], relationships: tuple[RelationshipSchema, ...] = ()
) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Testing",
        include_in_menu=False,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True), *attributes],
        relationships=list(relationships),
    )


def _nodes_by_name(schema: SchemaRoot) -> dict[str, NodeSchema]:
    return {node.name: node for node in schema.nodes}


def _number_parameters(attribute: AttributeSchema) -> NumberAttributeParameters:
    assert isinstance(attribute.parameters, NumberAttributeParameters)
    return attribute.parameters


def _text_parameters(attribute: AttributeSchema) -> TextAttributeParameters:
    assert isinstance(attribute.parameters, TextAttributeParameters)
    return attribute.parameters


def _pool_parameters(attribute: AttributeSchema) -> NumberPoolParameters:
    assert isinstance(attribute.parameters, NumberPoolParameters)
    return attribute.parameters


def _registry_attribute(kind: str, attribute: str, branch: str) -> AttributeSchema:
    return registry.schema.get_node_schema(name=kind, branch=branch, duplicate=False).get_attribute(attribute)


async def _load_on_branch(client: InfrahubClient, schema: SchemaRoot, branch: Branch) -> None:
    response = await client.schema.load(schemas=[schema.model_dump(mode="json")], branch=branch.name)
    assert not response.errors


async def _create(db: InfrahubDatabase, kind: str, branch: Branch, name: str, **values: Any) -> Node:
    node = await Node.init(schema=kind, db=db, branch=branch)
    await node.new(db=db, name=name, **values)
    await node.save(db=db)
    return node


async def _stored_values(db: InfrahubDatabase, kind: str, attribute: str, branch: Branch) -> dict[str, object]:
    stored = await registry.manager.query(db=db, schema=kind, branch=branch)
    return {node.id: node.get_attribute(attribute).value for node in stored}


async def _assert_branch_open(db: InfrahubDatabase, branch: Branch) -> Branch:
    stored_branch = await Branch.get_by_name(db=db, name=branch.name)
    assert stored_branch.status == BranchStatus.OPEN
    return stored_branch


class TestSchemaChangeRefusedByStoredData(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_initial(self) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            generics=[
                GenericSchema(
                    name="Generic",
                    namespace="Location",
                    hierarchical=True,
                    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                )
            ],
            nodes=[
                _node("Person", []),
                _node("Team", []),
                _node(
                    "Widget",
                    [_number("low_max"), _number("high_min"), _number("excluded")],
                    relationships=(
                        RelationshipSchema(
                            name="owner", peer="TestingPerson", cardinality=RelationshipCardinality.ONE, optional=True
                        ),
                    ),
                ),
                _node(
                    "Ticket",
                    [
                        AttributeSchema(
                            name="ticket_number",
                            kind="NumberPool",
                            optional=False,
                            read_only=True,
                            parameters=NumberPoolParameters(start_range=1, end_range=100),
                        )
                    ],
                ),
                _node("Gadget", [_number("count")]),
                _node("Badge", [AttributeSchema(name="code", kind="Text", optional=True)]),
                _node("Pass", [AttributeSchema(name="code", kind="Text", optional=True)]),
                _node("Label", [AttributeSchema(name="text", kind="Text", optional=True)]),
                _node("Plug", []),
                _node("Sticker", [AttributeSchema(name="text", kind="Text", optional=True)]),
                _node("Fuse", []),
                _node("Cable", [AttributeSchema(name="color", kind="Text", optional=True)]),
                _node("Chip", [AttributeSchema(name="code", kind="Text", optional=True)]),
                _node("Switch", [AttributeSchema(name="level", kind="Text", enum=["low", "high"], optional=True)]),
                _node("Relay", [AttributeSchema(name="level", kind="Text", enum=["low", "high"], optional=True)]),
                _node(
                    "Port",
                    [
                        AttributeSchema(name="vlan_id", kind="Number", optional=True),
                        AttributeSchema(name="role", kind="Text", optional=False),
                    ],
                ),
                NodeSchema(
                    name="Country",
                    namespace="Location",
                    inherit_from=["LocationGeneric"],
                    parent="",
                    children="LocationSite",
                ),
                NodeSchema(
                    name="Site",
                    namespace="Location",
                    inherit_from=["LocationGeneric"],
                    parent="LocationCountry",
                    children="",
                ),
            ],
        )

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_initial: SchemaRoot
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_initial)
        await provision_schema_number_pools(db=db)

        person = await Node.init(schema="TestingPerson", db=db)
        await person.new(db=db, name="person-1")
        await person.save(db=db)

        widget = await Node.init(schema=WIDGET_KIND, db=db)
        await widget.new(db=db, name="widget-1", low_max=8, high_min=3, excluded=7, owner=person)
        await widget.save(db=db)

        ticket_ids = []
        for index in range(3):
            ticket = await Node.init(schema=TICKET_KIND, db=db)
            await ticket.new(db=db, name=f"ticket-{index}")
            await ticket.save(db=db)
            ticket_ids.append(ticket.id)

        country = await Node.init(schema=COUNTRY_KIND, db=db)
        await country.new(db=db, name="country-1")
        await country.save(db=db)
        site = await Node.init(schema=SITE_KIND, db=db)
        await site.new(db=db, name="site-1", parent=country)
        await site.save(db=db)

        return {
            "person": person.id,
            "widget": widget.id,
            "ticket_3": ticket_ids[2],
            "country": country.id,
            "site": site.id,
        }

    async def test_schema_load_on_main_is_refused_for_each_constraint(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        ticket = await registry.manager.get_one(db=db, id=initial_dataset["ticket_3"], branch=default_branch)
        assert ticket.get_attribute("ticket_number").value == 3

        schema = copy.deepcopy(schema_initial)
        nodes = _nodes_by_name(schema)
        widget = nodes["Widget"]
        _number_parameters(widget.get_attribute("low_max")).max_value = 5
        _number_parameters(widget.get_attribute("high_min")).min_value = 5
        _number_parameters(widget.get_attribute("excluded")).excluded_values = "7"
        widget.get_relationship("owner").peer = "TestingTeam"
        _pool_parameters(nodes["Ticket"].get_attribute("ticket_number")).end_range = 2
        nodes["Country"].children = "LocationMetro"
        nodes["Site"].parent = "LocationMetro"
        schema.nodes.append(
            NodeSchema(
                name="Metro",
                namespace="Location",
                inherit_from=["LocationGeneric"],
                parent="LocationCountry",
                children="LocationSite",
            )
        )

        response = await client.schema.load(schemas=[schema.model_dump(mode="json")], branch=default_branch.name)

        widget_label = f"Node (TestingWidget(ID: {initial_dataset['widget']})) is not compliant."
        assert len(response.errors["errors"]) == 1
        assert sorted(response.errors["errors"][0]["message"].split(",\n")) == sorted(
            [
                f"Attribute-level 'number' constraint violation on schema '{WIDGET_KIND}'. {widget_label}"
                " The error relates to field low_max=8.",
                f"Attribute-level 'number' constraint violation on schema '{WIDGET_KIND}'. {widget_label}"
                " The error relates to field high_min=3.",
                f"Attribute-level 'number' constraint violation on schema '{WIDGET_KIND}'. {widget_label}"
                " The error relates to field excluded=7.",
                f"Relationship-level 'peer' constraint violation on schema '{WIDGET_KIND}'. {widget_label}"
                f" The error relates to field owner.id={initial_dataset['person']}.",
                f"Attribute-level 'number_pool' constraint violation on schema '{TICKET_KIND}'."
                f" Node (TestingTicket(ID: {initial_dataset['ticket_3']})) is not compliant."
                " The error relates to field ticket_number=3.",
                f"Node-level 'hierarchy' constraint violation on schema '{SITE_KIND}'."
                f" Node (LocationSite(ID: {initial_dataset['site']})) is not compliant."
                f" The error relates to field parent.id={initial_dataset['country']}.",
                f"Node-level 'hierarchy' constraint violation on schema '{COUNTRY_KIND}'."
                f" Node (LocationCountry(ID: {initial_dataset['country']})) is not compliant."
                f" The error relates to field children.id={initial_dataset['site']}.",
                f"Relationship-level 'peer' constraint violation on schema '{SITE_KIND}'."
                f" Node (LocationSite(ID: {initial_dataset['site']})) is not compliant."
                f" The error relates to field parent.id={initial_dataset['country']}.",
                f"Relationship-level 'peer' constraint violation on schema '{COUNTRY_KIND}'."
                f" Node (LocationCountry(ID: {initial_dataset['country']})) is not compliant."
                f" The error relates to field children.id={initial_dataset['site']}.",
            ]
        )

        assert _number_parameters(_registry_attribute(WIDGET_KIND, "low_max", default_branch.name)).max_value == 10
        pool_after = _pool_parameters(_registry_attribute(TICKET_KIND, "ticket_number", default_branch.name))
        assert pool_after.end_range == 100
        assert registry.schema.get_node_schema(name=SITE_KIND, branch=default_branch.name).parent == COUNTRY_KIND
        stored_widget = await registry.manager.get_one(db=db, id=initial_dataset["widget"], branch=default_branch)
        assert stored_widget.get_attribute("low_max").value == 8

    async def test_merge_is_refused_when_a_value_on_main_breaks_a_limit_lowered_on_the_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        """The value is created on main after the branch, so the branch cannot view it when it lowers the limit."""
        branch = await create_branch(db=db, branch_name="lower-gadget-max")

        branch_schema = copy.deepcopy(schema_initial)
        _number_parameters(_nodes_by_name(branch_schema)["Gadget"].get_attribute("count")).max_value = 5
        response = await client.schema.load(schemas=[branch_schema.model_dump(mode="json")], branch=branch.name)
        assert not response.errors

        gadget = await Node.init(schema=GADGET_KIND, db=db, branch=default_branch)
        await gadget.new(db=db, name="gadget-8", count=8)
        await gadget.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch.name})

        assert [error["message"] for error in exc.value.errors] == [
            f"Attribute-level 'number' constraint violation on schema '{GADGET_KIND}'."
            f" Node ({GADGET_KIND}: {gadget.id}) is not compliant. The error relates to field count=8."
        ]

        assert _number_parameters(_registry_attribute(GADGET_KIND, "count", default_branch.name)).max_value == 10
        stored_gadget = await registry.manager.get_one(db=db, id=gadget.id, branch=default_branch)
        assert stored_gadget.get_attribute("count").value == 8

    async def test_merge_is_refused_for_each_branch_schema_change_that_a_node_created_on_main_breaks(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        """The nodes and the pool are created on main after the branch, so the branch cannot view them."""
        branch = await create_branch(db=db, branch_name="merge-branch-schema-changes")
        branch_schema = copy.deepcopy(schema_initial)
        nodes = _nodes_by_name(branch_schema)
        nodes["Badge"].get_attribute("code").unique = True
        nodes["Label"].get_attribute("text").optional = False
        nodes["Plug"].attributes.append(AttributeSchema(name="voltage", kind="Text", optional=False))
        nodes["Port"].get_attribute("role").optional = True
        _text_parameters(nodes["Chip"].get_attribute("code")).regex = "^[A-Z]+$"
        nodes["Switch"].get_attribute("level").enum = ["low"]
        await _load_on_branch(client=client, schema=branch_schema, branch=branch)

        badges = [
            await _create(db=db, kind=BADGE_KIND, branch=default_branch, name=f"badge-{index}", code="B-1")
            for index in (1, 2)
        ]
        label = await _create(db=db, kind=LABEL_KIND, branch=default_branch, name="label-1")
        plug = await _create(db=db, kind=PLUG_KIND, branch=default_branch, name="plug-1")
        chip = await _create(db=db, kind=CHIP_KIND, branch=default_branch, name="chip-1", code="abc")
        switch = await _create(db=db, kind=SWITCH_KIND, branch=default_branch, name="switch-1", level="high")
        pool = await client.create(
            kind=InfrahubKind.NUMBERPOOL,
            name=PORT_POOL_NAME,
            node=PORT_KIND,
            node_attribute="vlan_id",
            start_range=1,
            end_range=10,
            allocation_scope=["role"],
        )
        await pool.save()

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch.name})

        assert len(exc.value.errors) == 1
        assert sorted(exc.value.errors[0]["message"].split(",\n")) == sorted(
            [
                *(
                    f"Attribute-level 'unique' constraint violation on schema '{BADGE_KIND}'."
                    f" Node ({BADGE_KIND}: {badge.id}) is not compliant. The error relates to field code='B-1'."
                    for badge in badges
                ),
                *(
                    f"Node-level 'uniqueness_constraints' constraint violation on schema '{BADGE_KIND}'."
                    f" Node ({BADGE_KIND}: {badge.id}) is not compliant. The error relates to field code.value='B-1'."
                    for badge in badges
                ),
                f"Attribute-level 'optional' constraint violation on schema '{LABEL_KIND}'."
                f" Node ({LABEL_KIND}: {label.id}) is not compliant.",
                f"Node-level 'attribute' constraint violation on schema '{PLUG_KIND}'."
                f" Node ({PLUG_KIND}: {plug.id}) is not compliant.",
                f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'."
                f" Node ({PORT_POOL_NAME}) is not compliant. The error relates to field role='pool {PORT_POOL_NAME}"
                f" divides its numbers by {PORT_KIND}.role; a scope element must stay required'.",
                REGEX_REFUSAL.format(node_id=chip.id),
                ENUM_REFUSAL.format(kind=SWITCH_KIND, node_id=switch.id),
            ]
        )
        await _assert_branch_open(db=db, branch=branch)
        assert _registry_attribute(BADGE_KIND, "code", default_branch.name).unique is False
        assert _registry_attribute(LABEL_KIND, "text", default_branch.name).optional is True
        main_plug_schema = registry.schema.get_node_schema(name=PLUG_KIND, branch=default_branch.name, duplicate=False)
        assert main_plug_schema.attribute_names == ["name"]
        assert _registry_attribute(PORT_KIND, "role", default_branch.name).optional is False
        assert _registry_attribute(CHIP_KIND, "code", default_branch.name).get_regex() is None
        assert _registry_attribute(SWITCH_KIND, "level", default_branch.name).enum == ["low", "high"]
        assert await _stored_values(db=db, kind=BADGE_KIND, attribute="code", branch=default_branch) == {
            badge.id: "B-1" for badge in badges
        }
        assert await registry.manager.query(db=db, schema=BADGE_KIND, branch=branch) == []

    async def test_rebase_is_refused_for_each_branch_schema_change_that_a_node_created_on_main_breaks(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        """The nodes are created on main after the branch, so the branch cannot view them."""
        branch = await create_branch(db=db, branch_name="rebase-branch-schema-changes")
        branch_schema = copy.deepcopy(schema_initial)
        nodes = _nodes_by_name(branch_schema)
        nodes["Pass"].get_attribute("code").unique = True
        nodes["Sticker"].get_attribute("text").optional = False
        nodes["Relay"].get_attribute("level").enum = ["low"]
        await _load_on_branch(client=client, schema=branch_schema, branch=branch)
        branched_from = branch.branched_from

        passes = [
            await _create(db=db, kind=PASS_KIND, branch=default_branch, name=f"pass-{index}", code="P-1")
            for index in (1, 2)
        ]
        sticker = await _create(db=db, kind=STICKER_KIND, branch=default_branch, name="sticker-1")
        relay = await _create(db=db, kind=RELAY_KIND, branch=default_branch, name="relay-1", level="high")

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_REBASE_MUTATION, variables={"branch": branch.name})

        assert len(exc.value.errors) == 1
        assert sorted(exc.value.errors[0]["message"].split(",\n")) == sorted(
            [
                *(
                    f"Attribute-level 'unique' constraint violation on schema '{PASS_KIND}'."
                    f" Node ({PASS_KIND}: {node.id}) is not compliant. The error relates to field code='P-1'."
                    f" for constraint attribute.unique.update code unique and node {node.id} {PASS_KIND}"
                    for node in passes
                ),
                *(
                    f"Node-level 'uniqueness_constraints' constraint violation on schema '{PASS_KIND}'."
                    f" Node ({PASS_KIND}: {node.id}) is not compliant. The error relates to field code.value='P-1'."
                    " for constraint node.uniqueness_constraints.update uniqueness_constraints uniqueness_constraints"
                    f" and node {node.id} {PASS_KIND}"
                    for node in passes
                ),
                f"Attribute-level 'optional' constraint violation on schema '{STICKER_KIND}'."
                f" Node ({STICKER_KIND}: {sticker.id}) is not compliant."
                f" for constraint attribute.optional.update text optional and node {sticker.id} {STICKER_KIND}",
                ENUM_REFUSAL.format(kind=RELAY_KIND, node_id=relay.id)
                + f" for constraint attribute.enum.update level enum and node {relay.id} {RELAY_KIND}",
            ]
        )
        stored_branch = await _assert_branch_open(db=db, branch=branch)
        assert stored_branch.branched_from == branched_from
        assert _registry_attribute(PASS_KIND, "code", default_branch.name).unique is False
        assert _registry_attribute(STICKER_KIND, "text", branch.name).optional is False
        assert await registry.manager.query(db=db, schema=PASS_KIND, branch=branch) == []

    async def test_merge_is_accepted_when_the_branch_sets_a_value_on_every_node_a_mandatory_attribute_needs(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        """The branch adds a mandatory attribute before it creates its nodes, and sets the value of a node from main."""
        cable = await _create(db=db, kind=CABLE_KIND, branch=default_branch, name="cable-1")
        branch = await create_branch(db=db, branch_name="mandatory-values-set-on-branch")
        cable_on_branch = await registry.manager.get_one(db=db, id=cable.id, branch=branch)
        cable_on_branch.get_attribute("color").value = "blue"
        await cable_on_branch.save(db=db)
        branch_schema = copy.deepcopy(schema_initial)
        nodes = _nodes_by_name(branch_schema)
        nodes["Fuse"].attributes.append(AttributeSchema(name="rating", kind="Text", optional=False))
        nodes["Cable"].get_attribute("color").optional = False
        await _load_on_branch(client=client, schema=branch_schema, branch=branch)
        first = await _create(db=db, kind=FUSE_KIND, branch=branch, name="fuse-1", rating="10A")
        second = await _create(db=db, kind=FUSE_KIND, branch=branch, name="fuse-2", rating="16A")
        assert await _stored_values(db=db, kind=CABLE_KIND, attribute="color", branch=default_branch) == {
            cable.id: None
        }

        response = await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch.name})

        assert response == {"BranchMerge": {"ok": True}}
        assert _registry_attribute(FUSE_KIND, "rating", default_branch.name).optional is False
        assert _registry_attribute(CABLE_KIND, "color", default_branch.name).optional is False
        assert await _stored_values(db=db, kind=FUSE_KIND, attribute="rating", branch=default_branch) == {
            first.id: "10A",
            second.id: "16A",
        }
        assert await _stored_values(db=db, kind=CABLE_KIND, attribute="color", branch=default_branch) == {
            cable.id: "blue"
        }

    async def test_schema_load_renaming_a_hierarchical_kind_with_stored_nodes_is_accepted(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        schema_initial: SchemaRoot,
    ) -> None:
        """Renaming hierarchical kinds with stored nodes is accepted."""
        country_id = registry.schema.get_node_schema(name=COUNTRY_KIND, branch=default_branch.name).id
        schema = copy.deepcopy(schema_initial)
        nodes = _nodes_by_name(schema)
        nodes["Country"].id = country_id
        nodes["Country"].name = "Nation"
        nodes["Site"].parent = "LocationNation"

        response = await client.schema.load(schemas=[schema.model_dump(mode="json")], branch=default_branch.name)

        assert not response.errors
        site_schema = registry.schema.get_node_schema(name=SITE_KIND, branch=default_branch.name)
        assert site_schema.parent == "LocationNation"
        stored_site = await registry.manager.get_one(db=db, id=initial_dataset["site"], branch=default_branch)
        site_parent = await stored_site.get_relationship("parent").get_peer(db=db, raise_on_error=True)
        assert site_parent.get_id() == initial_dataset["country"]
        assert site_parent.get_kind() == "LocationNation"
