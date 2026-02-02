from infrahub.computed_attribute.gather import (
    gather_trigger_computed_attribute_jinja2,
    gather_trigger_computed_attribute_python,
)
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_gather_trigger_computed_attribute_jinja2_empty(register_core_models_schema) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 0


async def test_gather_trigger_computed_attribute_jinja2_only_main(car_person_schema_computed_attr) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc::kind::TestCar"
    assert trigger.generate_name() == "computed_attr_jinja2::main::TestCar_computed_desc::kind::TestCar"
    assert "infrahub.branch.name" not in trigger.trigger.match


async def test_gather_trigger_computed_attribute_jinja2_different_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)

    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get_node("TestCar")

    attr1 = car_schema.get_attribute(name="computed_desc")
    attr1.computed_attribute.jinja2_template = (
        "{{ name__value | upper }} {{ owner__name__value | upper }} has {{ nbr_seats__value | upper }} seats"
    )
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    name_main = "computed_attr_jinja2::main::TestCar_computed_desc::kind::TestCar"
    name_branch_first = "computed_attr_jinja2::branch2::TestCar_computed_desc::kind::TestCar"
    name_branch_second = "computed_attr_jinja2::branch2::TestCar_computed_desc::kind::TestPerson"

    triggers = await gather_trigger_computed_attribute_jinja2()
    triggers_by_name = {trigger.generate_name(): trigger for trigger in triggers}
    assert set(triggers_by_name.keys()) == {name_main, name_branch_first, name_branch_second}

    trigger_main = triggers_by_name[name_main]
    assert "infrahub.branch.name" in trigger_main.trigger.match
    assert trigger_main.trigger.match["infrahub.branch.name"] == ["!branch2"]

    trigger_branch = triggers_by_name[name_branch_first]
    assert "infrahub.branch.name" in trigger_branch.trigger.match
    assert trigger_branch.trigger.match["infrahub.branch.name"] == "branch2"

    trigger_branch = triggers_by_name[name_branch_second]
    assert "infrahub.branch.name" in trigger_branch.trigger.match
    assert trigger_branch.trigger.match["infrahub.branch.name"] == "branch2"


async def test_gather_trigger_computed_attribute_python(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr, transform01: Node
) -> None:
    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)
    assert triggers
    assert trigger_queries

    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc_python"


async def test_gather_trigger_computed_attribute_python_only_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    transform01: Node,
) -> None:
    """Test that gather_trigger_computed_attribute_python handles the case where
    a computed attribute only exists on a branch (not on main).
    """
    # Create a branch
    branch = await create_branch(branch_name="branch_with_computed_attr", db=db)

    # Add computed attribute to the schema ONLY on the branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get_node("TestCar")
    car_schema.attributes.append(
        AttributeSchema(
            name="computed_desc",
            kind="Text",
            read_only=True,
            optional=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                transform="transform01",
            ),
        )
    )
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    # This should not raise a KeyError
    triggers, _ = await gather_trigger_computed_attribute_python(db=db)

    # Verify we got triggers for the branch only
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc"
    assert trigger.branch == "branch_with_computed_attr"
