import pytest
from neo4j import Record
from neo4j._codec.hydration.bolt.v1.hydration_handler import _GraphHydrator
from neo4j.graph import Node as Neo4jNode
from neo4j.graph import Path as Neo4jPath
from neo4j.graph import Relationship as Neo4jRelationship

from infrahub.core.query import CypherValue, Query, QueryResult, QueryType


class PagedQuery(Query):
    name = "paged-query"
    type = QueryType.READ

    def __init__(self) -> None:
        super().__init__()
        self.add_to_query("MATCH (n:Node) WHERE n.uuid = $uuid")
        self.params["uuid"] = "5ffa45d4"
        self.return_labels = ["n"]


class UnpagedQuery(PagedQuery):
    insert_limit = False


@pytest.fixture
def paged_query() -> PagedQuery:
    return PagedQuery()


def test_render_binds_the_page_bounds_as_parameters(paged_query: PagedQuery) -> None:
    rendered = paged_query.render(limit=2, offset=5)

    assert rendered.text.endswith("SKIP $query_offset\nLIMIT $query_limit")
    assert rendered.params == {"uuid": "5ffa45d4", "query_offset": 5, "query_limit": 2}


def test_rendering_leaves_the_query_parameters_untouched(paged_query: PagedQuery) -> None:
    paged_query.render(limit=2, offset=5)
    paged_query.get_query(limit=2, offset=5)

    assert paged_query.params == {"uuid": "5ffa45d4"}


def test_every_page_of_a_query_shares_one_text(paged_query: PagedQuery) -> None:
    first_page = paged_query.render(limit=100, offset=100)
    second_page = paged_query.render(limit=100, offset=200)

    assert first_page.text == second_page.text
    assert first_page.params["query_offset"] == 100
    assert second_page.params["query_offset"] == 200


def test_first_page_shares_the_text_of_the_pages_after_it(paged_query: PagedQuery) -> None:
    first_page = paged_query.render(limit=100, offset=0)
    second_page = paged_query.render(limit=100, offset=100)

    assert first_page.text == second_page.text
    assert first_page.params["query_offset"] == 0


def test_zero_limit_is_no_bound(paged_query: PagedQuery) -> None:
    rendered = paged_query.render(limit=0, offset=2)

    assert rendered.text.endswith("SKIP $query_offset")
    assert "LIMIT" not in rendered.text
    assert rendered.params == {"uuid": "5ffa45d4", "query_offset": 2}


def test_unset_bounds_render_no_clauses(paged_query: PagedQuery) -> None:
    rendered = paged_query.render()

    assert "SKIP" not in rendered.text
    assert "LIMIT" not in rendered.text
    assert rendered.params == {"uuid": "5ffa45d4"}


def test_query_rendering_its_own_bounds_gets_no_clauses_or_parameters() -> None:
    rendered = UnpagedQuery().render(limit=2, offset=5)

    assert "SKIP" not in rendered.text
    assert "LIMIT" not in rendered.text
    assert rendered.params == {"uuid": "5ffa45d4"}


def test_inline_rendering_substitutes_the_bounds(paged_query: PagedQuery) -> None:
    text = paged_query.get_query(var=True, inline=True, limit=2, offset=5)

    assert text.endswith('WHERE n.uuid = "5ffa45d4"\nRETURN n\nSKIP 5\nLIMIT 2')


def test_shell_rendering_lists_the_bounds_with_the_parameters(paged_query: PagedQuery) -> None:
    text = paged_query.get_query(var=True, limit=2, offset=5)

    assert text.startswith('\n:params { uuid: "5ffa45d4", query_offset: 5, query_limit: 2 }\n\n')


def build_result(**columns: CypherValue) -> QueryResult:
    return QueryResult(data=Record(columns.items()), labels=list(columns))


@pytest.fixture
def graph() -> _GraphHydrator:
    return _GraphHydrator()


@pytest.fixture
def device(graph: _GraphHydrator) -> Neo4jNode:
    return graph.hydrate_node(
        id_=901, labels={"Node", "TestDevice"}, properties={"name": "spine1"}, element_id="4:query-result:901"
    )


