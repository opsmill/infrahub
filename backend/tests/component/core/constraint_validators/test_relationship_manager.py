import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.relationship.constraints.count import RelationshipCountConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_node_validate_constraint_relationship_count_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160, cars=[car_accord_main.id])

    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=person.cars, node_schema=person.get_schema(), node=person)

    assert "has 2 peers for testcar__testperson, maximum of 1 allowed" in exc.value.message


async def test_node_validate_constraint_relationship_count_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)

    await constraint.check(relm=person_john_main.cars, node_schema=person_john_main.get_schema(), node=person_john_main)


async def test_node_validate_constraint_relationship_count_failure_generic_peer(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """When the declared peer is a generic but cardinality=one is declared on a concrete subtype,
    the count constraint must still raise ValidationError on the over-quota peer."""
    schema = SchemaRoot(
        generics=[
            {
                "name": "Thing",
                "namespace": "Test",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ],
        nodes=[
            {
                "name": "ExclusiveThing",
                "namespace": "Test",
                "inherit_from": ["TestThing"],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "identifier": "person__thing",
                        "cardinality": "one",
                        "optional": True,
                        "direction": "inbound",
                    },
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "things",
                        "peer": "TestThing",
                        "identifier": "person__thing",
                        "cardinality": "many",
                        "optional": True,
                        "direction": "outbound",
                    },
                ],
            },
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    widget = await Node.init(db=db, schema="TestExclusiveThing", branch=default_branch)
    await widget.new(db=db, name="widget")
    await widget.save(db=db)

    alice = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await alice.new(db=db, name="alice", things=[widget.id])
    await alice.save(db=db)

    bob = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await bob.new(db=db, name="bob", things=[widget.id])

    constraint = RelationshipCountConstraint(db=db, branch=default_branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=bob.things, node_schema=bob.get_schema(), node=bob)

    assert "has 2 peers for person__thing, maximum of 1 allowed" in exc.value.message
