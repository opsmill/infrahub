from copy import deepcopy
from typing import Any

from infrahub.computed_attribute.gather import (
    gather_trigger_computed_attribute_jinja2,
    gather_trigger_computed_attribute_python,
)
from infrahub.computed_attribute.models import ComputedAttrPythonQueryTriggerDefinition
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

TRANSFORM_NAME = "transform_person_cars"

# TestPerson.cars peers with the TestCar generic, whose members are TestElectricCar and TestGazCar.
# Only TestElectricCar is read through, so the other kinds behind the generic contribute no field.
QUERY_THROUGH_GENERIC = """
query PersonCars($id: ID!) {
    TestPerson(ids: [$id]) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            ... on TestElectricCar {
                                nbr_engine { value }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

QUERY_THROUGH_GENERIC_DISPLAY_LABEL = """
query PersonCars($id: ID!) {
    TestPerson(ids: [$id]) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            display_label
                        }
                    }
                }
            }
        }
    }
}
"""


async def _setup_person_transform(
    db: InfrahubDatabase,
    default_branch: Branch,
    schema_dict: dict[str, Any],
    query: str,
) -> None:
    """Give TestPerson a Python computed attribute fed by a transform that runs `query`."""
    gql_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await gql_query.new(db=db, name="person_cars", query=query)
    await gql_query.save(db=db)

    repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repository.new(
        db=db,
        name="repo_generics",
        ref=default_branch.name,
        commit="commit01",
        location="location01",
        queries=[gql_query],
    )
    await repository.save(db=db)

    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON, branch=default_branch)
    await transform.new(
        db=db,
        name=TRANSFORM_NAME,
        file_path="transform.py",
        class_name="Transform",
        query=gql_query,
        repository=repository,
    )
    await transform.save(db=db)

    schema_dict = deepcopy(schema_dict)
    person = next(node for node in schema_dict["nodes"] if node["name"] == "Person")
    person["attributes"].append(
        {
            "name": "computed_desc_python",
            "kind": "Text",
            "read_only": True,
            "optional": True,
            "computed_attribute": {
                "kind": ComputedAttributeKind.TRANSFORM_PYTHON.value,
                "transform": TRANSFORM_NAME,
            },
        }
    )
    registry.schema.register_schema(schema=SchemaRoot(**schema_dict), branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)


def _triggers_by_kind(
    triggers: list[ComputedAttrPythonQueryTriggerDefinition],
) -> dict[str, ComputedAttrPythonQueryTriggerDefinition]:
    return {trigger.trigger.match["infrahub.node.kind"]: trigger for trigger in triggers}


async def test_gather_trigger_computed_attribute_jinja2_empty(register_core_models_schema: SchemaBranch) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 0


async def test_gather_trigger_computed_attribute_jinja2_only_main(car_person_schema_computed_attr: None) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc::kind::TestCar"
    assert trigger.generate_name() == "computed_attr_jinja2::main::TestCar_computed_desc::kind::TestCar"
    assert "infrahub.branch.name" not in trigger.trigger.match


async def test_gather_trigger_computed_attribute_jinja2_different_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr: None
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
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr: None, transform01: Node
) -> None:
    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)
    assert triggers

    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc_python"

    triggers_by_kind = _triggers_by_kind(trigger_queries)
    assert set(triggers_by_kind) == {"TestCar"}
    assert triggers_by_kind["TestCar"].trigger.match_related["infrahub.field.name"] == ["name"]


async def test_gather_trigger_computed_attribute_python_only_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    transform01: Node,
) -> None:
    """Test that gather_trigger_computed_attribute_python handles the case where.

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


async def test_gather_trigger_computed_attribute_python_query_skips_unread_kinds(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics_unregistered: dict[str, Any],
) -> None:
    """A kind reached through a generic but never read from gets no trigger.

    Such a trigger would carry no field filter, so it would fire on every update to that kind
    and recompute a value those updates cannot change.
    """
    await _setup_person_transform(
        db=db,
        default_branch=default_branch,
        schema_dict=car_person_schema_generics_unregistered,
        query=QUERY_THROUGH_GENERIC,
    )

    _, trigger_queries = await gather_trigger_computed_attribute_python(db=db)
    triggers_by_kind = _triggers_by_kind(trigger_queries)

    assert set(triggers_by_kind) == {"TestPerson", "TestElectricCar"}
    assert sorted(triggers_by_kind["TestPerson"].trigger.match_related["infrahub.field.name"]) == ["cars", "name"]
    assert triggers_by_kind["TestElectricCar"].trigger.match_related["infrahub.field.name"] == ["nbr_engine"]


async def test_gather_trigger_computed_attribute_python_query_keeps_display_label_kinds(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics_unregistered: dict[str, Any],
) -> None:
    """A kind read only through display_label keeps its trigger, matching on any field.

    The analyzer cannot tell which field updates change a display label, so the trigger stays
    unfiltered on purpose. That is a non-empty read set and must not be confused with an unread kind.
    """
    await _setup_person_transform(
        db=db,
        default_branch=default_branch,
        schema_dict=car_person_schema_generics_unregistered,
        query=QUERY_THROUGH_GENERIC_DISPLAY_LABEL,
    )

    _, trigger_queries = await gather_trigger_computed_attribute_python(db=db)
    triggers_by_kind = _triggers_by_kind(trigger_queries)

    assert set(triggers_by_kind) == {"TestPerson", "TestCar", "TestElectricCar", "TestGazCar"}
    for kind in ("TestCar", "TestElectricCar", "TestGazCar"):
        assert "infrahub.field.name" not in triggers_by_kind[kind].trigger.match_related
