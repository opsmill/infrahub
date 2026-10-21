"""Schema changes that stored data breaks are refused, on a schema load and on a merge.

One dataset and one app serve every case to keep the suite fast: each refused change leaves the
schema and the data as they were, so later tests start from the same state.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters, NumberPoolParameters
from infrahub.log import get_logger
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

log = get_logger()

WIDGET_KIND = "TestingWidget"
TICKET_KIND = "TestingTicket"
GADGET_KIND = "TestingGadget"
COUNTRY_KIND = "LocationCountry"
SITE_KIND = "LocationSite"

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
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


def _pool_parameters(attribute: AttributeSchema) -> NumberPoolParameters:
    assert isinstance(attribute.parameters, NumberPoolParameters)
    return attribute.parameters


def _registry_attribute(kind: str, attribute: str, branch: str) -> AttributeSchema:
    return registry.schema.get_node_schema(name=kind, branch=branch, duplicate=False).get_attribute(attribute)


def _with_pool_id(schema: SchemaRoot, branch: str) -> SchemaRoot:
    """Copy the schema with the id of the provisioned pool, since a schema load cannot change it."""
    pool_id = _pool_parameters(_registry_attribute(TICKET_KIND, "ticket_number", branch)).number_pool_id
    schema = copy.deepcopy(schema)
    _pool_parameters(_nodes_by_name(schema)["Ticket"].get_attribute("ticket_number")).number_pool_id = pool_id
    return schema


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
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        await SchemaNumberPoolSynchronizer(db=db, log=log, schema_manager=registry.schema, upserter=upserter).run()

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

        schema = _with_pool_id(schema_initial, default_branch.name)
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

        branch_schema = _with_pool_id(schema_initial, branch.name)
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
