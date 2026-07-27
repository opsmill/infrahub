from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.regeneration.predicates import relevant_node_changes
from tests.helpers.diff_summary import node_diff

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

BRANCH = "feature/test"


def _node_diff(
    node_id: str,
    kind: str,
    field_names: list[str],
    *,
    branch: str = BRANCH,
    element_type: str = "ATTRIBUTE",
) -> NodeDiff:
    """Build a diff entry with the raw shape the diff summary emits.

    `element_type` accepts the raw value (e.g. "RELATIONSHIP_MANY") so a relationship endpoint
    flip can be reproduced exactly as it appears in production data.
    """
    return node_diff(
        node_id=node_id,
        kind=kind,
        branch=branch,
        display_label="",
        field_names=field_names,
        element_type=element_type,
    )


@dataclass
class RelevantChangeCase:
    name: str
    diff_summary: list[NodeDiff]
    readable_fields_by_kind: dict[str, set[str]]
    expected_ids: list[str]
    source_branch: str = BRANCH


RELEVANT_CHANGE_CASES = [
    RelevantChangeCase(
        name="attribute_read_field_changed_is_included",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"])],
        readable_fields_by_kind={"TestDevice": {"name", "color"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="attribute_unread_field_changed_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", ["description"])],
        readable_fields_by_kind={"TestDevice": {"name", "color"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="kind_not_read_is_excluded",
        diff_summary=[_node_diff("tag1", "BuiltinTag", ["name"])],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="kind_with_no_readable_fields_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"])],
        readable_fields_by_kind={"TestDevice": set()},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="read_relationship_flip_is_included",
        diff_summary=[_node_diff("dev1", "TestDevice", ["tags"], element_type="RELATIONSHIP_MANY")],
        readable_fields_by_kind={"TestDevice": {"name", "tags"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="unread_relationship_flip_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", ["tags"], element_type="RELATIONSHIP_MANY")],
        readable_fields_by_kind={"TestDevice": {"name", "color"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="change_on_other_branch_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"], branch="some/other-branch")],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="node_with_one_read_and_one_unread_field_is_included",
        diff_summary=[_node_diff("dev1", "TestDevice", ["description", "name"])],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="empty_diff_summary_returns_nothing",
        diff_summary=[],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="node_without_elements_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", [])],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="mixed_nodes_returns_only_relevant",
        diff_summary=[
            _node_diff("dev1", "TestDevice", ["name"]),
            _node_diff("dev2", "TestDevice", ["description"]),
            _node_diff("dev3", "TestDevice", ["color"]),
        ],
        readable_fields_by_kind={"TestDevice": {"name", "color"}},
        expected_ids=["dev1", "dev3"],
    ),
]


@pytest.mark.parametrize("case", RELEVANT_CHANGE_CASES, ids=lambda case: case.name)
def test_relevant_node_changes(case: RelevantChangeCase) -> None:
    result = relevant_node_changes(
        diff_summary=case.diff_summary,
        query_branch=case.source_branch,
        readable_fields_by_kind=case.readable_fields_by_kind,
    )
    assert sorted(result) == case.expected_ids
