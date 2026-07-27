from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.regeneration.impact_classifier import QueryImpactClassifier
from infrahub.core.regeneration.models import ImpactScope
from tests.helpers.diff_summary import node_diff

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

BRANCH = "feature/regen"

# A query rooted on the device that also reads a field off each of its interfaces. The interface is
# therefore readable but never a root kind, which is what separates the two narrowing outcomes.
ROOT_KINDS = {"TestDevice"}
READABLE_FIELDS = {"TestDevice": {"name", "interfaces"}, "TestInterface": {"description"}}


@dataclass(frozen=True, kw_only=True)
class AssessCase:
    name: str
    only_has_unique_targets: bool
    diff_summary: list[NodeDiff]
    expected_scope: ImpactScope
    expected_node_ids: list[str] = field(default_factory=list)
    root_kinds: set[str] = field(default_factory=lambda: set(ROOT_KINDS))
    readable_fields_by_kind: dict[str, set[str]] = field(default_factory=lambda: dict(READABLE_FIELDS))


ASSESS_CASES = [
    AssessCase(
        name="unique_targets_root_change_narrows_to_that_node",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected_scope=ImpactScope.SPECIFIC,
        expected_node_ids=["dev1"],
    ),
    AssessCase(
        name="unique_targets_related_change_widens",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"])],
        expected_scope=ImpactScope.ALL,
    ),
    AssessCase(
        name="unique_targets_root_and_related_change_widens",
        only_has_unique_targets=True,
        diff_summary=[
            node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"]),
            node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"]),
        ],
        expected_scope=ImpactScope.ALL,
    ),
    AssessCase(
        name="unique_targets_unread_field_narrows_to_nothing",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["name"])],
        expected_scope=ImpactScope.SPECIFIC,
    ),
    AssessCase(
        name="unique_targets_concrete_kind_behind_generic_root_narrows",
        only_has_unique_targets=True,
        diff_summary=[node_diff(node_id="car1", kind="TestElectricCar", branch=BRANCH, field_names=["name"])],
        expected_scope=ImpactScope.SPECIFIC,
        expected_node_ids=["car1"],
        root_kinds={"TestCar", "TestElectricCar", "TestGazCar"},
        readable_fields_by_kind={"TestCar": {"name"}, "TestElectricCar": {"name"}, "TestGazCar": {"name"}},
    ),
    AssessCase(
        name="without_unique_targets_relevant_change_widens",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["name"])],
        expected_scope=ImpactScope.ALL,
    ),
    AssessCase(
        name="without_unique_targets_related_change_widens",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="intf1", kind="TestInterface", branch=BRANCH, field_names=["description"])],
        expected_scope=ImpactScope.ALL,
    ),
    AssessCase(
        name="without_unique_targets_unread_field_selects_nothing",
        only_has_unique_targets=False,
        diff_summary=[node_diff(node_id="dev1", kind="TestDevice", branch=BRANCH, field_names=["description"])],
        expected_scope=ImpactScope.NONE,
    ),
    AssessCase(
        name="without_unique_targets_empty_diff_selects_nothing",
        only_has_unique_targets=False,
        diff_summary=[],
        expected_scope=ImpactScope.NONE,
    ),
    AssessCase(
        name="change_on_another_branch_is_ignored",
        only_has_unique_targets=True,
        diff_summary=[
            node_diff(node_id="intf1", kind="TestInterface", branch="other/branch", field_names=["description"])
        ],
        expected_scope=ImpactScope.SPECIFIC,
    ),
]


@pytest.mark.parametrize("case", ASSESS_CASES, ids=lambda case: case.name)
def test_assess(case: AssessCase) -> None:
    classifier = QueryImpactClassifier(
        query_branch=BRANCH,
        only_has_unique_targets=case.only_has_unique_targets,
        root_kinds=case.root_kinds,
        readable_fields_by_kind=case.readable_fields_by_kind,
    )

    assessment = classifier.assess(diff_summary=case.diff_summary)

    assert assessment.scope == case.expected_scope
    assert assessment.changed_node_ids == case.expected_node_ids
