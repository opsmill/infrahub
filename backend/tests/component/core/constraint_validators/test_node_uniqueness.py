import re

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.node.constraints.uniqueness_violation_message import UniquenessViolationMessageBuilder
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import UniquenessViolationError


async def test_node_validate_constraint_node_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeGroupedUniquenessConstraint(
        db=db,
        branch=default_branch,
        message_builder=UniquenessViolationMessageBuilder(
            schema_branch=registry.schema.get_schema_branch(default_branch.name)
        ),
    )
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(UniquenessViolationError) as exc:
        await constraint.check(new_john)

    assert "Violates uniqueness constraint 'name'" in exc.value.message


async def test_node_validate_constraint_attribute_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(UniquenessViolationError) as exc:
        await constraint.check(new_john)

    assert "An object already exist with this value" in exc.value.message


async def test_node_validate_constraint_node_uniqueness_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeGroupedUniquenessConstraint(
        db=db,
        branch=default_branch,
        message_builder=UniquenessViolationMessageBuilder(
            schema_branch=registry.schema.get_schema_branch(default_branch.name)
        ),
    )
    alfred = await Node.init(db=db, schema="TestPerson", branch=default_branch)

    await alfred.new(db=db, name="Alfred", height=160)

    await constraint.check(alfred)


async def test_hierarchical_uniqueness_constraint(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema_simple_unregistered: SchemaRoot
) -> None:
    site_schema = hierarchical_location_schema_simple_unregistered.get(name="LocationSite")
    site_schema.human_friendly_id = ["parent__name__value", "name__value"]
    site_schema.uniqueness_constraints = [["parent", "name__value"]]

    rack_schema = hierarchical_location_schema_simple_unregistered.get(name="LocationRack")
    rack_schema.human_friendly_id = ["parent__name__value", "status__value"]
    rack_schema.uniqueness_constraints = [["parent", "status__value"]]

    registry.schema.register_schema(schema=hierarchical_location_schema_simple_unregistered, branch=default_branch.name)
    constraint = NodeGroupedUniquenessConstraint(
        db=db,
        branch=default_branch,
        message_builder=UniquenessViolationMessageBuilder(
            schema_branch=registry.schema.get_schema_branch(default_branch.name)
        ),
    )

    eu = await Node.init(db=db, schema="LocationRegion", branch=default_branch)
    await eu.new(db=db, name="Europe")
    await eu.save(db=db)
    fr = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await fr.new(db=db, name="France", parent=eu)
    await fr.save(db=db)
    uk = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await uk.new(db=db, name="United Kingdom", parent=eu)
    await uk.save(db=db)

    th2 = await Node.init(db=db, schema="LocationRack", branch=default_branch)
    await th2.new(db=db, name="th2-par", parent=fr)
    await th2.save(db=db)

    ld6 = await Node.init(db=db, schema="LocationRack", branch=default_branch)
    await ld6.new(db=db, name="ld6-ldn", parent=uk)
    await ld6.save(db=db)
    await constraint.check(ld6)

    ld62 = await Node.init(db=db, schema="LocationRack", branch=default_branch)
    await ld62.new(db=db, name="ld6-ldn2", parent=uk)
    with pytest.raises(UniquenessViolationError, match=r"Violates uniqueness constraint 'parent-status'"):
        await constraint.check(ld62)


async def test_attribute_uniqueness_matches_canonical_ip_on_update(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """A bare address submitted on update collides with a node that stores the same host with its prefix length."""
    node_schema = NodeSchema(
        name="UniqueHost",
        namespace="Test",
        attributes=[
            AttributeSchema(name="name", kind="Text", optional=True),
            AttributeSchema(name="address", kind="IPHost", unique=True),
        ],
    )
    registry.schema.set(name=node_schema.kind, schema=node_schema, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)

    first_address = "192.0.2.20/32"
    first_address_short_format = "192.0.2.20"
    second_address = "192.0.2.21/32"

    first = await Node.init(db=db, schema=node_schema.kind, branch=default_branch)

    await first.new(db=db, name="first", address=first_address)
    await first.save(db=db)
    second = await Node.init(db=db, schema=node_schema.kind, branch=default_branch)
    await second.new(db=db, name="second", address=second_address)
    await second.save(db=db)

    reloaded = await NodeManager.get_one(id=second.id, db=db, branch=default_branch)
    await reloaded.from_graphql(db=db, data={"address": {"value": first_address_short_format}})

    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    with pytest.raises(
        UniquenessViolationError,
        match=rf"An object already exist with this value: address: {re.escape(first_address)}",
    ):
        await constraint.check(reloaded)