@pytest.fixture
def interface(graph: _GraphHydrator) -> Neo4jNode:
    return graph.hydrate_node(
        id_=902, labels={"Node", "TestInterface"}, properties={"name": "Ethernet1"}, element_id="4:query-result:902"
    )


@pytest.fixture
def is_related(graph: _GraphHydrator, device: Neo4jNode, interface: Neo4jNode) -> Neo4jRelationship:
    return graph.hydrate_relationship(
        id_=903,
        n0_id=901,
        n1_id=902,
        type_="IS_RELATED",
        properties={"branch": "main", "status": "active"},
        element_id="5:query-result:903",
        n0_element_id=device.element_id,
        n1_element_id=interface.element_id,
    )


@pytest.fixture
def path(device: Neo4jNode, is_related: Neo4jRelationship) -> Neo4jPath:
    return Neo4jPath(device, is_related)


def test_optional_node_reads_a_node_column(device: Neo4jNode) -> None:
    assert build_result(owner=device).get_optional_node(label="owner") is device


def test_optional_node_reads_a_null_column_as_none() -> None:
    assert build_result(owner=None).get_optional_node(label="owner") is None


def test_optional_node_rejects_a_relationship_column(is_related: Neo4jRelationship) -> None:
    with pytest.raises(ValueError, match=r"^owner is not a Node$"):
        build_result(owner=is_related).get_optional_node(label="owner")


def test_list_reads_a_list_column() -> None:
    result = build_result(attributes=[["description", "spine"], ["profile_priority", 1000]])

    assert result.get_list(label="attributes") == [["description", "spine"], ["profile_priority", 1000]]


def test_list_rejects_a_null_column() -> None:
    with pytest.raises(ValueError, match=r"^attributes is not a list$"):
        build_result(attributes=None).get_list(label="attributes")


def test_node_collection_reads_a_list_of_nodes(device: Neo4jNode, interface: Neo4jNode) -> None:
    assert build_result(peers=[device, interface]).get_node_collection(label="peers") == [device, interface]


def test_node_collection_rejects_a_list_holding_a_scalar(device: Neo4jNode) -> None:
    with pytest.raises(ValueError, match=r"^peers holds a value that is not a Node$"):
        build_result(peers=[device, "spine1"]).get_node_collection(label="peers")


def test_nested_node_collection_keeps_the_nulls_of_optional_matches(device: Neo4jNode, interface: Neo4jNode) -> None:
    result = build_result(diff_attributes=[[device, None, None], [interface, device, None]])

    assert result.get_nested_node_collection(label="diff_attributes") == [
        [device, None, None],
        [interface, device, None],
    ]


def test_nested_node_collection_rejects_a_value_that_is_neither_a_node_nor_null(device: Neo4jNode) -> None:
    with pytest.raises(ValueError, match=r"^diff_attributes holds a value that is neither a Node nor null$"):
        build_result(diff_attributes=[[device, "active"]]).get_nested_node_collection(label="diff_attributes")


def test_nested_node_collection_rejects_an_element_that_is_not_a_list(device: Neo4jNode) -> None:
    with pytest.raises(ValueError, match=r"^diff_attributes is not a list of lists$"):
        build_result(diff_attributes=[device]).get_nested_node_collection(label="diff_attributes")


def test_relationship_collection_reads_a_list_of_relationships(is_related: Neo4jRelationship) -> None:
    assert build_result(rels=[is_related]).get_rel_collection(label="rels") == [is_related]


def test_relationship_collection_rejects_a_list_holding_a_node(
    is_related: Neo4jRelationship, device: Neo4jNode
) -> None:
    with pytest.raises(ValueError, match=r"^rels holds a value that is not a Relationship$"):
        build_result(rels=[is_related, device]).get_rel_collection(label="rels")


def test_paths_skips_the_nulls_of_a_list_column(path: Neo4jPath) -> None:
    assert list(build_result(paths=[path, None]).get_paths(label="paths")) == [path]


def test_paths_rejects_a_null_column() -> None:
    with pytest.raises(ValueError, match=r"^paths is not a list$"):
        list(build_result(paths=None).get_paths(label="paths"))
