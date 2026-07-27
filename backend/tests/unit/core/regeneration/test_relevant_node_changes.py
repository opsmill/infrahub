from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.regeneration.predicates import relevant_node_changes
from tests.helpers.diff_summary import node_diff, node_diff_element

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff, NodeDiffElement

BRANCH = "feature/test"


def _node_diff(
    node_id: str, kind: str, field_names: list[str], *, branch: str = BRANCH, action: str = "UPDATED"
) -> NodeDiff:
    """Build an attribute-only diff entry with the raw shape the diff summary emits.

    `action` is the uppercase GraphQL enum name and is shared by the generated elements. Cases
    needing a relationship element type, or elements whose actions differ from the node's, build
    their entry through the shared helper directly.
    """
    return node_diff(
        node_id=node_id, kind=kind, branch=branch, display_label="", field_names=field_names, action=action
    )


def _relationship_diff(node_id: str, kind: str, field_names: list[str], *, element_type: str) -> NodeDiff:
    """Build a diff entry whose elements are relationship flips rather than attribute changes."""
    return node_diff(
        node_id=node_id, kind=kind, branch=BRANCH, display_label="", field_names=field_names, element_type=element_type
    )


def _mixed_element_diff(node_id: str, kind: str, elements: list[NodeDiffElement]) -> NodeDiff:
    """Build a changed diff entry whose elements carry their own, differing actions."""
    return node_diff(node_id=node_id, kind=kind, branch=BRANCH, display_label="", elements=elements)


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
        diff_summary=[_relationship_diff("dev1", "TestDevice", ["tags"], element_type="RELATIONSHIP_MANY")],
        readable_fields_by_kind={"TestDevice": {"name", "tags"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="unread_relationship_flip_is_excluded",
        diff_summary=[_relationship_diff("dev1", "TestDevice", ["tags"], element_type="RELATIONSHIP_MANY")],
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
        name="unchanged_node_is_excluded",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"], action="UNCHANGED")],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="removed_node_is_included",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"], action="REMOVED")],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="added_node_is_included",
        diff_summary=[_node_diff("dev1", "TestDevice", ["name"], action="ADDED")],
        readable_fields_by_kind={"TestDevice": {"name"}},
        expected_ids=["dev1"],
    ),
    RelevantChangeCase(
        name="unchanged_element_on_a_changed_node_is_ignored",
        diff_summary=[
            _mixed_element_diff(
                "dev1",
                "TestDevice",
                elements=[
                    node_diff_element(name="description", action="UPDATED"),
                    node_diff_element(name="parent", action="UNCHANGED", element_type="RELATIONSHIP_ONE"),
                ],
            )
        ],
        readable_fields_by_kind={"TestDevice": {"parent"}},
        expected_ids=[],
    ),
    RelevantChangeCase(
        name="changed_element_beside_an_unchanged_one_is_included",
        diff_summary=[
            _mixed_element_diff(
                "dev1",
                "TestDevice",
                elements=[
                    node_diff_element(name="name", action="UPDATED"),
                    node_diff_element(name="parent", action="UNCHANGED", element_type="RELATIONSHIP_ONE"),
                ],
            )
        ],
        readable_fields_by_kind={"TestDevice": {"name", "parent"}},
        expected_ids=["dev1"],
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
