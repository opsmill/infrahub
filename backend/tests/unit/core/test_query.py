import pendulum
import pytest

from infrahub.core.query import (
    Query,
    QueryNode,
    QueryRel,
    QueryRelDirection,
    QueryResult,
    cleanup_return_labels,
    sort_results_by_time,
)
from infrahub.database import InfrahubDatabase


class Query01(Query):
    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.order_by = ["at.name", "r2.from"]

        query = """
        MATCH (n) WHERE n.uuid = $uuid
        MATCH (n)-[r1]-(at:Attribute)-[r2]-(av)
        """

        self.return_labels = ["n", "at", "av", "r1", "r2"]
        self.params["uuid"] = "5ffa45d4"

        self.add_to_query(query)


def test_cleanup_return_labels():
    assert cleanup_return_labels(["r", "n", "l"]) == ["r", "n", "l"]
    assert cleanup_return_labels(["r.uuid", "n", "l"]) == ["r.uuid", "n", "l"]
    assert cleanup_return_labels(["ID(r) as  myid", "n", "l"]) == ["myid", "n", "l"]


async def test_query_base(db: InfrahubDatabase):
    query = await Query01.init(db=db)
    expected_query = "MATCH (n) WHERE n.uuid = $uuid\nMATCH (n)-[r1]-(at:Attribute)-[r2]-(av)\nRETURN n,at,av,r1,r2\nORDER BY at.name,r2.from"

    assert query.get_query() == expected_query


async def test_insert_variables_in_query(db: InfrahubDatabase, simple_dataset_01):
    params = {
        "mystring": "5ffa45d4",
        "mylist1": ["1", "2", "3"],
        "mylist2": [1, 2, 3],
        "myint": 198,
    }

    query_lines = [
        "MATCH (n1) WHERE n1.uuid = $mystring",
        "MATCH (n2) WHERE n2.uuid in $mylist1",
        "MATCH (n3) WHERE n3.uuid in $mylist2",
        "MATCH (n4) WHERE n4.uuid in $myint",
    ]

    expected_query_lines = [
        'MATCH (n1) WHERE n1.uuid = "5ffa45d4"',
        "MATCH (n2) WHERE n2.uuid in ['1', '2', '3']",
        "MATCH (n3) WHERE n3.uuid in [1, 2, 3]",
        "MATCH (n4) WHERE n4.uuid in 198",
    ]

    result = Query.insert_variables_in_query(query="\n".join(query_lines), variables=params)
    assert result == "\n".join(expected_query_lines)


async def test_query_results(db: InfrahubDatabase, simple_dataset_01):
    query = await Query01.init(db=db)

    assert query.has_been_executed is False
    await query.execute(db=db)

    assert query.has_been_executed is True

    assert query.num_of_results == 3
    assert query.results[0].get("at") is not None


async def test_query_results_limit_offset(db: InfrahubDatabase, simple_dataset_01):
    query = await Query01.init(db=db, limit=2, offset=1)
    await query.execute(db=db)
    assert query.num_of_results == 2
    expected_values = [result.get("av").get("value") for result in query.results]
    assert expected_values == ["accord", 5]

    query = await Query01.init(db=db, limit=2)
    await query.execute(db=db)
    assert query.num_of_results == 2
    expected_values = [result.get("av").get("value") for result in query.results]
    assert set(expected_values) == {"accord", "volt"}

    query = await Query01.init(db=db, offset=2)
    await query.execute(db=db)
    assert query.num_of_results == 1
    expected_values = [result.get("av").get("value") for result in query.results]
    assert expected_values == [5]


async def test_query_async(db: InfrahubDatabase, simple_dataset_01):
    query = await Query01.init(db=db)

    assert query.has_been_executed is False
    await query.execute(db=db)

    assert query.has_been_executed is True

    assert query.num_of_results == 3
    assert query.results[0].get("at") is not None


async def test_query_count(db: InfrahubDatabase, simple_dataset_01):
    query = await Query01.init(db=db)
    assert await query.count(db=db) == 3


async def test_query_result_getters(neo4j_factory):
    time0 = pendulum.now(tz="UTC")

    n1 = neo4j_factory.hydrate_node(111, {"Car"}, {"uuid": "n1"}, "111")
    n2 = neo4j_factory.hydrate_node(222, {"AttributeValue"}, {"uuid": "n1a1", "name": "name"}, "222")
    r1 = neo4j_factory.hydrate_relationship(
        1112221,
        111,
        222,
        "HAS_ATTRIBUTE",
        {
            "branch": "main",
            "from": time0.subtract(seconds=60).to_iso8601_string(),
            "to": time0.subtract(seconds=30).to_iso8601_string(),
            "status": "active",
        },
    )
    r2 = neo4j_factory.hydrate_relationship(
        1112222,
        111,
        222,
        "HAS_ATTRIBUTE",
        {"branch": "main", "from": time0.subtract(seconds=30).to_iso8601_string(), "to": None, "status": "active"},
    )

    qr = QueryResult(
        data=[n1, r1, r2, n2],
        labels=[
            "n1",
            "r1",
            "r2",
            "n2",
        ],
    )
    assert list(qr.get_rels()) == [r1, r2]
    assert list(qr.get_nodes()) == [n1, n2]
    assert qr.get("n1") == n1
    assert qr.get("r1") == r1
    assert qr.get("r2") == r2

    with pytest.raises(ValueError):
        qr.get("r3")


