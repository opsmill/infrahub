from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class SizeCase:
    name: str
    repository_ids: list[str] = field(default_factory=lambda: ["repository-1"])
    branch_names: list[str] = field(default_factory=lambda: ["main"])
    attribute_names: list[str] = field(default_factory=lambda: ["commit"])
    expected_limit: int = 1


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

    assert query.limit == 2


@pytest.mark.parametrize(
    "case",
    [
        SizeCase(name="single_triple", expected_limit=1),
        SizeCase(name="many_branches", branch_names=["main", "branch-1", "branch-2"], expected_limit=3),
        SizeCase(
            name="branches_times_attributes",
            branch_names=["main", "branch-1"],
            attribute_names=["commit", "ref", "sync_status"],
            expected_limit=6,
        ),
        SizeCase(name="no_attributes_selected", attribute_names=[], expected_limit=1),
    ],
    ids=lambda case: case.name,
)
def test_limit_covers_every_row_the_statement_can_produce(case: SizeCase) -> None:
    query = _build(
        repository_ids=case.repository_ids,
        branch_names=case.branch_names,
        attribute_names=case.attribute_names,
    )

    assert query.limit == case.expected_limit
