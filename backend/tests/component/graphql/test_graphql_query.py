from typing import Literal

import pytest
from deepdiff import DeepDiff

from infrahub import __version__, config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.registry import registry as graphql_registry
from tests.helpers.graphql import graphql


async def test_info_query(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema) -> None:
    query = """
    query {
        InfrahubInfo {
            version
        }
    }
    """
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=query,
        context_value=params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubInfo"]["version"] == __version__


async def test_simple_query(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

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
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert gql_params.context.related_node_ids == {obj1.id, obj2.id}


async def test_simple_query_with_offset_and_limit(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

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
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 1


async def test_display_hfid(db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = """
    query {
        TestDog {
            edges {
                node {
                    id
                    hfid
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
    assert len(result.data["TestDog"]["edges"]) == 1
    assert result.data["TestDog"]["edges"][0] == {
        "node": {
            "display_label": await dog1.get_display_label(db=db),
            "hfid": ["Jack", "Rocky"],
            "id": dog1.id,
        },
    }


async def test_all_attributes(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None, all_attribute_types_schema: NodeSchema
) -> None:
    obj1 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj1.new(
        db=db,
        name="obj1",
        mystring="abc",
        mybool=False,
        myint=123,
        mylist=["1", 2, False],
        myjson={"key1": "bill"},
        ipaddress="10.5.0.1/27",
        prefix="10.1.0.0/22",
        bare_address="10.5.0.1",
    )
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj2.new(db=db, name="obj2")
    await obj2.save(db=db)

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
                    ipaddress {
                        value
                        prefixlen
                        netmask
                    }
                    prefix {
                        value
                        prefixlen
                        netmask
                    }
                    bare_address {
                        __typename
                        value
                        version
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
    assert len(result.data["TestAllAttributeTypes"]["edges"]) == 2

    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestAllAttributeTypes"]["edges"]}

    assert results["obj1"]["mystring"]["value"] == obj1.mystring.value
    assert results["obj1"]["mybool"]["value"] == obj1.mybool.value
    assert results["obj1"]["myint"]["value"] == obj1.myint.value
    assert results["obj1"]["mylist"]["value"] == obj1.mylist.value
    assert results["obj1"]["myjson"]["value"] == obj1.myjson.value
    assert results["obj1"]["ipaddress"]["value"] == obj1.ipaddress.value
    assert results["obj1"]["ipaddress"]["netmask"] == obj1.ipaddress.netmask
    assert results["obj1"]["ipaddress"]["prefixlen"] == obj1.ipaddress.prefixlen
    assert results["obj1"]["prefix"]["value"] == obj1.prefix.value
    assert results["obj1"]["prefix"]["netmask"] == obj1.prefix.netmask
    assert results["obj1"]["prefix"]["prefixlen"] == obj1.prefix.prefixlen
    # a bare address round-trips without gaining a prefix, unlike the IPHost attribute above
    assert results["obj1"]["bare_address"]["__typename"] == "IPAddress"
    assert results["obj1"]["bare_address"]["value"] == "10.5.0.1"
    assert results["obj1"]["bare_address"]["version"] == 4

    assert results["obj2"]["mystring"]["value"] == obj2.mystring.value
    assert results["obj2"]["mybool"]["value"] == obj2.mybool.value
    assert results["obj2"]["myint"]["value"] == obj2.myint.value
    assert results["obj2"]["mylist"]["value"] == obj2.mylist.value
    assert results["obj2"]["myjson"]["value"] == obj2.myjson.value
    assert results["obj2"]["ipaddress"]["value"] == obj2.ipaddress.value
    assert results["obj2"]["ipaddress"]["netmask"] is None
    assert results["obj2"]["ipaddress"]["prefixlen"] is None
    assert results["obj2"]["prefix"]["value"] == obj2.prefix.value
    assert results["obj2"]["prefix"]["netmask"] is None
    assert results["obj2"]["prefix"]["prefixlen"] is None
    assert results["obj2"]["bare_address"]["value"] == obj2.bare_address.value
    assert results["obj2"]["bare_address"]["version"] is None


async def test_ipaddress_attribute_filters(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None, all_attribute_types_schema: NodeSchema
) -> None:
    """An IPAddress attribute exposes the same filters as IPHost, matching on the normalized value."""
    obj1 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj1.new(db=db, name="obj1", bare_address="2001:0DB8::0001")
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj2.new(db=db, name="obj2", bare_address="10.0.0.2")
    await obj2.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    async def names_for(filters: str) -> list[str]:
        result = await graphql(
            schema=gql_params.schema,
            source="query { TestAllAttributeTypes(%s) { edges { node { name { value } } } } }" % filters,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert result.errors is None
        assert result.data
        return sorted(item["node"]["name"]["value"] for item in result.data["TestAllAttributeTypes"]["edges"])

    # the compressed form matches, the expanded input form does not
    assert await names_for('bare_address__value: "2001:db8::1"') == ["obj1"]
    assert await names_for('bare_address__value: "2001:0DB8::0001"') == []
    assert await names_for('bare_address__values: ["2001:db8::1", "10.0.0.2"]') == ["obj1", "obj2"]
    assert await names_for("bare_address__isnull: true") == []
    assert await names_for("bare_address__is_protected: false") == ["obj1", "obj2"]


async def test_query_typename(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.data
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


async def test_query_filter_ids(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)
    obj3 = await Node.init(db=db, schema=criticality_schema)
    await obj3.new(db=db, name="high", level=1, description="My desc", color="#222222")
    await obj3.save(db=db)

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


async def test_query_filter_relationship_isnull(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_albert_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    car_camry_main: Node,
    car_accord_main: Node,
) -> None:
    query = """
    query {
        TestPerson(cars__isnull: true) {
            count
            edges {
                node {
                    id
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
    assert result.data["TestPerson"]["count"] == 1
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["id"] == person_albert_main.id

    query = """
    query {
        TestPerson(cars__isnull: false) {
            count
            edges {
                node {
                    id
                }
            }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPerson"]["count"] == 2
    assert len(result.data["TestPerson"]["edges"]) == 2
    result_person_ids = {node["node"]["id"] for node in result.data["TestPerson"]["edges"]}
    assert result_person_ids == {person_john_main.id, person_jane_main.id}


async def test_query_filter_attribute_isnull(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_albert_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    car_camry_main: Node,
    car_accord_main: Node,
) -> None:
    person_albert = await NodeManager.get_one(db=db, id=person_albert_main.id)
    person_albert.height.value = None
    await person_albert.save(db=db)

    query = """
    query {
        TestPerson(height__isnull: true) {
            count
            edges {
                node {
                    id
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
    assert result.data["TestPerson"]["count"] == 1
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["id"] == person_albert_main.id

    query = """
    query {
        TestPerson(height__isnull: false) {
            count
            edges {
                node {
                    id
                }
            }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPerson"]["count"] == 2
    assert len(result.data["TestPerson"]["edges"]) == 2
    result_person_ids = {node["node"]["id"] for node in result.data["TestPerson"]["edges"]}
    assert result_person_ids == {person_john_main.id, person_jane_main.id}


async def test_query_filter_local_attrs(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

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


@pytest.mark.parametrize("graphql_enums_on,enum_value", [(True, "MANUAL"), (False, '"manual"')])
async def test_query_filter_on_enum(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
    graphql_enums_on: bool,
    enum_value: Literal["MANUAL", '"manual"'],
    reset_graphql_schema_between_tests: None,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = graphql_enums_on
    car = registry.schema.get(name="TestCar")

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="GoKart", nbr_seats=1, is_electric=True, owner=person_john_main, transmission="manual")
    await c1.save(db=db)

    query = """
    query {
        TestCar(transmission__value: %s) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (enum_value)
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
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["name"]["value"] == "GoKart"


async def test_query_multiple_filters(
    db: InfrahubDatabase, default_branch: Branch, car_person_manufacturer_schema: None
) -> None:
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")
    manufacturer = registry.schema.get(name="TestManufacturer")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    m1 = await Node.init(db=db, schema=manufacturer)
    await m1.new(db=db, name="chevrolet")
    await m1.save(db=db)
    m2 = await Node.init(db=db, schema=manufacturer)
    await m2.new(db=db, name="ford", description="from Michigan")
    await m2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=False, owner=p1, manufacturer=m1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=3, is_electric=True, owner=p1, manufacturer=m2)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2, manufacturer=m1)
    await c3.save(db=db)

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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query01,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query02,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c3.id

    query03 = """
    query {
        TestCar(owner__name__value: "John", manufacturer__name__value: "ford") {
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query03,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id

    query04 = """
    query {
        TestCar(owner__ids: ["%s"], manufacturer__ids: ["%s"]) {
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query04,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id

    # test filter by peer ID after node kind migration
    person_schema = registry.schema.get("TestPerson", branch=default_branch)
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    assert person_schema.kind == "Test2NewPerson"
    registry.schema.set(name="Test2NewPerson", schema=person_schema, branch=default_branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get(name="TestPerson", branch=default_branch),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    query05 = """
    query {
        TestCar(owner__ids: ["%s"]) {
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
    """ % (p1.id)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query05,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestCar"]["edges"]) == 2
    assert {node["node"]["id"] for node in result.data["TestCar"]["edges"]} == {c1.id, c2.id}


async def test_query_filter_relationships(
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
    assert result.data["TestPerson"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationships_with_generic(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> None:
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
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationships_with_generic_filter(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> None:
    query = """
    query {
        TestPerson(cars__name__value: "volt") {
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

    expected_results = [
        {
            "node": {
                "name": {"value": "John"},
                "cars": {"edges": [{"node": {"name": {"value": "bolt"}}}, {"node": {"name": {"value": "volt"}}}]},
            }
        }
    ]
    assert result.data
    assert DeepDiff(result.data["TestPerson"]["edges"], expected_results, ignore_order=True).to_dict() == {}


async def test_query_filter_relationship_id(
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

    query = (
        """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(ids: ["%s"]) {
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
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"

    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(ids: ["%s", "%s"]) {
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
    """ % (
        c1.id,
        c4.id,
    )
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
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 2


@pytest.mark.parametrize(
    "graphql_filter,expected_results",
    [
        ('mylist__value: "tree"', ["obj1", "obj2"]),
        ("mylist__value: 2", ["obj2", "obj3", "obj5"]),
        ('mylist__value: "one", level__value: 2', ["obj2"]),
        ('mylist__values: ["one"]', ["obj1", "obj2", "obj3"]),
        ('mylist__values: ["one", "two"]', ["obj1", "obj2", "obj3", "obj5"]),
        ('mylist__values: ["one", 5]', ["obj1", "obj2", "obj3", "obj4"]),
        ("mylist__value: true", ["obj3"]),
        ("mylist__values: [true]", ["obj3"]),
        ("mylist__values: [true, false]", ["obj3", "obj5"]),
    ],
)
async def test_query_filter_list(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    graphql_filter: str,
    expected_results: list[str],
) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="obj1", level=1, mylist=["one", "two", "tree", 5])
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="obj2", level=2, mylist=["one", 2, "tree"])
    await obj2.save(db=db)
    obj3 = await Node.init(db=db, schema=criticality_schema)
    await obj3.new(db=db, name="obj3", level=3, mylist=["one", "two", True, 2])
    await obj3.save(db=db)
    obj4 = await Node.init(db=db, schema=criticality_schema)
    await obj4.new(db=db, name="obj4", level=4, mylist=["anotherone", "twotree", "true", "2", 5])
    await obj4.save(db=db)
    obj5 = await Node.init(db=db, schema=criticality_schema)
    await obj5.new(db=db, name="obj5", level=5, mylist=["oneone", "two", False, 2])
    await obj5.save(db=db)

    query = """
    query {
        TestCriticality(%(filter)s) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % {"filter": graphql_filter}
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
    names = sorted([item["node"]["name"]["value"] for item in result.data["TestCriticality"]["edges"]])
    assert names == expected_results


async def test_query_attribute_multiple_values(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)

    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    query = """
    query {
        TestPerson(name__values: ["John", "Jane"]) {
            count
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
    assert result.data["TestPerson"]["count"] == 2


async def test_query_at_specific_time(db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None) -> None:
    t1 = await Node.init(db=db, schema="TestingTag")
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema="TestingTag")
    await t2.new(db=db, name="Red")
    await t2.save(db=db)

    time1 = Timestamp()

    t2.name.value = "Green"
    await t2.save(db=db)

    query = """
    query {
        TestingTag {
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
    assert len(result.data["TestingTag"]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data["TestingTag"]["edges"]])
    assert names == ["Blue", "Green"]

    # Now query at a specific time
    query = """
    query {
        TestingTag {
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, at=time1, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["TestingTag"]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data["TestingTag"]["edges"]])
    assert names == ["Blue", "Red"]


async def test_query_attribute_updated_at(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None
) -> None:
    p11 = await Node.init(db=db, schema="TestPerson")
    await p11.new(db=db, firstname="John", lastname="Doe")
    await p11.save(db=db)

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
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        == result1.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )

    p12 = await NodeManager.get_one(db=db, id=p11.id)
    p12.firstname.value = "Jim"
    await p12.save(db=db)

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
    assert result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )


async def test_query_node_updated_at(db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe")
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node_metadata {
                    updated_at
                }
                node {
                    id
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
    assert result1.data["TestPerson"]["edges"][0]["node"]["id"]
    assert result1.data["TestPerson"]["edges"][0]["node_metadata"]["updated_at"]

    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, firstname="Jane", lastname="Doe")
    await p2.save(db=db)

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
    assert result2.data["TestPerson"]["edges"][0]["node_metadata"]["updated_at"]
    assert result2.data["TestPerson"]["edges"][1]["node_metadata"]["updated_at"]
    assert result2.data["TestPerson"]["edges"][1]["node_metadata"]["updated_at"] == Timestamp(
        result2.data["TestPerson"]["edges"][1]["node_metadata"]["updated_at"]
    ).to_string(with_z=False)
    assert (
        result2.data["TestPerson"]["edges"][0]["node_metadata"]["updated_at"]
        != result2.data["TestPerson"]["edges"][1]["node_metadata"]["updated_at"]
    )


# TODO IFC-1813 add test for cardinality-one updated_at


async def test_query_attribute_node_property_source(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    person_tag_schema: None,
    first_account: Node,
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        source {
                            id
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
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]["id"] == first_account.id
    assert gql_params.context.related_node_ids == {p1.id, first_account.id}


async def test_query_attribute_node_property_owner(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    first_account: Node,
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", _owner=first_account)
    await p1.save(db=db)

    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(
        db=db,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1},
    )
    await c1.save(db=db)

    # test node-level query
    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    name {
                        value
                        owner {
                            id
                            display_label
                        }
                        is_from_profile
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
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["owner"]
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["owner"]["id"] == first_account.id
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["owner"][
        "display_label"
    ] == await first_account.get_display_label(db=db)
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["is_from_profile"] is False
    assert gql_params.context.related_node_ids == {p1.id, first_account.id}

    # test relationship-level query
    query = """
    query {
        TestCar {
            edges {
                node {
                    id
                    owner {
                        node {
                            id
                            name {
                                value
                                owner {
                                    id
                                    display_label
                                }
                                is_from_profile
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
    result2 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None

    assert result2.data
    assert result2.data["TestCar"]["edges"][0]["node"]["owner"]["node"]["name"]["owner"]
    assert result2.data["TestCar"]["edges"][0]["node"]["owner"]["node"]["name"]["owner"]["id"] == first_account.id
    assert result2.data["TestCar"]["edges"][0]["node"]["owner"]["node"]["name"]["owner"][
        "display_label"
    ] == await first_account.get_display_label(db=db)
    assert result2.data["TestCar"]["edges"][0]["node"]["owner"]["node"]["name"]["is_from_profile"] is False
    assert gql_params.context.related_node_ids == {c1.id, p1.id, first_account.id}


async def test_query_attribute_flag_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    person_tag_schema: None,
    first_account: Node,
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(
        db=db,
        firstname={"value": "John", "is_protected": True},
        lastname={"value": "Doe"},
        _source=first_account,
    )
    await p1.save(db=db)

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
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["is_protected"] is True


async def test_query_branches(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    query = """
    query {
        Branch {
            id
            name
            branched_from
            sync_with_git
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
    assert result1.data["Branch"][0]["name"] == "main"


async def test_query_multiple_branches(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    query = """
    query {
        branch1: Branch {
            id
            name
            branched_from
            sync_with_git
        }
        branch2: Branch {
            id
            name
            branched_from
            sync_with_git
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
    assert result1.data["branch1"][0]["name"] == "main"
    assert result1.data["branch2"][0]["name"] == "main"


async def test_multiple_queries(db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe")
    await p1.save(db=db)

    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, firstname="Jane", lastname="Doe")
    await p2.save(db=db)

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
    assert result1.data["firstperson"]["edges"][0]["node"]["firstname"]["value"] == "John"
    assert result1.data["secondperson"]["edges"][0]["node"]["firstname"]["value"] == "Jane"
    assert gql_params.context.related_node_ids == {p1.id, p2.id}


async def test_model_node_interface(db: InfrahubDatabase, default_branch: Branch, car_schema: NodeSchema) -> None:
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    d2 = await Node.init(db=db, schema="TestCar")
    await d2.new(db=db, name="Renaud Clio", nbr_doors=4)
    await d2.save(db=db)

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
    assert sorted([car["node"]["name"]["value"] for car in result.data["TestCar"]["edges"]]) == [
        "Porsche 911",
        "Renaud Clio",
    ]
    assert sorted([car["node"]["nbr_doors"]["value"] for car in result.data["TestCar"]["edges"]]) == [2, 4]
    assert gql_params.context.related_node_ids == {d1.id, d2.id}


async def test_generic_root_with_pagination(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
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


async def test_generic_root_with_filters(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> None:
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
    graphql_registry.clear_cache()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
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


async def test_member_of_groups(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> None:
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1, c2])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
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


async def test_hierarchical_location_parent_filter(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    query = """
    query GetRack {
        LocationRack(parent__name__values: "europe") {
            edges {
                node {
                    id
                    display_label
                    name {
                        value
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
    assert result.data

    nodes = [node["node"]["name"]["value"] for node in result.data["LocationRack"]["edges"]]

    assert result.errors is None
    assert nodes == ["london-r1", "london-r2", "paris-r1", "paris-r2"]


async def test_hierarchical_location_ancestors(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    query = """
    query {
        LocationRack(name__value: "paris-r1") {
            edges {
                node {
                    id
                    display_label
                    ancestors {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
                        }
                    }
                    descendants {
                        edges {
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
    rack = result.data["LocationRack"]["edges"][0]["node"]
    ancestors = rack["ancestors"]["edges"]
    descendants = rack["descendants"]["edges"]
    ancestor_names = [node["node"]["name"]["value"] for node in ancestors]

    assert ancestor_names == ["europe", "paris"]
    assert descendants == []


async def test_hierarchical_location_descendants(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
                        }
                    }
                    ancestors {
                        edges {
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    ancestors = asia["ancestors"]["edges"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing",
        "beijing-r1",
        "beijing-r2",
        "singapore",
        "singapore-r1",
        "singapore-r2",
    ]
    assert ancestors == []


async def test_hierarchical_location_descendants_filters_attr(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants(status__value: "offline") {
                        edges {
                            node {
                                id
                                display_label
                                __typename
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing-r2",
        "singapore-r2",
    ]


async def test_hierarchical_location_descendants_filters_ids(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants(ids: ["%s", "%s", "%s"]) {
                        edges {
                            node {
                                id
                                display_label
                                __typename
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
    """ % (
        hierarchical_location_data["beijing"].id,
        hierarchical_location_data["beijing-r1"].id,
        hierarchical_location_data["singapore-r2"].id,
    )
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing",
        "beijing-r1",
        "singapore-r2",
    ]


async def test_hierarchical_location_include_descendants(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_thing: dict[str, Node]
) -> None:
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    things(include_descendants: true) {
                        count
                        edges {
                            node {
                                id
                                display_label
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    things = asia["things"]["edges"]
    things_names = [node["node"]["name"]["value"] for node in things]

    assert things_names == [
        "thing-asia",
        "thing-beijing",
        "thing-beijing-r1",
        "thing-beijing-r2",
        "thing-singapore",
        "thing-singapore-r1",
        "thing-singapore-r2",
    ]
    assert asia["things"]["count"] == 7


async def test_hierarchical_groups_descendants(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_groups_data: dict[str, Node]
) -> None:
    query = """
    query {
        CoreStandardGroup(name__value: "grp1") {
            edges {
                node {
                    id
                    display_label
                    members(include_descendants: true) {
                        count
                        edges {
                            node {
                                id
                                display_label
                                __typename
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
    grp1 = result.data["CoreStandardGroup"]["edges"][0]["node"]
    members = grp1["members"]["edges"]
    members_ids = [node["node"]["id"] for node in members]

    member_names = [hierarchical_groups_data[member_id].name.value for member_id in members_ids]

    # members returned in order of group names
    assert member_names == [
        # grp1
        "tag-0",
        "tag-1",
        # grp11
        "tag-2",
        "tag-3",
        # grp111
        "tag-6",
        "tag-7",
        # grp112
        "tag-8",
        "tag-9",
        # grp12
        "tag-4",
        "tag-5",
        # grp 121
        "tag-10",
        "tag-11",
        # grp 122
        "tag-12",
        "tag-13",
    ]
    assert grp1["members"]["count"] == 14
