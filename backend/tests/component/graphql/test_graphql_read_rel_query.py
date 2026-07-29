from copy import deepcopy
from typing import Any

import pytest
from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_display_hfid_related_node(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    person_schema = animal_person_schema.get_node(name="TestPerson")
    dog_schema = animal_person_schema.get_node(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    hfid
                    animals {
                        edges {
                            node {
                                hfid
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
    assert result.data
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0] == {
        "node": {
            "animals": {"edges": [{"node": {"hfid": ["Jack", "Rocky"]}}]},
            "hfid": ["Jack"],
        },
    }


async def test_nested_query(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    car = registry.schema.get_node_schema(name="TestCar")
    person = registry.schema.get_node_schema(name="TestPerson")

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
    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1
    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, c3.id}


async def test_double_nested_query(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    car = registry.schema.get_node_schema(name="TestCar")
    person = registry.schema.get_node_schema(name="TestPerson")

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
    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1
    assert result_per_name["John"]["cars"]["count"] == 2
    assert result_per_name["Jane"]["cars"]["count"] == 1
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["node"]["name"]["value"] == "John"

    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, c3.id}


async def test_nested_query_single_relationship(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    raw_schema = {
        "version": "1.0",
        "generics": [
            {
                "name": "Generic",
                "namespace": "Location",
                "hierarchical": True,
                "attributes": [{"name": "name", "optional": False, "kind": "Text"}],
                "relationships": [{"name": "devices", "peer": "InfraDevice", "cardinality": "many", "optional": True}],
            }
        ],
        "nodes": [
            {
                "name": "Device",
                "namespace": "Infra",
                "attributes": [{"name": "name", "kind": "Text", "optional": False}],
                "relationships": [
                    {"name": "location", "peer": "LocationGeneric", "optional": False, "cardinality": "one"}
                ],
            },
            {
                "name": "Site",
                "namespace": "Location",
                "inherit_from": ["LocationGeneric"],
                "attributes": [{"name": "description", "optional": False, "kind": "Text"}],
            },
        ],
    }
    schema = SchemaRoot(**raw_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    site_schema = schema_branch.get_node(name="LocationSite")
    device_schema = schema_branch.get_node(name="InfraDevice")

    site1 = await Node.init(db=db, schema=site_schema, branch=default_branch)
    await site1.new(db=db, name="site1", description="test")
    await site1.save(db=db)

    device1 = await Node.init(db=db, schema=device_schema, branch=default_branch)
    await device1.new(db=db, name="device1", location=site1)
    await device1.save(db=db)

    device2 = await Node.init(db=db, schema=device_schema, branch=default_branch)
    await device2.new(db=db, name="device2", location=site1)
    await device2.save(db=db)

    query = """
    fragment LocationData on LocationSite {
        name {
            value
        }
        devices {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }

    query {
        InfraDevice {
            edges {
                node {
                    name {
                        value
                    }
                    location {
                        node {
                            ... LocationData
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
    assert result.data
    result_per_name = {
        result["node"]["name"]["value"]: result["node"] for result in result.data["InfraDevice"]["edges"]
    }
    assert sorted(result_per_name.keys()) == ["device1", "device2"]
    expected_location_data = {
        "node": {
            "name": {"value": "site1"},
            "devices": {"edges": [{"node": {"name": {"value": "device1"}}}, {"node": {"name": {"value": "device2"}}}]},
        }
    }
    assert result.data["InfraDevice"]["edges"][0]["node"]["location"] == expected_location_data
    assert result.data["InfraDevice"]["edges"][1]["node"]["location"] == expected_location_data


async def test_nested_generic_query_many_relationship(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Validates that nested GraphQL fragments work for cardinality=many relationships."""
    raw_schema = {
        "version": "1.0",
        "generics": [
            {
                "name": "Generic",
                "namespace": "Location",
                "hierarchical": True,
                "attributes": [{"name": "name", "optional": False, "kind": "Text"}],
                "relationships": [{"name": "devices", "peer": "InfraDevice", "cardinality": "many", "optional": True}],
            }
        ],
        "nodes": [
            {
                "name": "Device",
                "namespace": "Infra",
                "attributes": [{"name": "name", "kind": "Text", "optional": False}],
                "relationships": [
                    {"name": "location", "peer": "LocationGeneric", "optional": False, "cardinality": "one"}
                ],
            },
            {
                "name": "Site",
                "namespace": "Location",
                "inherit_from": ["LocationGeneric"],
                "attributes": [{"name": "description", "optional": False, "kind": "Text"}],
            },
        ],
    }
    schema = SchemaRoot(**raw_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    site_schema = schema_branch.get_node(name="LocationSite")
    device_schema = schema_branch.get_node(name="InfraDevice")

    site1 = await Node.init(db=db, schema=site_schema, branch=default_branch)
    await site1.new(db=db, name="site1", description="test")
    await site1.save(db=db)

    device1 = await Node.init(db=db, schema=device_schema, branch=default_branch)
    await device1.new(db=db, name="device1", location=site1)
    await device1.save(db=db)

    device2 = await Node.init(db=db, schema=device_schema, branch=default_branch)
    await device2.new(db=db, name="device2", location=site1)
    await device2.save(db=db)

    query = """
    fragment DeviceData on InfraDevice {
        name {
            value
        }
    }

    fragment LocationData on LocationSite {
        name {
            value
        }
        devices {
            edges {
            node {
                ...DeviceData
            }
            }
        }
    }

    query {
        LocationSite {
            edges {
            node {
                ...LocationData
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

    assert result.data == {
        "LocationSite": {
            "edges": [
                {
                    "node": {
                        "name": {"value": "site1"},
                        "devices": {
                            "edges": [
                                {"node": {"name": {"value": "device1"}}},
                                {"node": {"name": {"value": "device2"}}},
                            ]
                        },
                    }
                }
            ]
        }
    }


async def test_query_relationship_multiple_values(
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
    c4 = await Node.init(db=db, schema=car)
    await c4.new(db=db, name="yaris", nbr_seats=5, is_electric=False, owner=p1)
    await c4.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars (name__values: ["volt", "nolt"]) {
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
    assert len(result.data["TestPerson"]["edges"]) == 2
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert result.data["TestPerson"]["edges"][1]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "nolt"


async def test_query_oneway_relationship(db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="Red")
    await t2.save(db=db)
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(db=db)

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
    assert len(result.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2


async def test_query_relationship_updated_at(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None
) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="Red")
    await t2.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    tags {
                        edges {
                            node_metadata {
                                updated_at
                            }
                            node {
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data
    assert result1.data["TestPerson"]["edges"] == []

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result2 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data
    assert len(result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2
    assert result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node_metadata"]["updated_at"] is not None
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node_metadata"]["updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["properties"]["updated_at"]
    )
    assert result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node_metadata"][
        "updated_at"
    ] == Timestamp(
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node_metadata"]["updated_at"]
    ).to_string(with_z=False)


async def test_query_relationship_node_property(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, first_account: Node
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
    await c1.new(
        db=db,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1, "_relation__owner": first_account.id},
    )
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(
        db=db,
        name="bolt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p2, "_relation__source": first_account.id},
    )
    await c2.save(db=db)

    # test many relationship query
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
    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestPerson"]["edges"]}
    assert sorted(results.keys()) == ["Jane", "John"]
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
    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, first_account.id}

    # test single relationship query
    query = """
    query {
        TestCar {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    owner {
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
    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestCar"]["edges"]}
    assert set(results.keys()) == {"volt", "bolt"}

    assert results["volt"]["owner"]["node"]["name"]["value"] == "John"
    assert results["volt"]["owner"]["properties"]["owner"]
    assert results["volt"]["owner"]["properties"]["owner"]["id"] == first_account.id
    assert results["volt"]["owner"]["properties"]["source"] is None

    assert results["bolt"]["owner"]["node"]["name"]["value"] == "Jane"
    assert results["bolt"]["owner"]["properties"]["owner"] is None
    assert results["bolt"]["owner"]["properties"]["source"]
    assert results["bolt"]["owner"]["properties"]["source"]["id"] == first_account.id
    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, first_account.id}

    # test many relationship query with mixed properties on peer
    query = """
    query {
        people_with_cars_and_owners: TestPerson {
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
                            }
                        }
                    }
                }
            }
        }
        people_with_cars_and_sources: TestPerson {
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

    owner_results = {
        item["node"]["name"]["value"]: item["node"] for item in result.data["people_with_cars_and_owners"]["edges"]
    }
    assert sorted(owner_results.keys()) == ["Jane", "John"]
    assert len(owner_results["John"]["cars"]["edges"]) == 1
    assert len(owner_results["Jane"]["cars"]["edges"]) == 1

    assert owner_results["John"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert owner_results["John"]["cars"]["edges"][0]["properties"]["owner"]
    assert owner_results["John"]["cars"]["edges"][0]["properties"]["owner"]["id"] == first_account.id
    assert "source" not in owner_results["John"]["cars"]["edges"][0]["properties"]

    assert owner_results["Jane"]["cars"]["edges"][0]["node"]["name"]["value"] == "bolt"
    assert owner_results["Jane"]["cars"]["edges"][0]["properties"]["owner"] is None
    assert "source" not in owner_results["Jane"]["cars"]["edges"][0]["properties"]

    source_results = {
        item["node"]["name"]["value"]: item["node"] for item in result.data["people_with_cars_and_sources"]["edges"]
    }
    assert sorted(source_results.keys()) == ["Jane", "John"]
    assert len(source_results["John"]["cars"]["edges"]) == 1
    assert len(source_results["Jane"]["cars"]["edges"]) == 1

    assert source_results["John"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert "owner" not in source_results["John"]["cars"]["edges"][0]["properties"]
    assert source_results["John"]["cars"]["edges"][0]["properties"]["source"] is None

    assert source_results["Jane"]["cars"]["edges"][0]["node"]["name"]["value"] == "bolt"
    assert "owner" not in source_results["Jane"]["cars"]["edges"][0]["properties"]
    assert source_results["Jane"]["cars"]["edges"][0]["properties"]["source"]
    assert source_results["Jane"]["cars"]["edges"][0]["properties"]["source"]["id"] == first_account.id

    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, first_account.id}


async def test_same_many_relationship_with_different_limits_offsets(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_prius_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
) -> None:
    query = """
    query {
        people_with_cars_1: TestPerson {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    cars(limit: 1, offset: 0) {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
        people_with_cars_2: TestPerson {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    cars(limit: 1, offset: 1) {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
    """
    john_cars_by_uuid = sorted([car_accord_main, car_prius_main], key=lambda c: c.id)
    jane_cars_by_uuid = sorted([car_camry_main, car_yaris_main], key=lambda c: c.id)

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

    for person_node in result.data["people_with_cars_1"]["edges"]:
        person_name = person_node["node"]["name"]["value"]
        assert len(person_node["node"]["cars"]["edges"]) == 1
        if person_name == "John":
            assert person_node["node"]["cars"]["edges"][0]["node"]["id"] == john_cars_by_uuid[0].id
        elif person_name == "Jane":
            assert person_node["node"]["cars"]["edges"][0]["node"]["id"] == jane_cars_by_uuid[0].id
    for person_node in result.data["people_with_cars_2"]["edges"]:
        person_name = person_node["node"]["name"]["value"]
        assert len(person_node["node"]["cars"]["edges"]) == 1
        if person_name == "John":
            assert person_node["node"]["cars"]["edges"][0]["node"]["id"] == john_cars_by_uuid[1].id
        elif person_name == "Jane":
            assert person_node["node"]["cars"]["edges"][0]["node"]["id"] == jane_cars_by_uuid[1].id


async def test_model_rel_interface(db: InfrahubDatabase, default_branch: Branch, vehicule_person_schema: None) -> None:
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    b1 = await Node.init(db=db, schema="TestBoat")
    await b1.new(db=db, name="Laser", has_sails=True)
    await b1.save(db=db)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John Doe", vehicules=[d1, b1])
    await p1.save(db=db)

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


async def test_model_rel_interface_reverse(
    db: InfrahubDatabase, default_branch: Branch, vehicule_person_schema: None
) -> None:
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    b1 = await Node.init(db=db, schema="TestBoat")
    await b1.new(db=db, name="Laser", has_sails=True)
    await b1.save(db=db)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John Doe", vehicules=[d1, b1])
    await p1.save(db=db)

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
    assert len(result.data["TestBoat"]["edges"][0]["node"]["owners"]["edges"]) == 1


async def test_properties_on_different_query_paths(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data_thing: dict[str, Node],
    account_bob: Node,
    account_bill: Node,
) -> None:
    paris_owner = account_bob
    paris_rack_ids = [node.id for name, node in hierarchical_location_data_thing.items() if name.startswith("paris-r")]
    paris_racks = await NodeManager.get_many(db=db, ids=paris_rack_ids)
    for rack in paris_racks.values():
        thing_rels = await rack.things.get_relationships(db=db)
        await rack.things.update(
            db=db, data=[{"id": rel.peer_id, "_relation__owner": paris_owner.id} for rel in thing_rels]
        )
        await rack.save(db=db)

    london_source = account_bill
    london_rack_ids = [
        node.id for name, node in hierarchical_location_data_thing.items() if name.startswith("london-r")
    ]
    london_racks = await NodeManager.get_many(db=db, ids=london_rack_ids)
    for rack in london_racks.values():
        thing_rels = await rack.things.get_relationships(db=db)
        await rack.things.update(
            db=db, data=[{"id": rel.peer_id, "_relation__source": london_source.id} for rel in thing_rels]
        )
        await rack.save(db=db)

    query = """
    query GetRack {
        LocationRack(parent__name__values: "europe") {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    things {
                        edges {
                            properties {
                                owner {
                                    id
                                }
                            }
                            node {
                                id
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
        LocationSite(parent__name__values: "europe") {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    children {
                        edges {
                            node {
                                name {
                                    value
                                }
                                things {
                                    edges {
                                        properties {
                                        source {
                                                id
                                            }
                                        }
                                        node {
                                            id
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

    # check owners are correct
    for rack in result.data["LocationRack"]["edges"]:
        rack_name = rack["node"]["name"]["value"]
        for thing_rel in rack["node"]["things"]["edges"]:
            assert "source" not in thing_rel["properties"]
            if rack_name.startswith("paris"):
                assert thing_rel["properties"]["owner"]["id"] == paris_owner.id
            else:
                assert thing_rel["properties"]["owner"] is None

    # check sources are correct
    for site in result.data["LocationSite"]["edges"]:
        for rack in site["node"]["children"]["edges"]:
            rack_name = rack["node"]["name"]["value"]
            for thing_rel in rack["node"]["things"]["edges"]:
                assert "owner" not in thing_rel["properties"]
                if rack_name.startswith("london"):
                    assert thing_rel["properties"]["source"]["id"] == london_source.id
                else:
                    assert thing_rel["properties"]["source"] is None


async def test_single_relationship_id_only_uses_preloaded_peer_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema_unregistered: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cardinality-one peer ID relationship shortcut

    TestAnimal is a generic, so favorite_animal is a cardinality-one relationship whose
    GraphQL node field is an interface: the id-only shortcut can only answer it without
    hydrating the peer when the preloaded stub carries the peer's concrete kind. owner
    covers the same shortcut when the peer field is a concrete node type.
    """
    schema_dict = deepcopy(animal_person_schema_unregistered)
    person_node = next(node for node in schema_dict["nodes"] if node["name"] == "Person")
    person_node["relationships"].append(
        {
            "name": "favorite_animal",
            "peer": "TestAnimal",
            "optional": True,
            "identifier": "person__favorite_animal",
            "cardinality": "one",
            "direction": "outbound",
        }
    )
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**schema_dict), branch=default_branch.name)

    person_schema = schema_branch.get_node(name="TestPerson", duplicate=False)
    dog_schema = schema_branch.get_node(name="TestDog", duplicate=False)

    person = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person.new(db=db, name="Jack")
    await person.save(db=db)

    dog = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=person)
    await dog.save(db=db)

    await person.get_relationship("favorite_animal").update(db=db, data=dog)
    await person.save(db=db)

    async def fail_node_load(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the ID-only relationship unexpectedly used NodeDataLoader")

    monkeypatch.setattr(
        "infrahub.graphql.resolvers.single_relationship.NodeDataLoader.load",
        fail_node_load,
    )

    default_branch.update_schema_hash()

    concrete_peer_query = """
    query {
        TestDog {
            edges {
                node {
                    id
                    owner { node { id } }
                }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=concrete_peer_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data == {"TestDog": {"edges": [{"node": {"id": dog.id, "owner": {"node": {"id": person.id}}}}]}}
    assert gql_params.context.related_node_ids == {dog.id, person.id}

    generic_peer_query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    favorite_animal { node { id } }
                }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=generic_peer_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data == {
        "TestPerson": {"edges": [{"node": {"id": person.id, "favorite_animal": {"node": {"id": dog.id}}}}]}
    }
    assert gql_params.context.related_node_ids == {person.id, dog.id}
