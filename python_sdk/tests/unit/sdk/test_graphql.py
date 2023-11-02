import pytest

from infrahub_sdk.graphql import Mutation, Query, render_input_block, render_query_block

# pylint: disable=redefined-outer-name


@pytest.fixture
def query_data_no_filter():
    data = {
        "device": {
            "name": {"value": None},
            "description": {"value": None},
            "interfaces": {"name": {"value": None}},
        }
    }

    return data


@pytest.fixture
def query_data_alias():
    data = {
        "device": {
            "name": {"@alias": "new_name", "value": None},
            "description": {"value": {"@alias": "myvalue"}},
            "interfaces": {"@alias": "myinterfaces", "name": {"value": None}},
        }
    }

    return data


@pytest.fixture
def query_data_fragment():
    data = {
        "device": {
            "name": {"value": None},
            "...on Builtin": {
                "description": {"value": None},
                "interfaces": {"name": {"value": None}},
            },
        }
    }

    return data


@pytest.fixture
def query_data_empty_filter():
    data = {
        "device": {
            "@filters": {},
            "name": {"value": None},
            "description": {"value": None},
            "interfaces": {"name": {"value": None}},
        }
    }

    return data


@pytest.fixture
def query_data_filters_01():
    data = {
        "device": {
            "@filters": {"name__value": "$name"},
            "name": {"value": None},
            "description": {"value": None},
            "interfaces": {
                "@filters": {"enabled__value": "$enabled"},
                "name": {"value": None},
            },
        }
    }
    return data


@pytest.fixture
def query_data_filters_02():
    data = {
        "device": {
            "@filters": {"name__value": "myname", "integer__value": 44},
            "name": {"value": None},
            "interfaces": {
                "@filters": {"enabled__value": True},
                "name": {"value": None},
            },
        }
    }
    return data


@pytest.fixture
def input_data_01():
    data = {
        "data": {
            "name": {"value": "$name"},
            "some_number": {"value": 88},
            "some_bool": {"value": True},
            "some_list": {"value": ["value1", 33]},
            "query": {"value": "my_query"},
        }
    }
    return data


def test_render_query_block(query_data_no_filter):
    lines = render_query_block(data=query_data_no_filter)

    expected_lines = [
        "    device {",
        "        name {",
        "            value",
        "        }",
        "        description {",
        "            value",
        "        }",
        "        interfaces {",
        "            name {",
        "                value",
        "            }",
        "        }",
        "    }",
    ]

    assert lines == expected_lines

    # Render the query block with an indentation of 2
    lines = render_query_block(data=query_data_no_filter, offset=2, indentation=2)

    expected_lines = [
        "  device {",
        "    name {",
        "      value",
        "    }",
        "    description {",
        "      value",
        "    }",
        "    interfaces {",
        "      name {",
        "        value",
        "      }",
        "    }",
        "  }",
    ]

    assert lines == expected_lines


def test_render_query_block_alias(query_data_alias):
    lines = render_query_block(data=query_data_alias)

    expected_lines = [
        "    device {",
        "        new_name: name {",
        "            value",
        "        }",
        "        description {",
        "            myvalue: value",
        "        }",
        "        myinterfaces: interfaces {",
        "            name {",
        "                value",
        "            }",
        "        }",
        "    }",
    ]

    assert lines == expected_lines


def test_render_query_block_fragment(query_data_fragment):
    lines = render_query_block(data=query_data_fragment)

    expected_lines = [
        "    device {",
        "        name {",
        "            value",
        "        }",
        "        ...on Builtin {",
        "            description {",
        "                value",
        "            }",
        "            interfaces {",
        "                name {",
        "                    value",
        "                }",
        "            }",
        "        }",
        "    }",
    ]

    assert lines == expected_lines


def test_render_input_block(input_data_01):
    lines = render_input_block(data=input_data_01)

    expected_lines = [
        "    data: {",
        "        name: {",
        "            value: $name",
        "        }",
        "        some_number: {",
        "            value: 88",
        "        }",
        "        some_bool: {",
        "            value: true",
        "        }",
        "        some_list: {",
        "            value: [",
        '                "value1",',
        "                33,",
        "            ]",
        "        }",
        "        query: {",
        '            value: "my_query"',
        "        }",
        "    }",
    ]
    assert lines == expected_lines

    # Render the input block with an indentation of 2
    lines = render_input_block(data=input_data_01, offset=2, indentation=2)

    expected_lines = [
        "  data: {",
        "    name: {",
        "      value: $name",
        "    }",
        "    some_number: {",
        "      value: 88",
        "    }",
        "    some_bool: {",
        "      value: true",
        "    }",
        "    some_list: {",
        "      value: [",
        '        "value1",',
        "        33,",
        "      ]",
        "    }",
        "    query: {",
        '      value: "my_query"',
        "    }",
        "  }",
    ]
    assert lines == expected_lines


