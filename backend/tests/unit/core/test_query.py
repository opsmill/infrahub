import pytest

from infrahub.core.query import Query, QueryType


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


def test_first_page_has_no_skip_clause(paged_query: PagedQuery) -> None:
    rendered = paged_query.render(limit=100, offset=0)

    assert "SKIP" not in rendered.text
    assert "query_offset" not in rendered.params
    assert rendered.text.endswith("LIMIT $query_limit")


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
