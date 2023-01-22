from graphql import parse

from infrahub.graphql.utils import extract_fields


async def test_extract_fields():

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
             }
        }
    }
    """

    document = parse(query)

    expected_response = {"person": {"name": {"value": None}, "vehicules": {"name": {"value": None}}}}
    assert await extract_fields(document.definitions[0].selection_set) == expected_response


async def test_extract_fields_fragment():

    query = """
        query {
            person {
                name {
                    value
                }
                vehicules {
                    ... on RelatedCar {
                        name {
                            value
                            is_inherited
                        }
                        nbr_doors {
                            value
                        }
                    }
                    ... on RelatedBoat {
                        name {
                            value
                            is_protected
                        }
                        has_sails {
                            value
                        }
                    }
                }
            }
        }
    """

    document = parse(query)

    expected_response = {
        "person": {
            "name": {"value": None},
            "vehicules": {
                "has_sails": {"value": None},
                "name": {"value": None, "is_protected": None, "is_inherited": None},
                "nbr_doors": {"value": None},
            },
        },
    }

    assert await extract_fields(document.definitions[0].selection_set) == expected_response
