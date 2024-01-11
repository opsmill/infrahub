from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase


async def test_build_subquery_filter_attribute_text(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
):
    attr_schema = all_attribute_types_schema.get_attribute(name="mystring")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=attr_schema,
        name="name",
        filter_name="value",
        filter_value="myname",
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    expected_query = """
    WITH n
    MATCH path = (n)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av:AttributeValue { value: $filter1_value })
    WHERE all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {"filter1_name": "name", "filter1_value": "myname"}
    assert result_name == "filter1"


async def test_build_subquery_filter_attribute_int(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
):
    attr_schema = all_attribute_types_schema.get_attribute(name="myint")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=attr_schema,
        name="name",
        filter_name="value",
        filter_value=5,
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=2,
    )

    expected_query = """
    WITH n
    MATCH path = (n)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter2_name })-[:HAS_VALUE]-(av:AttributeValue { value: $filter2_value })
    WHERE all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter2
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {"filter2_name": "name", "filter2_value": 5}
    assert result_name == "filter2"


async def test_build_subquery_filter_relationship(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship(name="owner")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=rel_schema,
        name="owner",
        filter_name="name__value",
        filter_value="john",
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    # ruff: noqa: E501
    expected_query = """
    WITH n
    MATCH path = (n)-[r1:IS_RELATED]->(rl:Relationship { name: $filter1_rel_name })-[r2:IS_RELATED]->(peer:Node)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av:AttributeValue { value: $filter1_value })
    WHERE all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {
        "filter1_name": "name",
        "filter1_rel_name": "testcar__testperson",
        "filter1_value": "john",
    }
    assert result_name == "filter1"


async def test_build_subquery_filter_relationship_ids(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship(name="owner")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=rel_schema,
        name="owner",
        filter_name="ids",
        filter_value=["XXXXXX"],
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    # ruff: noqa: E501
    expected_query = """
    WITH n
    MATCH path = (n)-[r1:IS_RELATED]->(rl:Relationship { name: $filter1_rel_name })-[r2:IS_RELATED]->(peer:Node)
    WHERE peer.uuid IN $filter1_peer_ids AND all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {"filter1_peer_ids": ["XXXXXX"], "filter1_rel_name": "testcar__testperson"}
    assert result_name == "filter1"


async def test_build_subquery_order_relationship(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship(name="owner")

    query, params, result_name = await build_subquery_order(
        db=db,
        field=rel_schema,
        name="owner",
        order_by="name__value",
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    expected_query = """
    WITH n
    MATCH path = (n)-[:IS_RELATED]->(:Relationship { name: $order1_rel_name })-[:IS_RELATED]->(:Node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $order1_name })-[:HAS_VALUE]-(last:AttributeValue)
    WHERE all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH last, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN last.value as order1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {"order1_name": "name", "order1_rel_name": "testcar__testperson"}
    assert result_name == "order1"


async def test_build_subquery_filter_attribute_multiple_values(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
):
    attr_schema = all_attribute_types_schema.get_attribute(name="mystring")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=attr_schema,
        name="name",
        filter_name="values",
        filter_value=["myvalue", "myothervalue"],
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    expected_query = """
    WITH n
    MATCH path = (n)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av:AttributeValue)
    WHERE av.value IN $filter1_value AND all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {"filter1_name": "name", "filter1_value": ["myvalue", "myothervalue"]}
    assert result_name == "filter1"


async def test_build_subquery_filter_relationship_multiple_values(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema
):
    car_schema = registry.schema.get(name="TestCar")
    rel_schema = car_schema.get_relationship(name="owner")

    query, params, result_name = await build_subquery_filter(
        db=db,
        field=rel_schema,
        name="owner",
        filter_name="name__values",
        filter_value=["john", "jane"],
        branch_filter="PLACEHOLDER",
        branch=default_branch,
        subquery_idx=1,
    )

    # ruff: noqa: E501
    expected_query = """
    WITH n
    MATCH path = (n)-[r1:IS_RELATED]->(rl:Relationship { name: $filter1_rel_name })-[r2:IS_RELATED]->(peer:Node)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av:AttributeValue)
    WHERE av.value IN $filter1_value AND all(r IN relationships(path) WHERE (PLACEHOLDER))
    WITH n, path, reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level
    RETURN n as filter1
    ORDER BY branch_level DESC
    LIMIT 1
    """
    assert query == expected_query
    assert params == {
        "filter1_name": "name",
        "filter1_rel_name": "testcar__testperson",
        "filter1_value": ["john", "jane"],
    }
    assert result_name == "filter1"
