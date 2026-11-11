from typing import Any

import pytest

from infrahub import config
from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_all_attributes(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
                ipaddress: { value: "10.3.4.254/24" }
                prefix: { value: "10.3.4.0/24" }
            }
        ){
            ok
            object {
                id
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
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    assert len(result.data["TestAllAttributeTypesCreate"]["object"]["id"]) == 36  # length of an UUID

    objs = await NodeManager.query(db=db, schema="TestAllAttributeTypes")
    obj1 = objs[0]

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False
    assert obj1.ipaddress.value == "10.3.4.254/24"
    assert obj1.ipaddress.is_default is False
    assert obj1.prefix.value == "10.3.4.0/24"
    assert obj1.prefix.is_default is False


async def test_all_attributes_default_value(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_default_types_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
            }
        ){
            ok
            object {
                id
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
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    obj_id = result.data["TestAllAttributeTypesCreate"]["object"]["id"]
    assert len(obj_id) == 36  # length of an UUID

    obj1 = await NodeManager.get_one(db=db, id=obj_id)

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False

    assert obj1.mystring_default.value == "a string"
    assert obj1.mystring_default.is_default is True
    assert obj1.mybool_default.value is False
    assert obj1.mybool_default.is_default is True
    assert obj1.myint_default.value == 10
    assert obj1.myint_default.is_default is True
    assert obj1.mylist_default.value == [10, 11, 12]
    assert obj1.mylist_default.is_default is True

    assert obj1.mystring_none.value is None
    assert obj1.mystring_none.is_default is True
    assert obj1.mybool_none.value is None
    assert obj1.mybool_none.is_default is True
    assert obj1.myint_none.value is None
    assert obj1.myint_none.is_default is True
    assert obj1.mylist_none.value is None
    assert obj1.mylist_none.is_default is True


async def test_create_object_with_flag_property(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", is_protected: true }
                height: { value: 182 }
            }
        ) {
            ok
            object {
                id
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            is_protected
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
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["is_protected"] is True


async def test_create_object_with_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    first_account: Node,
    second_account: Node,
) -> None:
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", source: "%s" }
                height: { value: 182, owner: "%s" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        first_account.id,
        second_account.id,
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            source {
                                id
                                display_label
                            }
                        }
                        height {
                            id
                            owner {
                                id
                                display_label
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
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"]["id"] == first_account.id
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"][
        "display_label"
    ] == await first_account.get_display_label(db=db)
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"]["id"] == second_account.id
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"][
        "display_label"
    ] == await second_account.get_display_label(db=db)


async def test_create_person_not_valid(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {
            name: { value: "John"},
            height: {value: "182"}
        }) {
            ok
            object {
                id
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

    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Expected value of type 'BigInt', found \"182\"."


async def test_create_with_attribute_not_valid(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            color: { value: "#44444444" },
            is_electric: { value: true },
            owner: { id: "John" },
        }) {
            ok
            object {
                id
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

    assert result.errors
    assert len(result.errors) == 1
    assert "#44444444 must have a maximum length of 7 at color" in result.errors[0].message


async def test_create_valid_datetime_success(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "2021-01-01T00:00:00Z"}}) {
            ok
            object {
                id
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
    assert result.data["TestCriticalityCreate"]["ok"] is True
    crit = await NodeManager.get_one(db=db, id=result.data["TestCriticalityCreate"]["object"]["id"])
    assert crit.time.value == "2021-01-01T00:00:00Z"
    assert crit.time.is_default is False
    assert crit.name.value == "HIGH"
    assert crit.level.value == 1


async def test_create_valid_datetime_failure(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "10:1010"}}) {
            ok
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
    assert result.errors
    assert result.errors[0].args[0] == "10:1010 is not a valid DateTime at time"
    assert result.data["TestCriticalityCreate"] is None


# These tests have been moved at the end of the file to avoid colliding with other and breaking them


@pytest.mark.parametrize(
    "graphql_enums_on,enum_value,response_value", [(True, "MANUAL", "MANUAL"), (False, '"manual"', "manual")]
)
async def test_create_simple_object_with_enum(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
    graphql_enums_on: bool,
    enum_value: str,
    response_value: str,
    reset_graphql_schema_between_tests: Any,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = graphql_enums_on
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: %s },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
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
    assert result.data["TestCarCreate"]["ok"] is True
    assert result.data["TestCarCreate"]["object"]["transmission"]["value"] == response_value

    car_id = result.data["TestCarCreate"]["object"]["id"]
    database_car = await NodeManager.get_one(db=db, id=car_id)
    assert database_car.transmission.value.value == "manual"


async def test_create_enum_when_enums_off_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = False
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: MANUAL },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
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

    assert result.errors
    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


async def test_create_string_when_enums_on_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
    reset_graphql_schema_between_tests: Any,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = True
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: "manual" },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
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

    assert result.errors
    assert len(result.errors) == 1
    assert "'TestCarTransmissionValue' cannot represent non-enum value" in result.errors[0].message