async def test_sort_results_by_time(neo4j_factory):
    time0 = pendulum.now(tz="UTC")

    n1 = neo4j_factory.hydrate_node(111, {"Car"}, {"uuid": "n1"}, "111")
    n2 = neo4j_factory.hydrate_node(222, {"AttributeValue"}, {"uuid": "n1a1", "name": "name"}, "222")
    r1 = neo4j_factory.hydrate_relationship(
        1112221,
        111,
        222,
        "HAS_ATTRIBUTE",
        {
            "branch": "main",
            "from": time0.subtract(seconds=60).to_iso8601_string(),
            "to": time0.subtract(seconds=30).to_iso8601_string(),
            "status": "active",
        },
    )
    r2 = neo4j_factory.hydrate_relationship(
        1112222,
        111,
        222,
        "HAS_ATTRIBUTE",
        {"branch": "main", "from": time0.subtract(seconds=30).to_iso8601_string(), "to": None, "status": "active"},
    )
    r3 = neo4j_factory.hydrate_relationship(
        1112223,
        111,
        222,
        "HAS_ATTRIBUTE",
        {
            "branch": "main",
            "from": time0.subtract(seconds=90).to_iso8601_string(),
            "to": time0.subtract(seconds=60).to_iso8601_string(),
            "status": "active",
        },
    )

    qr1 = QueryResult(data=[n1, n2, r1], labels=["n1", "n2", "r"])
    qr2 = QueryResult(data=[n1, n2, r2], labels=["n1", "n2", "r"])
    qr3 = QueryResult(data=[n1, n2, r3], labels=["n1", "n2", "r"])

    results = sort_results_by_time(results=[qr1, qr2, qr3], rel_label="r")
    assert list(results) == [qr3, qr1, qr2]

    results = sort_results_by_time(results=[qr3, qr2, qr1], rel_label="r")
    assert list(results) == [qr3, qr1, qr2]


def test_query_node():
    assert str(QueryNode()) == "()"
    assert str(QueryNode(name="n")) == "(n)"
    assert str(QueryNode(name="n", labels=["MyObject"])) == "(n:MyObject)"
    assert str(QueryNode(labels=["MyObject"])) == "(:MyObject)"
    assert str(QueryNode(name="n", labels=["MyObject", "OtherClass"])) == "(n:MyObject:OtherClass)"
    assert str(QueryNode(name="n", labels=["MyObject"], params={"name": "john"})) == '(n:MyObject { name: "john" })'
    assert str(QueryNode(name="n", labels=["MyObject"], params={"name": "$myvar"})) == "(n:MyObject { name: $myvar })"


def test_query_rel():
    assert str(QueryRel()) == "-[]-"
    assert str(QueryRel(name="r2")) == "-[r2]-"
    assert str(QueryRel(name="r2", direction=QueryRelDirection.INBOUND)) == "<-[r2]-"
    assert str(QueryRel(name="r2", direction=QueryRelDirection.OUTBOUND)) == "-[r2]->"
    assert str(QueryRel(name="r2", labels=["HAS_VALUE"])) == "-[r2:HAS_VALUE]-"
    assert str(QueryRel(labels=["HAS_VALUE"])) == "-[:HAS_VALUE]-"
    assert str(QueryRel(name="r2", labels=["HAS_VALUE", "IS_RELATED"])) == "-[r2:HAS_VALUE:IS_RELATED]-"
    assert (
        str(QueryRel(name="r2", labels=["HAS_VALUE"], params={"name": "john"})) == '-[r2:HAS_VALUE { name: "john" }]-'
    )
    assert str(QueryRel(labels=["HAS_VALUE"], params={"name": "john"})) == '-[:HAS_VALUE { name: "john" }]-'
    assert (
        str(QueryRel(labels=["HAS_VALUE"], params={"name": "$myvar"}, direction=QueryRelDirection.OUTBOUND))
        == "-[:HAS_VALUE { name: $myvar }]->"
    )
    assert (
        str(QueryRel(labels=["HAS_VALUE"], direction=QueryRelDirection.OUTBOUND, length_max=3))
        == "-[:HAS_VALUE*1..3]->"
    )
