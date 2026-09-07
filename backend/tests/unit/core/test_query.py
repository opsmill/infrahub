import pytest

from infrahub.core.query import Query, QueryType


class PagedQuery(Query):
    name = "paged-query"
    type = QueryType.READ

    def __init__(self) -> None:
        super().__init__()
        self.add_to_query("MATCH (n:Node)")
        self.return_labels = ["n"]


class UnpagedQuery(PagedQuery):
    insert_limit = False


@pytest.fixture
def paged_query() -> PagedQuery:
    return PagedQuery()


def test_pagination_clauses_are_bound_as_parameters(paged_query: PagedQuery) -> None:
    text = paged_query.get_query(limit=2, offset=5)

    assert text.endswith("SKIP $query_offset\nLIMIT $query_limit")
    assert paged_query.params["query_offset"] == 5
    assert paged_query.params["query_limit"] == 2


def test_every_page_of_a_query_shares_one_text(paged_query: PagedQuery) -> None:
    first_page = paged_query.get_query(limit=100, offset=100)
    second_page = paged_query.get_query(limit=100, offset=200)

    assert first_page == second_page
    assert paged_query.params["query_offset"] == 200


def test_first_page_has_no_skip_clause(paged_query: PagedQuery) -> None:
    text = paged_query.get_query(limit=100, offset=0)

    assert "SKIP" not in text
    assert "query_offset" not in paged_query.params
    assert text.endswith("LIMIT $query_limit")


def test_query_rendering_its_own_bounds_gets_no_clauses_or_parameters() -> None:
    query = UnpagedQuery()

    text = query.get_query(limit=2, offset=5)

    assert "SKIP" not in text
    assert "LIMIT" not in text
    assert "query_limit" not in query.params
    assert "query_offset" not in query.params


def test_inline_rendering_substitutes_the_bounds(paged_query: PagedQuery) -> None:
    text = paged_query.get_query(var=True, inline=True, limit=2, offset=5)

    assert text.endswith("SKIP 5\nLIMIT 2")
