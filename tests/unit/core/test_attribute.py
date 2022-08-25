from infrahub.core.attribute import String


def test_string_attr_query_filter(default_branch):

    filters, params, nbr_rels = String.get_query_filter(name="description")
    assert filters == []
    assert params == {}
    assert nbr_rels == 0

    filters, params, nbr_rels = String.get_query_filter(name="description", filters={"value": "test"})
    expected_response = [
        "MATCH (n)-[r1:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r2:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2

    filters, params, nbr_rels = String.get_query_filter(name="description", filters={"value": "test"}, rels_offset=2)
    expected_response = [
        "MATCH (n)-[r3:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r4:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2

    filters, params, nbr_rels = String.get_query_filter(
        name="description", filters={"value": "test"}, include_match=False
    )
    expected_response = [
        "-[r1:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r2:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2
