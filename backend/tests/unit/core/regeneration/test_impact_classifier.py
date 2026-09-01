from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.regeneration.impact_classifier import (
    ChangedNodes,
    EveryTarget,
    ImpactAssessment,
    QueryImpactClassifier,
)
from tests.helpers.diff_summary import node_diff

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

BRANCH = "feature/regen"

# A query rooted on the device that also reads a field off each of its interfaces. The interface is
# therefore readable but reached only by following a relationship, which is what separates the two
# narrowing outcomes.
TRAVERSED_KINDS = {"TestInterface"}
READABLE_FIELDS = {"TestDevice": {"name", "interfaces"}, "TestInterface": {"description"}}


@dataclass(frozen=True, kw_only=True)
class AssessCase:
    name: str
    only_has_unique_targets: bool
    diff_summary: list[NodeDiff]
    expected: ImpactAssessment
    traversed_kinds: set[str] = field(default_factory=lambda: set(TRAVERSED_KINDS))
    readable_fields_by_kind: dict[str, set[str]] = field(default_factory=lambda: dict(READABLE_FIELDS))
    depends_on_everything: bool = False


ASSESS_CASES = [
    AssessCase(
        name="unique_targets_root_change_narrows_to_that_node",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected=ChangedNodes(node_ids=["dev1"]),
    ),
    AssessCase(
        name="unique_targets_related_change_widens",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"])],
        expected=EveryTarget(),
    ),
    AssessCase(
        name="unique_targets_root_and_related_change_widens",
        only_has_unique_targets=True,
        diff_summary=[
            node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"]),
            node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"]),
        ],
        expected=EveryTarget(),
    ),
    AssessCase(
        name="unique_targets_unread_field_narrows_to_nothing",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["name"])],
        expected=ChangedNodes(node_ids=[]),
    ),
    AssessCase(
        name="unique_targets_concrete_kind_behind_generic_root_narrows",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="car1", kind="TestElectricCar", branch=BRANCH, field_names=["name"])],
        expected=ChangedNodes(node_ids=["car1"]),
        traversed_kinds=set(),
        readable_fields_by_kind={"TestCar": {"name"}, "TestElectricCar": {"name"}, "TestGazCar": {"name"}},
    ),
    AssessCase(
        name="unique_targets_kind_read_at_root_and_through_a_relationship_widens",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev2", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected=EveryTarget(),
        traversed_kinds={"TestDevice"},
        readable_fields_by_kind={"TestDevice": {"name", "peers"}},
    ),
    AssessCase(
        name="without_unique_targets_relevant_change_widens",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected=EveryTarget(),
    ),
    AssessCase(
        name="without_unique_targets_related_change_widens",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"])],
        expected=EveryTarget(),
    ),
    AssessCase(
        name="without_unique_targets_unread_field_selects_nothing",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["description"])],
        expected=ChangedNodes(node_ids=[]),
    ),
    AssessCase(
        name="without_unique_targets_empty_diff_selects_nothing",
        only_has_unique_targets=False,
        diff_summary=[],
        expected=ChangedNodes(node_ids=[]),
    ),
    AssessCase(
        name="change_on_another_branch_is_ignored",
        only_has_unique_targets=True,
        diff_summary=[
            node_diff(node_id="intf1", kind="TestInterface", branch="other/branch", field_names=["description"])
        ],
        expected=ChangedNodes(node_ids=[]),
    ),
    # display_label / human_friendly_id are computed: a read records the computed field name, but a
    # change to the backing field that moves the value is reported under the backing field's name.
    # Such a read must be treated as imprecise for its kind -- any change to the kind is relevant --
    # or the reader is left stale.
    AssessCase(
        name="unique_targets_display_label_root_change_narrows_to_that_node",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected=ChangedNodes(node_ids=["dev1"]),
        traversed_kinds=set(),
        readable_fields_by_kind={"TestDevice": {"display_label"}},
    ),
    AssessCase(
        name="unique_targets_display_label_change_on_several_nodes_narrows_to_each",
        only_has_unique_targets=True,
        diff_summary=[
            node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"]),
            node_diff(node_id="dev2", kind="TestDevice", branch=BRANCH, field_names=["name"]),
        ],
        expected=ChangedNodes(node_ids=["dev1", "dev2"]),
        traversed_kinds=set(),
        readable_fields_by_kind={"TestDevice": {"display_label"}},
    ),
    AssessCase(
        name="unique_targets_display_label_read_through_a_relationship_widens",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["name"])],
        readable_fields_by_kind={"TestDevice": {"name"}, "TestInterface": {"display_label"}},
        expected=EveryTarget(),
    ),
    # A query that reads a derived value composed from a peer the read set cannot name cannot be
    # narrowed, so any relevant change widens to every target, and no relevant change selects nothing.
    AssessCase(
        name="depends_on_everything_relevant_change_widens",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        readable_fields_by_kind={"TestDevice": {"display_label"}},
        depends_on_everything=True,
        expected=EveryTarget(),
    ),
    AssessCase(
        name="depends_on_everything_unread_change_selects_nothing",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["description"])],
        readable_fields_by_kind={"TestDevice": {"name"}},
        depends_on_everything=True,
        expected=ChangedNodes(node_ids=[]),
    ),
]


@pytest.mark.parametrize("case", ASSESS_CASES, ids=lambda case: case.name)
def test_assess(case: AssessCase) -> None:
    classifier = QueryImpactClassifier(
        query_branch=BRANCH,
        only_has_unique_targets=case.only_has_unique_targets,
        traversed_kinds=case.traversed_kinds,
        readable_fields_by_kind=case.readable_fields_by_kind,
        depends_on_everything=case.depends_on_everything,
    )

    assessment = classifier.assess(diff_summary=case.diff_summary)

    assert assessment == case.expected
