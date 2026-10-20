from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_allocations_reader import AllocationFilters


@dataclass(frozen=True)
class PageBoundCase:
    name: str
    offset: int | None
    limit: int | None


ACCEPTED_PAGE_BOUND_CASES = [
    PageBoundCase(name="no-page-bounds", offset=None, limit=None),
    PageBoundCase(name="zero-offset-and-limit", offset=0, limit=0),
    PageBoundCase(name="positive-offset-and-limit", offset=5, limit=20),
]


@dataclass(frozen=True)
class RefusedPageBoundCase:
    name: str
    offset: int | None
    limit: int | None
    message: str


REFUSED_PAGE_BOUND_CASES = [
    RefusedPageBoundCase(name="negative-offset", offset=-1, limit=None, message="offset must be 0 or greater"),
    RefusedPageBoundCase(name="negative-limit", offset=None, limit=-1, message="limit must be 0 or greater"),
]


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in ACCEPTED_PAGE_BOUND_CASES])
def test_page_bounds_of_zero_or_more_are_accepted(test_case: PageBoundCase) -> None:
    filters = AllocationFilters(offset=test_case.offset, limit=test_case.limit)

    assert (filters.offset, filters.limit) == (test_case.offset, test_case.limit)


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in REFUSED_PAGE_BOUND_CASES])
def test_a_negative_page_bound_is_refused(test_case: RefusedPageBoundCase) -> None:
    with pytest.raises(ValidationError, match=f"^{re.escape(test_case.message)}$"):
        AllocationFilters(offset=test_case.offset, limit=test_case.limit)