def test_query_rendering_no_vars(query_data_no_filter):
    query = Query(query=query_data_no_filter)

    expected_query = """
query {
    device {
        name {
            value
        }
        description {
            value
        }
        interfaces {
            name {
                value
            }
        }
    }
}
"""
    assert query.render_first_line() == "query {"
    assert query.render() == expected_query


def test_query_rendering_empty_filter(query_data_empty_filter):
    query = Query(query=query_data_empty_filter)

    expected_query = """
query {
    device {
        name {
            value
        }
        description {
            value
        }
        interfaces {
            name {
                value
            }
        }
    }
}
"""
    assert query.render_first_line() == "query {"
    assert query.render() == expected_query


def test_query_rendering_with_filters_and_vars(query_data_filters_01):
    query = Query(query=query_data_filters_01, variables={"name": str, "enabled": bool})

    expected_query = """
query ($name: String!, $enabled: Boolean!) {
    device(name__value: $name) {
        name {
            value
        }
        description {
            value
        }
        interfaces(enabled__value: $enabled) {
            name {
                value
            }
        }
    }
}
"""
    assert query.render_first_line() == "query ($name: String!, $enabled: Boolean!) {"
    assert query.render() == expected_query


def test_query_rendering_with_filters(query_data_filters_02):
    query = Query(query=query_data_filters_02)

    expected_query = """
query {
    device(name__value: "myname", integer__value: 44) {
        name {
            value
        }
        interfaces(enabled__value: true) {
            name {
                value
            }
        }
    }
}
"""
    assert query.render() == expected_query


def test_mutation_rendering_no_vars(input_data_01):
    query_data = {"ok": None, "object": {"id": None}}

    query = Mutation(mutation="myobject_create", query=query_data, input_data=input_data_01)

    expected_query = """
mutation {
    myobject_create(
        data: {
            name: {
                value: $name
            }
            some_number: {
                value: 88
            }
            some_bool: {
                value: true
            }
            some_list: {
                value: [
                    "value1",
                    33,
                ]
            }
            query: {
                value: "my_query"
            }
        }
    ){
        ok
        object {
            id
        }
    }
}
"""
    assert query.render_first_line() == "mutation {"
    assert query.render() == expected_query


def test_mutation_rendering_many_relationships():
    query_data = {"ok": None, "object": {"id": None}}
    input_data = {
        "data": {
            "description": {"value": "JFK Airport"},
            "name": {"value": "JFK1"},
            "tags": [
                {"id": "b44c6a7d-3b9c-466a-b6e3-a547b0ecc965"},
                {"id": "c5dffab1-e3f1-4039-9a1e-c0df1705d612"},
            ],
        }
    }

    query = Mutation(mutation="myobject_create", query=query_data, input_data=input_data)

    expected_query = """
mutation {
    myobject_create(
        data: {
            description: {
                value: "JFK Airport"
            }
            name: {
                value: "JFK1"
            }
            tags: [
                {
                    id: "b44c6a7d-3b9c-466a-b6e3-a547b0ecc965"
                },
                {
                    id: "c5dffab1-e3f1-4039-9a1e-c0df1705d612"
                },
            ]
        }
    ){
        ok
        object {
            id
        }
    }
}
"""
    assert query.render_first_line() == "mutation {"
    assert query.render() == expected_query


def test_mutation_rendering_with_vars(input_data_01):
    query_data = {"ok": None, "object": {"id": None}}
    variables = {"name": str, "description": str, "number": int}
    query = Mutation(
        mutation="myobject_create",
        query=query_data,
        input_data=input_data_01,
        variables=variables,
    )

    expected_query = """
mutation ($name: String!, $description: String!, $number: Int!) {
    myobject_create(
        data: {
            name: {
                value: $name
            }
            some_number: {
                value: 88
            }
            some_bool: {
                value: true
            }
            some_list: {
                value: [
                    "value1",
                    33,
                ]
            }
            query: {
                value: "my_query"
            }
        }
    ){
        ok
        object {
            id
        }
    }
}
"""
    assert query.render_first_line() == "mutation ($name: String!, $description: String!, $number: Int!) {"
    assert query.render() == expected_query
