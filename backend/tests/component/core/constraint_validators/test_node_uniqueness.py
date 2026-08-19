import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.node.constraints.uniqueness_violation_message import UniquenessViolationMessageBuilder
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import UniquenessViolationError
from tests.helpers.schema import LOCATION_SCHEMA, load_schema


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

    with pytest.raises(UniquenessViolationError, match=r"^Violates uniqueness constraint 'name'$") as exc:
        await constraint.check(new_john)

    assert exc.value.node_kind == "TestPerson"
    assert exc.value.fields == ["name"]


async def test_node_validate_constraint_attribute_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(UniquenessViolationError, match=r"^An object already exist with this value: name: John$") as exc:
        await constraint.check(new_john)

    assert exc.value.node_kind == "TestPerson"
    assert exc.value.fields == ["name"]


async def test_attribute_uniqueness_reports_the_submitted_kind_not_the_constraint_scope(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
    register_core_models_schema: SchemaBranch,
) -> None:
    # TestingContinent inherits `name` (unique) from the TestingLocation generic, so uniqueness is
    # enforced against the generic. node_kind must still name the kind the caller submitted,
    # otherwise a consumer gets back a kind it never mentioned.
    await load_schema(db, schema=LOCATION_SCHEMA, update_db=True)
    europe = await Node.init(db=db, schema="TestingContinent", branch=default_branch)
    await europe.new(db=db, name="Europe", shortname="EU")
    await europe.save(db=db)

    duplicate = await Node.init(db=db, schema="TestingContinent", branch=default_branch)
    await duplicate.new(db=db, name="Europe", shortname="EUR")

    constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
    with pytest.raises(UniquenessViolationError) as exc:
        await constraint.check(duplicate)

    assert exc.value.node_kind == "TestingContinent"
    assert exc.value.fields == ["name"]


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
