import pytest

from infrahub_client.graphql import (
    Mutation,
    Query,
    render_input_block,
    render_query_block,
)


@pytest.fixture
def query_data_no_filter():
    data = {
        "device": {"name": {"value": None}, "description": {"value": None}, "interfaces": {"name": {"value": None}}}
    }

    return data


@pytest.fixture
def query_data_filters():
    data = {
        "device": {
            "@filters": {"name__value": "$name"},
            "name": {"value": None},
            "description": {"value": None},
            "interfaces": {"@filters": {"enabled__value": "$enabled"}, "name": {"value": None}},
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


def test_query_rendering_with_vars(query_data_filters):
    query = Query(query=query_data_filters, variables={"name": str, "enabled": bool})

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


def test_mutation_rendering_with_vars(input_data_01):
    query_data = {"ok": None, "object": {"id": None}}
    variables = {"name": str, "description": str, "number": int}
    query = Mutation(mutation="myobject_create", query=query_data, input_data=input_data_01, variables=variables)

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
