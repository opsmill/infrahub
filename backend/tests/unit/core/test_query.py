from typing import Any

import pytest
from neo4j import Record
from neo4j.graph import Graph, Path
from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryResult, QueryType


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


NODE_UUID = "1827f6b3-5d4c-4c4a-9d6e-3a8b2f0c7e11"
PEER_UUIDS = ["1827f6b4-0a2e-4b6f-8c1d-5e7f9a0b3c22", "1827f6b4-7f3d-4e8a-b2c5-6d9e0f1a4b33"]


def build_node(uuid: str) -> Neo4jNode:
    return Neo4jNode(Graph(), element_id=f"4:db:{uuid}", id_=0, n_labels=["Node"], properties={"uuid": uuid})


PEERS = [build_node(uuid=peer_uuid) for peer_uuid in PEER_UUIDS]


def build_result(**columns: Any) -> QueryResult:
    labels = list(columns)
    return QueryResult(data=Record(zip(labels, columns.values(), strict=True)), labels=labels)


@pytest.fixture
def result() -> QueryResult:
    return build_result(uuid=NODE_UUID, deleted_at=None, peers=PEERS, nbr_peers="2")


def test_get_returns_scalar_and_null_columns_as_is(result: QueryResult) -> None:
    assert result.get(label="uuid") == NODE_UUID
    assert result.get(label="deleted_at") is None


def test_node_collection_returns_a_list_column_as_is(result: QueryResult) -> None:
    assert result.get_node_collection(label="peers") == PEERS


def test_node_collection_rejects_a_scalar_column(result: QueryResult) -> None:
    with pytest.raises(ValueError, match="uuid is not a collection"):
        result.get_node_collection(label="uuid")


def test_unknown_label_is_rejected(result: QueryResult) -> None:
    with pytest.raises(ValueError, match="peer is not a valid value"):
        result.get(label="peer")


def test_get_as_type_converts_the_column(result: QueryResult) -> None:
    assert result.get_as_type(label="nbr_peers", return_type=int) == 2


def build_path(uuid: str) -> Path:
    return Path(build_node(uuid=uuid))


def test_get_path_returns_a_path_column() -> None:
    path = build_path(uuid=NODE_UUID)
    result = build_result(path=path, uuid=NODE_UUID)

    assert result.get_path(label="path") is path
    with pytest.raises(ValueError, match="uuid is not a Path"):
        result.get_path(label="uuid")


def test_get_paths_yields_only_the_paths_of_a_list_column() -> None:
    paths = [build_path(uuid=peer_uuid) for peer_uuid in PEER_UUIDS]
    result = build_result(paths=[paths[0], None, paths[1]])

    assert list(result.get_paths(label="paths")) == paths
