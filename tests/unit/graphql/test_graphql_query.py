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


async def test_simple_query(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 2


async def test_all_attributes(db, session, default_branch: Branch, data_schema, all_attribute_types_schema):
    obj1 = await Node.init(session=session, schema="AllAttributeTypes")
    await obj1.new(session=session, name="obj1", mystring="abc", mybool=False, myint=123, mylist=["1", 2, False])
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema="AllAttributeTypes")
    await obj2.new(session=session, name="obj2")
    await obj2.save(session=session)

    query = """
    query {
        all_attribute_types {
            name { value }
            mystring { value }
            mybool { value }
            myint { value }
            mylist { value }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["all_attribute_types"]) == 2

    results = {item["name"]["value"]: item for item in result.data["all_attribute_types"]}

    assert results["obj1"]["mystring"]["value"] == obj1.mystring.value
    assert results["obj1"]["mybool"]["value"] == obj1.mybool.value
    assert results["obj1"]["myint"]["value"] == obj1.myint.value
    assert results["obj1"]["mylist"]["value"] == obj1.mylist.value

    assert results["obj2"]["mystring"]["value"] == obj2.mystring.value
    assert results["obj2"]["mybool"]["value"] == obj2.mybool.value
    assert results["obj2"]["myint"]["value"] == obj2.myint.value
    assert results["obj2"]["mylist"]["value"] == obj2.mylist.value


async def test_nested_query(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="Car")
    person = registry.get_schema(name="Person")

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
        person {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["name"]["value"]: result for result in result.data["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


async def test_double_nested_query(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="Car")
    person = registry.get_schema(name="Person")

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
        person {
            name {
                value
            }
            cars {
                name {
                    value
                }
                owner {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["name"]["value"]: result for result in result.data["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1
    assert result_per_name["John"]["cars"][0]["owner"]["name"]["value"] == "John"


async def test_query_typename(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="Car")
    person = registry.get_schema(name="Person")

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
        person {
            __typename
            name {
                value
                __typename
            }
            cars {
                __typename
                name {
                    __typename
                    value
                }
                owner {
                    __typename
                    name {
                        value
                        __typename
                    }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["name"]["value"]: result for result in result.data["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert result.data["person"][0]["__typename"] == "Person"
    assert result.data["person"][0]["name"]["__typename"] == "StrAttribute"
    assert result_per_name["John"]["cars"][0]["__typename"] == "RelatedCar"


async def test_query_filter_local_attrs(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality(name__value: "low") {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 1


async def test_query_filter_relationships(db, session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="Car")
    person = registry.get_schema(name="Person")

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
        person(name__value: "John") {
            name {
                value
            }
            cars(name__value: "volt") {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"]) == 1
    assert result.data["person"][0]["name"]["value"] == "John"
    assert len(result.data["person"][0]["cars"]) == 1
    assert result.data["person"][0]["cars"][0]["name"]["value"] == "volt"


async def test_query_oneway_relationship(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    query = """
    query {
        person {
            id
            tags {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["tags"]) == 2


async def test_query_at_specific_time(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    time1 = Timestamp()

    t2.name.value = "Green"
    await t2.save(session=session)

    query = """
    query {
        tag {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["tag"]) == 2
    names = sorted([tag["name"]["value"] for tag in result.data["tag"]])
    assert names == ["Blue", "Green"]

    # Now query at a specific time
    query = """
    query {
        tag {
            name {
                value
            }
        }
    }
    """

    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
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
    assert len(result.data["tag"]) == 2
    names = sorted([tag["name"]["value"] for tag in result.data["tag"]])
    assert names == ["Blue", "Red"]


async def test_query_attribute_updated_at(db, session, default_branch: Branch, person_tag_schema):
    p11 = await Node.init(session=session, schema="Person")
    await p11.new(session=session, firstname="John", lastname="Doe")
    await p11.save(session=session)

    query = """
    query {
        person {
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
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["updated_at"]
    assert result1.data["person"][0]["firstname"]["updated_at"] == result1.data["person"][0]["lastname"]["updated_at"]

    p12 = await NodeManager.get_one(session=session, id=p11.id)
    p12.firstname.value = "Jim"
    await p12.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["person"][0]["firstname"]["updated_at"]
    assert result2.data["person"][0]["firstname"]["updated_at"] != result2.data["person"][0]["lastname"]["updated_at"]


async def test_query_node_updated_at(db, session, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    query {
        person {
            _updated_at
            id
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["_updated_at"]

    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, firstname="Jane", lastname="Doe")
    await p2.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["person"][0]["_updated_at"]
    assert result2.data["person"][1]["_updated_at"]
    assert result2.data["person"][1]["_updated_at"] == Timestamp(result2.data["person"][1]["_updated_at"]).to_string()
    assert result2.data["person"][0]["_updated_at"] != result2.data["person"][1]["_updated_at"]


async def test_query_relationship_updated_at(db, session, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    query = """
    query {
        person {
            id
            tags {
                _updated_at
                _relation__updated_at
                name {
                    value
                }
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"] == []

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    result2 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert len(result2.data["person"][0]["tags"]) == 2
    assert (
        result2.data["person"][0]["tags"][0]["_updated_at"]
        != result2.data["person"][0]["tags"][0]["_relation__updated_at"]
    )
    assert (
        result2.data["person"][0]["tags"][0]["_updated_at"]
        == Timestamp(result2.data["person"][0]["tags"][0]["_updated_at"]).to_string()
    )


async def test_query_node_property_source(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(session=session)

    query = """
    query {
        person {
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
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["source"]
    assert result1.data["person"][0]["firstname"]["source"]["name"]["value"] == first_account.name.value


async def test_query_node_property_owner(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", _owner=first_account)
    await p1.save(session=session)

    query = """
    query {
        person {
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
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["owner"]
    assert result1.data["person"][0]["firstname"]["owner"]["name"]["value"] == first_account.name.value


async def test_query_attribute_flag_property(
    db, session, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(
        session=session,
        firstname={"value": "John", "is_protected": True},
        lastname={"value": "Doe", "is_visible": False},
        _source=first_account,
    )
    await p1.save(session=session)

    query = """
    query {
        person {
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
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["is_protected"] is True
    assert result1.data["person"][0]["lastname"]["is_visible"] is False


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
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
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
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["branch1"][0]["name"] == "main"
    assert result1.data["branch2"][0]["name"] == "main"


async def test_multiple_queries(db, session, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, firstname="Jane", lastname="Doe")
    await p2.save(session=session)

    query = """
    query {
        firstperson: person(firstname__value: "John") {
            id
            firstname {
                value
            }
        }
        secondperson: person(firstname__value: "Jane") {
            id
            firstname {
                value
            }
        }
    }
    """
    result1 = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["firstperson"][0]["firstname"]["value"] == "John"
    assert result1.data["secondperson"][0]["firstname"]["value"] == "Jane"


async def test_model_node_interface(db, session, default_branch: Branch, car_schema):
    d1 = await Node.init(session=session, schema="Car")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    d2 = await Node.init(session=session, schema="Car")
    await d2.new(session=session, name="Renaud Clio", nbr_doors=4)
    await d2.save(session=session)

    query = """
    query {
        car {
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
    """
    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert sorted([car["name"]["value"] for car in result.data["car"]]) == ["Porsche 911", "Renaud Clio"]
    assert sorted([car["nbr_doors"]["value"] for car in result.data["car"]]) == [2, 4]


async def test_model_rel_interface(db, session, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(session=session, schema="Car")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    b1 = await Node.init(session=session, schema="Boat")
    await b1.new(session=session, name="Laser", has_sails=True)
    await b1.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John Doe", vehicules=[d1, b1])
    await p1.save(session=session)

    query = """
    query {
        person {
            name {
                value
            }
            vehicules {
                name {
                    value
                }
                ... on RelatedCar {
                    nbr_doors {
                        value
                    }
                }
                ... on RelatedBoat {
                    has_sails {
                        value
                    }
                }
            }
        }
    }
    """

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["vehicules"]) == 2

    assert result.data["person"][0] == {
        "name": {"value": "John Doe"},
        "vehicules": [
            {"name": {"value": "Porsche 911"}, "nbr_doors": {"value": 2}},
            {"has_sails": {"value": True}, "name": {"value": "Laser"}},
        ],
    }


async def test_model_rel_interface_reverse(db, session, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(session=session, schema="Car")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    b1 = await Node.init(session=session, schema="Boat")
    await b1.new(session=session, name="Laser", has_sails=True)
    await b1.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John Doe", vehicules=[d1, b1])
    await p1.save(session=session)

    query = """
    query {
        boat {
            name {
                value
            }
            owners {
                name {
                    value
                }
            }
        }
    }
    """

    result = await graphql(
        await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["boat"][0]["owners"]) == 1


async def test_union_relationship(
    db, session, default_branch: Branch, generic_vehicule_schema, car_schema, truck_schema, motorcycle_schema
):
    SCHEMA = {
        "name": "person",
        "kind": "Person",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
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

    schema = await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False)

    result = await graphql(
        schema=schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["road_vehicules"]) == 3
    assert result.data["person"][0] == {
        "name": {"value": "John Doe"},
        "road_vehicules": [
            {"nbr_doors": {"value": 2}},
            {"nbr_axles": {"value": 4}},
            {"nbr_seats": {"value": 1}},
        ],
    }


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
            {"name": "name", "kind": "String", "unique": True},
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

    schema = await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False)

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

    schema = await generate_graphql_schema(session=session, include_mutation=False, include_subscription=False)

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
            "kind": "Car",
        },
        {
            "action": "updated",
            "branch": "branch1",
            "attributes": [{"action": "updated", "name": "nbr_seats"}],
            "changed_at": None,
            "id": "c1",
            "kind": "Car",
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
            "kind": "Car",
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
            "kind": "Car",
        },
    ]

    expected_rels = [
        {
            "action": "updated",
            "branch": "main",
            "changed_at": None,
            "id": "r1",
            "name": "car__person",
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
            "name": "car__person",
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
            "name": "car__person",
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
