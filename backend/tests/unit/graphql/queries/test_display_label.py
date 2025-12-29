from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_display_label_one_item(db: InfrahubDatabase, default_branch: Branch, data_schema: None) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
        ],
    }
    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)
    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low")
    await obj1.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == "Low"


async def test_display_label_multiple_items(db: InfrahubDatabase, default_branch: Branch, data_schema: None) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["name__value", "level__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)

    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=schema)
    await obj2.new(db=db, name="medium", level=3)
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert sorted([node["node"]["display_label"] for node in result.data["TestCriticality"]["edges"]]) == [
        "low 4",
        "medium 3",
    ]


async def test_display_label_default_value(db: InfrahubDatabase, default_branch: Branch, data_schema: None) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)

    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low")
    await obj1.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == f"TestCriticality(ID: {obj1.id})"


async def test_display_label_generic(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")
    cat_schema = animal_person_schema.get(name="TestCat")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    cat1 = await Node.init(db=db, schema=cat_schema, branch=default_branch)
    await cat1.new(db=db, name="Kitty", breed="Persian", owner=person1)
    await cat1.save(db=db)

    query = """
    query {
        TestAnimal {
            edges {
                node {
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestAnimal"]["edges"]) == 2
    expected_results = ["Kitty Persian #444444", "Rocky Labrador"]
    assert sorted([item["node"]["display_label"] for item in result.data["TestAnimal"]["edges"]]) == expected_results


async def test_display_label_nested_query(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                id
                                display_label
                                owner {
                                    node {
                                        id
                                        display_label
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    expected_result = {
        "cars": {
            "edges": [
                {
                    "node": {
                        "display_label": "volt #444444",
                        "id": str(c1.id),
                        "owner": {
                            "node": {
                                "display_label": "John",
                                "id": str(p1.id),
                            }
                        },
                    }
                },
                {
                    "node": {
                        "display_label": "bolt #444444",
                        "id": str(c2.id),
                        "owner": {
                            "node": {
                                "display_label": "John",
                                "id": str(p1.id),
                            }
                        },
                    }
                },
            ],
        },
        "name": {"value": "John"},
    }

    assert DeepDiff(result.data["TestPerson"]["edges"][0]["node"], expected_result, ignore_order=True).to_dict() == {}


async def test_display_label_computed_attr(db: InfrahubDatabase, default_branch: Branch, data_schema: None) -> None:
    object_a_schema = NodeSchema(
        name="ObjectA",
        namespace="Test",
        display_labels=["computed_name__value"],
        branch=BranchSupportType.AWARE.value,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(
                name="computed_name",
                kind="Text",
                optional=False,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value | upper }}"
                ),
            ),
        ],
    )
    object_b_schema = NodeSchema(
        name="ObjectB",
        namespace="Test",
        display_labels=["computed_name__value"],
        branch=BranchSupportType.AWARE.value,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(
                name="computed_name",
                kind="Text",
                optional=False,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2,
                    jinja2_template="{{ related_object__name__value }} {{ name__value | upper }}",
                ),
            ),
        ],
        relationships=[
            RelationshipSchema(
                name="related_object",
                kind="Attribute",
                peer="TestObjectA",
                optional=False,
                cardinality=RelationshipCardinality.ONE,
            )
        ],
    )
    registry.schema.set(name=object_a_schema.kind, schema=object_a_schema)
    registry.schema.set(name=object_b_schema.kind, schema=object_b_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    object_a_schema = registry.schema.get(object_a_schema.kind, branch=default_branch)
    object_b_schema = registry.schema.get(object_b_schema.kind, branch=default_branch)

    obj1 = await Node.init(db=db, schema=object_a_schema)
    await obj1.new(db=db, name="first")
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema=object_b_schema)
    await obj2.new(db=db, name="second", related_object=obj1)
    await obj2.save(db=db)

    # Validate first object, ObjectA with a computed_attribute referencing a related node
    query = """
    query {
        TestObjectA {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestObjectA"]["edges"]) == 1
    assert result.data["TestObjectA"]["edges"][0]["node"]["display_label"] == "FIRST"

    # Validate second object, Object B with a computed_attribute referencing a related node
    query = """
    query {
        TestObjectB {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestObjectB"]["edges"]) == 1
    assert result.data["TestObjectB"]["edges"][0]["node"]["display_label"] == "first SECOND"
