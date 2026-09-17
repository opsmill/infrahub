from typing import Any

from infrahub.core.query import QueryResult
from infrahub.core.query.diff import DiffCountChanges
from infrahub.core.timestamp import Timestamp


def build_query(branch_names: list[str], rows: list[tuple[str, int]]) -> DiffCountChanges:
    query = DiffCountChanges(branch_names=branch_names, diff_from=Timestamp(), diff_to=Timestamp())
    # A row is typed as list[Any] because QueryResult.data is annotated for graph entities, while
    # this query projects the scalars `branch_name` and `count(*)`.
    data: list[list[Any]] = [[branch_name, num_changes] for branch_name, num_changes in rows]
    query.results = [QueryResult(data=row, labels=["branch_name", "num_changes"]) for row in data]
    return query


def test_each_returned_row_is_mapped_to_its_branch() -> None:
    query = build_query(branch_names=["main", "branch2"], rows=[("main", 3), ("branch2", 7)])

    assert query.get_num_changes_by_branch() == {"main": 3, "branch2": 7}


def test_a_branch_without_a_row_counts_as_zero() -> None:
    query = build_query(branch_names=["main", "untouched"], rows=[("main", 3)])

    assert query.get_num_changes_by_branch() == {"main": 3, "untouched": 0}


def test_a_row_for_an_unrequested_branch_is_still_reported() -> None:
    query = build_query(branch_names=["main"], rows=[("main", 3), ("other", 1)])

    assert query.get_num_changes_by_branch() == {"main": 3, "other": 1}


def test_no_rows_means_every_branch_counts_as_zero() -> None:
    query = build_query(branch_names=["main", "branch2"], rows=[])

    assert query.get_num_changes_by_branch() == {"main": 0, "branch2": 0}
