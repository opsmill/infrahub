import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_node_validate_constraint_node_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(ValidationError) as exc:
        await constraint.check(new_john)

    assert "An object already exist with this value" in exc.value.message


async def test_node_validate_constraint_node_uniqueness_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    alfred = await Node.init(db=db, schema="TestPerson", branch=default_branch)

    await alfred.new(db=db, name="Alfred", height=160)

    await constraint.check(alfred)


async def test_hierarchical_uniqueness_constraint(db, default_branch):
    schema = {
        "generics": [
            {
                "attributes": [{"kind": "Text", "name": "name"}],
                "description": "Generic hierarchical location",
                "hierarchical": True,
                "human_friendly_id": ["name__value"],
                "label": "Location",
                "name": "Generic",
                "namespace": "Location",
            }
        ],
        "nodes": [
            {
                "children": "LocationCountry",
                "description": "A continent on planet earth",
                "display_labels": ["name__value"],
                "generate_profile": False,
                "human_friendly_id": ["name__value"],
                "inherit_from": ["LocationGeneric"],
                "name": "Continent",
                "namespace": "Location",
                "order_by": ["name__value"],
                "parent": "",
                "uniqueness_constraints": [["name__value"]],
            },
            {
                "children": "LocationSite",
                "description": "A country within a continent",
                "display_labels": ["name__value"],
                "generate_profile": False,
                "human_friendly_id": ["parent__name__value", "name__value"],
                "inherit_from": ["LocationGeneric"],
                "name": "Country",
                "namespace": "Location",
                "order_by": ["name__value"],
                "parent": "LocationContinent",
                "uniqueness_constraints": [["parent", "name__value"]],
            },
            {
                "attributes": [{"kind": "Text", "name": "city", "optional": True}],
                "children": "",
                "description": "A site within a country",
                "display_labels": ["name__value"],
                "human_friendly_id": ["parent__name__value", "name__value"],
                "inherit_from": ["LocationGeneric"],
                "name": "Site",
                "namespace": "Location",
                "order_by": ["name__value"],
                "parent": "LocationCountry",
                "uniqueness_constraints": [["parent", "name__value"]],
            },
        ],
    }

    registry.schema.register_schema(schema=SchemaRoot(**schema), branch=default_branch.name)
    constraint = NodeGroupedUniquenessConstraint(db=db, branch=default_branch)

    eu = await Node.init(db=db, schema="LocationContinent", branch=default_branch)
    await eu.new(db=db, name="Europe")
    await eu.save(db=db)
    fr = await Node.init(db=db, schema="LocationCountry", branch=default_branch)
    await fr.new(db=db, name="France", parent=eu)
    await fr.save(db=db)
    uk = await Node.init(db=db, schema="LocationCountry", branch=default_branch)
    await uk.new(db=db, name="United Kingdom", parent=eu)
    await fr.save(db=db)

    th2 = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await th2.new(db=db, name="Telehouse 2", city="Paris", parent=fr)
    await th2.save(db=db)

    ld6 = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await ld6.new(db=db, name="Equinix LD6", city="London", parent=uk)
    await ld6.save(db=db)
    await constraint.check(ld6)

    ld6 = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await ld6.new(db=db, name="Equinix LD6", city="London", parent=uk)
    with pytest.raises(ValidationError, match=r"Violates uniqueness constraint 'parent-name' at parent"):
        await constraint.check(ld6)
