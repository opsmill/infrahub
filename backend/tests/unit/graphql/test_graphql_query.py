import pytest
from deepdiff import DeepDiff
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_simple_query(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        TestCriticality {
            count
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, include_mutation=False, include_subscription=False, branch=default_branch
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 2


async def test_simple_query_with_offset_and_limit(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        TestCriticality(offset: 0, limit:1) {
            count
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, include_mutation=False, include_subscription=False, branch=default_branch
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 1


async def test_display_label_one_item(db, session, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["label__value"],
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=schema.kind, schema=schema)

    obj1 = await Node.init(session=session, schema=schema)
    await obj1.new(session=session, name="low")
    await obj1.save(session=session)

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
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == "Low"


async def test_display_label_multiple_items(db, session, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["name__value", "level__value"],
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=schema.kind, schema=schema)

    obj1 = await Node.init(session=session, schema=schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=schema)
    await obj2.new(session=session, name="medium", level=3)
    await obj2.save(session=session)

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
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert sorted([node["node"]["display_label"] for node in result.data["TestCriticality"]["edges"]]) == [
        "low 4",
        "medium 3",
    ]


async def test_display_label_default_value(db, session, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=schema.kind, schema=schema)

    obj1 = await Node.init(session=session, schema=schema)
    await obj1.new(session=session, name="low")
    await obj1.save(session=session)

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
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == f"TestCriticality(ID: {obj1.id})"


async def test_all_attributes(db, session, default_branch: Branch, data_schema, all_attribute_types_schema):
    obj1 = await Node.init(session=session, schema="TestAllAttributeTypes")
    await obj1.new(
        session=session,
        name="obj1",
        mystring="abc",
        mybool=False,
        myint=123,
        mylist=["1", 2, False],
        myjson={"key1": "bill"},
    )
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema="TestAllAttributeTypes")
    await obj2.new(session=session, name="obj2")
    await obj2.save(session=session)

    query = """
    query {
        TestAllAttributeTypes {
            edges {
                node {
                    name { value }
                    mystring { value }
                    mybool { value }
                    myint { value }
                    mylist { value }
                    myjson { value }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestAllAttributeTypes"]["edges"]) == 2

    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestAllAttributeTypes"]["edges"]}

    assert results["obj1"]["mystring"]["value"] == obj1.mystring.value
    assert results["obj1"]["mybool"]["value"] == obj1.mybool.value
    assert results["obj1"]["myint"]["value"] == obj1.myint.value
    assert results["obj1"]["mylist"]["value"] == obj1.mylist.value
    assert results["obj1"]["myjson"]["value"] == obj1.myjson.value

    assert results["obj2"]["mystring"]["value"] == obj2.mystring.value
    assert results["obj2"]["mybool"]["value"] == obj2.mybool.value
    assert results["obj2"]["myint"]["value"] == obj2.myint.value
    assert results["obj2"]["mylist"]["value"] == obj2.mylist.value
    assert results["obj2"]["myjson"]["value"] == obj2.myjson.value


async def test_nested_query(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1


async def test_double_nested_query(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                                owner {
                                    node {
                                        name {
                                            value
                                        }
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
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1
    assert result_per_name["John"]["cars"]["count"] == 2
    assert result_per_name["Jane"]["cars"]["count"] == 1
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["node"]["name"]["value"] == "John"


async def test_display_label_nested_query(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

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
    result = await graphql(
        await generate_graphql_schema(
            session=session, branch=default_branch, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
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


async def test_query_typename(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        TestPerson {
        __typename
            edges {
            __typename
                node {
                    __typename
                    name {
                        value
                        __typename
                    }
                    cars {
                    __typename
                        edges {
                        __typename
                            properties {
                                __typename
                            }
                            node {
                                __typename
                                name {
                                    __typename
                                    value
                                }
                                owner {
                                    __typename
                                    node {
                                        __typename
                                        name {
                                            value
                                            __typename
                                        }
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
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert result.data["TestPerson"]["__typename"] == "PaginatedTestPerson"
    assert result.data["TestPerson"]["edges"][0]["__typename"] == "EdgedTestPerson"
    assert result.data["TestPerson"]["edges"][0]["node"]["__typename"] == "TestPerson"
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["__typename"] == "TextAttribute"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["__typename"] == "TestCar"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["__typename"] == "NestedEdgedTestPerson"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["node"]["name"]["__typename"] == "TextAttribute"
    assert result_per_name["John"]["cars"]["edges"][0]["properties"]["__typename"] == "RelationshipProperty"


async def test_query_filter_ids(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)
    obj3 = await Node.init(session=session, schema=criticality_schema)
    await obj3.new(session=session, name="high", level=1, description="My desc", color="#222222")
    await obj3.save(session=session)

    query = (
        """
    query {
        TestCriticality(ids: ["%s"]) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
        % obj1.id
    )

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 1

    query = """
    query {
        TestCriticality(ids: ["%s", "%s"]) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        obj1.id,
        obj2.id,
    )

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 2


async def test_query_filter_local_attrs(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        TestCriticality(name__value: "low") {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCriticality"]["edges"]) == 1


async def test_query_multiple_filters(db, session, default_branch: Branch, car_person_manufacturer_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")
    manufacturer = registry.get_schema(name="TestManufacturer")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    m1 = await Node.init(session=session, schema=manufacturer)
    await m1.new(session=session, name="chevrolet")
    await m1.save(session=session)
    m2 = await Node.init(session=session, schema=manufacturer)
    await m2.new(session=session, name="ford", description="from Michigan")
    await m2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=False, owner=p1, manufacturer=m1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=3, is_electric=True, owner=p1, manufacturer=m2)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2, manufacturer=m1)
    await c3.save(session=session)

    query01 = """
    query {
        TestCar(owner__name__value: "John", nbr_seats__value: 4) {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query01,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c1.id

    query02 = """
    query {
        TestCar(is_electric__value: true, nbr_seats__value: 4) {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query02,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c3.id

    query03 = """
    query {
        TestCar(owner__name__value: "John", manufacturer__name__value: "ford", ) {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query03,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id

    query04 = """
    query {
        TestCar(owner__id: "%s", manufacturer__id: "%s", ) {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        m2.id,
    )

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query04,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id


async def test_query_filter_relationships(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        TestPerson(name__value: "John") {
            count
            edges {
                node {
                    name {
                        value
                    }
                    cars(name__value: "volt") {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationships_with_generic(db, session, default_branch: Branch, car_person_generics_data):
    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(name__value: "volt") {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }

        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, branch=default_branch, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationship_id(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = (
        """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(id: "%s") {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
        % c1.id
    )

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_oneway_relationship(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="BuiltinTag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="BuiltinTag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    tags {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2


async def test_query_at_specific_time(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="BuiltinTag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="BuiltinTag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    time1 = Timestamp()

    t2.name.value = "Green"
    await t2.save(session=session)

    query = """
    query {
        BuiltinTag {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["BuiltinTag"]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data["BuiltinTag"]["edges"]])
    assert names == ["Blue", "Green"]

    # Now query at a specific time
    query = """
    query {
        BuiltinTag {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={
            "infrahub_session": session,
            "infrahub_database": db,
            "infrahub_at": time1,
            "infrahub_branch": default_branch,
        },
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["BuiltinTag"]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data["BuiltinTag"]["edges"]])
    assert names == ["Blue", "Red"]


async def test_query_attribute_updated_at(db, session, default_branch: Branch, person_tag_schema):
    p11 = await Node.init(session=session, schema="TestPerson")
    await p11.new(session=session, firstname="John", lastname="Doe")
    await p11.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        updated_at
                    }
                    lastname {
                        value
                        updated_at
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        == result1.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )

    p12 = await NodeManager.get_one(session=session, id=p11.id)
    p12.firstname.value = "Jim"
    await p12.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )


async def test_query_node_updated_at(db, session, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    _updated_at
                    id
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["_updated_at"]

    p2 = await Node.init(session=session, schema="TestPerson")
    await p2.new(session=session, firstname="Jane", lastname="Doe")
    await p2.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["TestPerson"]["edges"][0]["node"]["_updated_at"]
    assert result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
    assert (
        result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
        == Timestamp(result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]).to_string()
    )
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["_updated_at"]
        != result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
    )


async def test_query_relationship_updated_at(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="BuiltinTag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="BuiltinTag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    tags {
                        edges {
                            node {
                                _updated_at
                                name {
                                    value
                                }
                            }
                            properties {
                                updated_at
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"] == []

    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert len(result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["properties"]["updated_at"]
    )
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        == Timestamp(
            result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        ).to_string()
    )


async def test_query_attribute_node_property_source(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        source {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]["name"]["value"]
        == first_account.name.value
    )


async def test_query_attribute_node_property_owner(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe", _owner=first_account)
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        owner {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["owner"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["owner"]["name"]["value"]
        == first_account.name.value
    )


async def test_query_relationship_node_property(db, session, default_branch: Branch, car_person_schema, first_account):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(
        session=session,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1, "_relation__owner": first_account.id},
    )
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(
        session=session,
        name="bolt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p2, "_relation__source": first_account.id},
    )
    await c2.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                            properties {
                                owner {
                                    id
                                }
                                source {
                                    id
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestPerson"]["edges"]}
    assert sorted(list(results.keys())) == ["Jane", "John"]
    assert len(results["John"]["cars"]["edges"]) == 1
    assert len(results["Jane"]["cars"]["edges"]) == 1

    assert results["John"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert results["John"]["cars"]["edges"][0]["properties"]["owner"]
    assert results["John"]["cars"]["edges"][0]["properties"]["owner"]["id"] == first_account.id
    assert results["John"]["cars"]["edges"][0]["properties"]["source"] is None

    assert results["Jane"]["cars"]["edges"][0]["node"]["name"]["value"] == "bolt"
    assert results["Jane"]["cars"]["edges"][0]["properties"]["owner"] is None
    assert results["Jane"]["cars"]["edges"][0]["properties"]["source"]
    assert results["Jane"]["cars"]["edges"][0]["properties"]["source"]["id"] == first_account.id


async def test_query_attribute_flag_property(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(
        session=session,
        firstname={"value": "John", "is_protected": True},
        lastname={"value": "Doe", "is_visible": False},
        _source=first_account,
    )
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        is_protected
                    }
                    lastname {
                        value
                        is_visible
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["is_protected"] is True
    assert result1.data["TestPerson"]["edges"][0]["node"]["lastname"]["is_visible"] is False


async def test_query_branches(db, session, default_branch: Branch, register_core_models_schema):
    query = """
    query {
        branch {
            id
            name
            branched_from
            is_data_only
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["branch"][0]["name"] == "main"


async def test_query_multiple_branches(db, session, default_branch: Branch, register_core_models_schema):
    query = """
    query {
        branch1: branch {
            id
            name
            branched_from
            is_data_only
        }
        branch2: branch {
            id
            name
            branched_from
            is_data_only
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["branch1"][0]["name"] == "main"
    assert result1.data["branch2"][0]["name"] == "main"


async def test_multiple_queries(db, session, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    p2 = await Node.init(session=session, schema="TestPerson")
    await p2.new(session=session, firstname="Jane", lastname="Doe")
    await p2.save(session=session)

    query = """
    query {
        firstperson: TestPerson(firstname__value: "John") {
            edges {
                node {
                    id
                    firstname {
                        value
                    }
                }
            }
        }
        secondperson: TestPerson(firstname__value: "Jane") {
            edges {
                node {
                    id
                    firstname {
                        value
                    }
                }
            }

        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["firstperson"]["edges"][0]["node"]["firstname"]["value"] == "John"
    assert result1.data["secondperson"]["edges"][0]["node"]["firstname"]["value"] == "Jane"


async def test_model_node_interface(db, session, default_branch: Branch, car_schema):
    d1 = await Node.init(session=session, schema="TestCar")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    d2 = await Node.init(session=session, schema="TestCar")
    await d2.new(session=session, name="Renaud Clio", nbr_doors=4)
    await d2.save(session=session)

    query = """
    query {
        TestCar {
            edges {
                node {
                    name {
                        value
                    }
                    description {
                        value
                    }
                    nbr_doors {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert sorted([car["node"]["name"]["value"] for car in result.data["TestCar"]["edges"]]) == [
        "Porsche 911",
        "Renaud Clio",
    ]
    assert sorted([car["node"]["nbr_doors"]["value"] for car in result.data["TestCar"]["edges"]]) == [2, 4]


async def test_model_rel_interface(db, session, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(session=session, schema="TestCar")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    b1 = await Node.init(session=session, schema="TestBoat")
    await b1.new(session=session, name="Laser", has_sails=True)
    await b1.save(session=session)

    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John Doe", vehicules=[d1, b1])
    await p1.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    vehicules {
                        edges {
                            node {
                                name {
                                    value
                                }
                                ... on TestCar {
                                    nbr_doors {
                                        value
                                    }
                                }
                                ... on TestBoat {
                                    has_sails {
                                        value
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

    result = await graphql(
        schema=await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestPerson"]["edges"][0]["node"]["vehicules"]["edges"]) == 2
    expected_results = {
        "name": {"value": "John Doe"},
        "vehicules": {
            "edges": [
                {"node": {"name": {"value": "Porsche 911"}, "nbr_doors": {"value": 2}}},
                {"node": {"has_sails": {"value": True}, "name": {"value": "Laser"}}},
            ]
        },
    }
    assert DeepDiff(result.data["TestPerson"]["edges"][0]["node"], expected_results, ignore_order=True).to_dict() == {}


async def test_model_rel_interface_reverse(db, session, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(session=session, schema="TestCar")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    b1 = await Node.init(session=session, schema="TestBoat")
    await b1.new(session=session, name="Laser", has_sails=True)
    await b1.save(session=session)

    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John Doe", vehicules=[d1, b1])
    await p1.save(session=session)

    query = """
    query {
        TestBoat {
            edges {
                node {
                    name {
                        value
                    }
                    owners {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }

                    }
                }
            }
        }
    }
    """

    result = await graphql(
        await generate_graphql_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestBoat"]["edges"][0]["node"]["owners"]["edges"]) == 1


@pytest.mark.skip(reason="pending convertion - review use of fragments")
async def test_union_relationship(
    db, session, default_branch: Branch, generic_vehicule_schema, car_schema, truck_schema, motorcycle_schema
):
    SCHEMA = {
        "name": "person",
        "kind": "Person",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "road_vehicules", "peer": "OnRoad", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    d1 = await Node.init(session=session, schema="Car")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    t1 = await Node.init(session=session, schema="Truck")
    await t1.new(session=session, name="Silverado", nbr_axles=4)
    await t1.save(session=session)

    m1 = await Node.init(session=session, schema="Motorcycle")
    await m1.new(session=session, name="Monster", nbr_seats=1)
    await m1.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John Doe", road_vehicules=[d1, t1, m1])
    await p1.save(session=session)

    query = """
    query {
        person {
            name {
                value
            }
            road_vehicules {
                ... on RelatedTruck {
                    nbr_axles {
                        value
                    }
                }
                ... on RelatedMotorcycle {
                    nbr_seats {
                        value
                    }
                }
                ... on RelatedCar {
                    nbr_doors {
                        value
                    }
                }
            }
        }
    }
    """

    schema = await generate_graphql_schema(
        branch=default_branch, session=session, include_mutation=False, include_subscription=False
    )

    result = await graphql(
        schema=schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["road_vehicules"]) == 3

    expected_result = {
        "name": {"value": "John Doe"},
        "road_vehicules": [
            {"nbr_doors": {"value": 2}},
            {"nbr_axles": {"value": 4}},
            {"nbr_seats": {"value": 1}},
        ],
    }
    assert DeepDiff(result.data["person"][0], expected_result, ignore_order=True).to_dict() == {}


async def test_generic_root_with_pagination(db, session, default_branch: Branch, car_person_generics_data):
    query = """
    query {
        TestCar(limit: 2) {
            count
            edges {
                node {
                    name {
                        value
                    }
                }
            }

        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, branch=default_branch, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    expected_response = {
        "TestCar": {
            "count": 3,
            "edges": [
                {"node": {"name": {"value": "bolt"}}},
                {"node": {"name": {"value": "nolt"}}},
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


async def test_generic_root_with_filters(db, session, default_branch: Branch, car_person_generics_data):
    query = """
    query {
        TestCar(owner__name__value: "John" ) {
            count
            edges {
                node {
                    name {
                        value
                    }
                }
            }

        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, branch=default_branch, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    expected_response = {
        "TestCar": {
            "count": 2,
            "edges": [
                {"node": {"name": {"value": "bolt"}}},
                {"node": {"name": {"value": "volt"}}},
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


async def test_member_of_groups(db, session, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(session=session, schema="CoreStandardGroup")
    await g1.new(session=session, name="group1", members=[c1, c2])
    await g1.save(session=session)
    g2 = await Node.init(session=session, schema="CoreStandardGroup")
    await g2.new(session=session, name="group2", members=[c2, c3])
    await g2.save(session=session)

    query = """
    query {
        TestCar {
            count
            edges {
                node {
                    name {
                        value
                    }
                    member_of_groups {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(
            session=session, branch=default_branch, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    expected_response = {
        "TestCar": {
            "count": 3,
            "edges": [
                {
                    "node": {
                        "member_of_groups": {
                            "count": 2,
                            "edges": [
                                {"node": {"name": {"value": "group1"}}},
                                {"node": {"name": {"value": "group2"}}},
                            ],
                        },
                        "name": {"value": "bolt"},
                    },
                },
                {
                    "node": {
                        "member_of_groups": {
                            "count": 1,
                            "edges": [{"node": {"name": {"value": "group2"}}}],
                        },
                        "name": {"value": "nolt"},
                    },
                },
                {
                    "node": {
                        "member_of_groups": {
                            "count": 1,
                            "edges": [{"node": {"name": {"value": "group1"}}}],
                        },
                        "name": {"value": "volt"},
                    },
                },
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


@pytest.mark.skip(reason="Union is not supported at the root of the GraphQL Schema yet .. ")
async def test_union_root(
    db, session, default_branch: Branch, generic_vehicule_schema, car_schema, truck_schema, motorcycle_schema
):
    SCHEMA = {
        "name": "person",
        "kind": "Person",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "road_vehicules", "peer": "OnRoad", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    d1 = await Node.init(session=session, schema="Car")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    t1 = await Node.init(session=session, schema="Truck")
    await t1.new(session=session, name="Silverado", nbr_axles=4)
    await t1.save(session=session)

    m1 = await Node.init(session=session, schema="Motorcycle")
    await m1.new(session=session, name="Monster", nbr_seats=1)
    await m1.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John Doe", road_vehicules=[d1, t1, m1])
    await p1.save(session=session)

    query = """
    query {
        on_road {
            ... on RelatedTruck {
                name {
                    value
                }
                nbr_axles {
                    value
                }
            }
            ... on RelatedMotorcycle {
                name {
                    value
                }
                nbr_seats {
                    value
                }
            }
            ... on RelatedCar {
                name {
                    value
                }
                nbr_doors {
                    value
                }
            }
        }
    }
    """

    schema = await generate_graphql_schema(
        branch=default_branch, session=session, include_mutation=False, include_subscription=False
    )

    result = await graphql(
        schema=schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["on_road"]) == 3


async def test_query_diff_graphs(db, session, default_branch, base_dataset_02):
    query = """
    query {
        diff(branch: "branch1") {
            nodes {
                id
                branch
                kind
                action
                changed_at
                attributes {
                    name
                    action
                }
            }
            relationships {
                id
                branch
                name
                properties {
                    branch
                    type
                    changed_at
                    action
                }
                changed_at
                action
            }
        }
    }
    """
    main_branch = await Branch.get_by_name(name="main", session=session)

    schema = await generate_graphql_schema(
        branch=default_branch, session=session, include_mutation=False, include_subscription=False
    )

    result = await graphql(
        schema=schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": main_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    expected_nodes = [
        {
            "action": "updated",
            "branch": "main",
            "attributes": [{"action": "updated", "name": "name"}],
            "changed_at": None,
            "id": "c1",
            "kind": "TestCar",
        },
        {
            "action": "updated",
            "branch": "branch1",
            "attributes": [{"action": "updated", "name": "nbr_seats"}],
            "changed_at": None,
            "id": "c1",
            "kind": "TestCar",
        },
        {
            "action": "added",
            "branch": "main",
            "attributes": [
                {"action": "added", "name": "name"},
                {"action": "added", "name": "nbr_seats"},
                {"action": "added", "name": "is_electric"},
                {"action": "added", "name": "color"},
            ],
            "changed_at": base_dataset_02["time_m20"],
            "id": "c2",
            "kind": "TestCar",
        },
        {
            "action": "added",
            "branch": "branch1",
            "attributes": [
                {"action": "added", "name": "name"},
                {"action": "added", "name": "nbr_seats"},
                {"action": "added", "name": "is_electric"},
                {"action": "added", "name": "color"},
            ],
            "changed_at": base_dataset_02["time_m40"],
            "id": "c3",
            "kind": "TestCar",
        },
    ]

    expected_rels = [
        {
            "action": "updated",
            "branch": "main",
            "changed_at": None,
            "id": "r1",
            "name": "testcar__testperson",
            "properties": [
                {
                    "action": "updated",
                    "branch": "main",
                    "changed_at": base_dataset_02["time_m30"],
                    "type": "IS_PROTECTED",
                },
            ],
        },
        {
            "action": "updated",
            "branch": "branch1",
            "changed_at": None,
            "id": "r1",
            "name": "testcar__testperson",
            "properties": [
                {
                    "action": "updated",
                    "branch": "branch1",
                    "changed_at": base_dataset_02["time_m20"],
                    "type": "IS_VISIBLE",
                },
            ],
        },
        {
            "action": "added",
            "branch": "branch1",
            "changed_at": base_dataset_02["time_m20"],
            "id": "r2",
            "name": "testcar__testperson",
            "properties": [
                {
                    "action": "added",
                    "branch": "branch1",
                    "changed_at": base_dataset_02["time_m20"],
                    "type": "IS_PROTECTED",
                },
                {
                    "action": "added",
                    "branch": "branch1",
                    "changed_at": base_dataset_02["time_m20"],
                    "type": "IS_VISIBLE",
                },
            ],
        },
    ]

    assert len(result.data["diff"]["nodes"]) == 4
    assert len(result.data["diff"]["relationships"]) == 3
    assert DeepDiff(result.data["diff"]["nodes"], expected_nodes, ignore_order=True).to_dict() == {}
    assert DeepDiff(result.data["diff"]["relationships"], expected_rels, ignore_order=True).to_dict() == {}
