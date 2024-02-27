import pytest
from deepdiff import DeepDiff

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.graphql import graphql_query


@pytest.mark.parametrize("filter_value", ["l", "o", "w", "low"])
async def test_query_filter_local_attrs_partial_match(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema, filter_value
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = (
        """
    query {
        TestCriticality(name__value: "%s", partial_match: true) {
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
        % filter_value
    )
    result = await graphql_query(query=query, db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["name"]["value"] == "low"


async def test_query_filter_local_int_attr_partial_match(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality(level__value: 4, partial_match: true) {
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
    result = await graphql_query(query=query, db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["count"] == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["name"]["value"] == "low"


async def test_query_filter_local_bool_attr_partial_match(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4, is_false=True)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality(is_false__value: true, partial_match: true) {
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
    result = await graphql_query(query=query, db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["count"] == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["name"]["value"] == "low"


async def test_query_filter_relationships_with_generic_filter_partial_match(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data
):
    query = """
    query {
        TestPerson(cars__name__value: "v", partial_match: true) {
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
    result = await graphql_query(query=query, db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    expected_results = [
        {
            "node": {
                "name": {"value": "John"},
                "cars": {"edges": [{"node": {"name": {"value": "bolt"}}}, {"node": {"name": {"value": "volt"}}}]},
            }
        }
    ]
    assert DeepDiff(result.data["TestPerson"]["edges"], expected_results, ignore_order=True).to_dict() == {}


async def test_query_filter_relationships_with_generic_filter_mutliple_partial_match(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, person_john_main, person_jane_main
):
    volt_car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await volt_car.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=person_john_main.id)
    await volt_car.save(db=db)
    colt_car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await colt_car.new(db=db, name="colt", nbr_seats=4, is_electric=True, owner=person_john_main.id)
    await colt_car.save(db=db)
    smolt_car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await smolt_car.new(db=db, name="smolt", nbr_seats=4, is_electric=True, owner=person_jane_main.id)
    await smolt_car.save(db=db)

    query = """
    query {
        TestCar(name__value: "olt", owner__name__value: "ane", partial_match: true) {
            edges {
                node {
                    id
                }
            }
        }
    }
    """
    result = await graphql_query(query=query, db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == smolt_car.id
