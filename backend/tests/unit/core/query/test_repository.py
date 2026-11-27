from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

from infrahub.core.query.repository import RepositoryBranchAttributesQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass
class PagingCase:
    name: str
    kwargs: dict[str, Any]
    expected_message: str


def _build(**kwargs: Any) -> RepositoryBranchAttributesQuery:
    return RepositoryBranchAttributesQuery(
        repository_ids=kwargs.pop("repository_ids", ["repository-1"]),
        branch_names=kwargs.pop("branch_names", ["main"]),
        attribute_names=kwargs.pop("attribute_names", ["commit"]),
        default_branch_name="main",
        global_branch_name="-global-",
        **kwargs,
    )


@pytest.mark.parametrize(
    "case",
    [
        PagingCase(
            name="limit",
            kwargs={"limit": 5},
            expected_message="limit not supported: the read returns every matching row",
        ),
        PagingCase(
            name="offset",
            kwargs={"offset": 10},
            expected_message="offset not supported: the read returns every matching row",
        ),
        PagingCase(
            name="limit_and_offset",
            kwargs={"limit": 5, "offset": 10},
            expected_message="limit, offset not supported: the read returns every matching row",
        ),
    ],
    ids=lambda case: case.name,
)
def test_paging_arguments_are_rejected(case: PagingCase) -> None:
    with pytest.raises(ValueError, match=rf"^{case.expected_message}$"):
        _build(**case.kwargs)


async def test_paging_arguments_left_unset_are_accepted() -> None:
    # The statement is built without reading the database, so the connection is never used.
    query = await RepositoryBranchAttributesQuery.init(
        db=cast("InfrahubDatabase", None),
        repository_ids=["repository-1"],
        branch_names=["main", "branch-1"],
        attribute_names=["commit"],
        default_branch_name="main",
        global_branch_name="-global-",
    )

    assert query.limit is None
    assert query.offset is None
