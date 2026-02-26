import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_node_validate_constraint_node_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeGroupedUniquenessConstraint(db=db, branch=default_branch)
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(ValidationError) as exc:
        await constraint.check(new_john)

    assert "Violates uniqueness constraint 'name'" in exc.value.message


async def test_node_validate_constraint_node_uniqueness_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeGroupedUniquenessConstraint(db=db, branch=default_branch)
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
    constraint = NodeGroupedUniquenessConstraint(db=db, branch=default_branch)

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
    with pytest.raises(ValidationError, match=r"Violates uniqueness constraint 'parent-status'"):
        await constraint.check(ld62)
