"""Branch scoping of the per-node trigger families.

A branch whose definition differs from the default branch owns its own automation. The
default-branch automation must then skip the events of that branch, or the work runs twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

import pytest

from infrahub.computed_attribute.models import ComputedAttrJinja2TriggerDefinition
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget, ComputedAttributeTriggerNode
from infrahub.display_labels.models import DisplayLabelTriggerDefinition
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.hfid.models import HFIDTriggerDefinition
from infrahub.profiles.models import ProfileRefreshTriggerDefinition
from infrahub.trigger.models import EventTrigger
from infrahub.workflows.catalogue import PROFILE_REFRESH_PROCESS
from tests.helpers.trigger import branches_covered_by

if TYPE_CHECKING:
    from infrahub.trigger.models import TriggerBranchDefinition

DEFAULT_BRANCH = "main"
DIVERGED_BRANCHES = ["branch1", "branch2"]
UNKNOWN_BRANCH = "branch-created-after-setup"
NODE_KIND = "TestCar"
FIELD = "name"

BRANCH_EXCLUSION_BRANCH1 = {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": "!branch1"}
BRANCH_EXCLUSION_BRANCH2 = {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": "!branch2"}


def _covered_branches(triggers_by_scope: dict[str, TriggerBranchDefinition]) -> dict[str, list[str]]:
    return branches_covered_by(
        triggers_by_scope=triggers_by_scope,
        kind=NODE_KIND,
        field=FIELD,
        branch_names=[DEFAULT_BRANCH, *DIVERGED_BRANCHES, UNKNOWN_BRANCH],
    )


def _computed_attribute_target() -> ComputedAttributeTarget:
    return ComputedAttributeTarget(
        kind=NODE_KIND,
        attribute=AttributeSchema(
            name="computed_desc",
            kind="Text",
            read_only=True,
            optional=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"
            ),
        ),
    )


def _jinja2_computed_attribute(branch: str, branches_out_of_scope: list[str]) -> ComputedAttrJinja2TriggerDefinition:
    return ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
        branch=branch,
        computed_attribute=_computed_attribute_target(),
        trigger_node=ComputedAttributeTriggerNode(kind=NODE_KIND, attributes=[FIELD]),
        branches_out_of_scope=branches_out_of_scope,
    )


def _display_label(branch: str, branches_out_of_scope: list[str]) -> DisplayLabelTriggerDefinition:
    return DisplayLabelTriggerDefinition.new(
        branch=branch,
        node_kind=NODE_KIND,
        target_kind=NODE_KIND,
        template_hash="hash01",
        fields=[FIELD],
        branches_out_of_scope=branches_out_of_scope,
    )


def _hfid(branch: str, branches_out_of_scope: list[str]) -> HFIDTriggerDefinition:
    return HFIDTriggerDefinition.new(
        branch=branch,
        node_kind=NODE_KIND,
        target_kind=NODE_KIND,
        hfid_hash="hash01",
        fields=[FIELD],
        branches_out_of_scope=branches_out_of_scope,
    )


def _profile(branch: str, branches_out_of_scope: list[str]) -> ProfileRefreshTriggerDefinition:
    return ProfileRefreshTriggerDefinition.from_profile_schema(
        branch=branch,
        profile_kind=NODE_KIND,
        trigger_fields=[FIELD],
        workflow=PROFILE_REFRESH_PROCESS,
        branches_out_of_scope=branches_out_of_scope,
    )


@dataclass
class BuilderCase:
    name: str
    build: Callable[[str, list[str]], TriggerBranchDefinition]


BUILDER_CASES = [
    BuilderCase(name="computed_attribute_jinja2", build=_jinja2_computed_attribute),
    BuilderCase(name="display_label", build=_display_label),
    BuilderCase(name="hfid", build=_hfid),
    BuilderCase(name="profile_refresh", build=_profile),
]


@pytest.mark.parametrize("case", BUILDER_CASES, ids=lambda case: case.name)
class TestBranchScoping:
    def test_exactly_one_automation_fires_per_branch(self, case: BuilderCase) -> None:
        """Every branch is owned by one automation, including a branch nothing knows about yet."""
        automations = {
            DEFAULT_BRANCH: case.build(DEFAULT_BRANCH, DIVERGED_BRANCHES),
            **{branch: case.build(branch, []) for branch in DIVERGED_BRANCHES},
        }

        assert _covered_branches(automations) == {
            DEFAULT_BRANCH: [DEFAULT_BRANCH],
            "branch1": ["branch1"],
            "branch2": ["branch2"],
            UNKNOWN_BRANCH: [DEFAULT_BRANCH],
        }

    def test_default_automation_excludes_every_diverged_branch(self, case: BuilderCase) -> None:
        trigger = case.build(DEFAULT_BRANCH, DIVERGED_BRANCHES).trigger

        assert "infrahub.branch.name" not in trigger.match
        assert isinstance(trigger.match_related, list)
        assert trigger.match_related[1:] == [BRANCH_EXCLUSION_BRANCH1, BRANCH_EXCLUSION_BRANCH2]

    def test_branch_automation_matches_its_own_branch(self, case: BuilderCase) -> None:
        trigger = case.build("branch1", []).trigger

        assert trigger.match["infrahub.branch.name"] == "branch1"
        assert isinstance(trigger.match_related, dict)

    def test_default_automation_without_diverged_branch_covers_every_branch(self, case: BuilderCase) -> None:
        """With nothing diverged, one automation owns every branch, including future ones."""
        automation = case.build(DEFAULT_BRANCH, [])

        assert "infrahub.branch.name" not in automation.trigger.match
        assert isinstance(automation.trigger.match_related, dict)
        assert _covered_branches({DEFAULT_BRANCH: automation}) == {
            DEFAULT_BRANCH: [DEFAULT_BRANCH],
            "branch1": [DEFAULT_BRANCH],
            "branch2": [DEFAULT_BRANCH],
            UNKNOWN_BRANCH: [DEFAULT_BRANCH],
        }


@dataclass
class ExcludeBranchesCase:
    name: str
    match_related: dict | list[dict]
    branch_names: list[str]
    expected: dict | list[dict]
    expected_prefect_specifications: int = field(default=1)


EXCLUDE_BRANCHES_CASES = [
    ExcludeBranchesCase(
        name="no_branch_leaves_the_dict_untouched",
        match_related={"infrahub.field.name": [FIELD]},
        branch_names=[],
        expected={"infrahub.field.name": [FIELD]},
    ),
    ExcludeBranchesCase(
        name="one_branch_promotes_the_dict_to_a_list",
        match_related={"infrahub.field.name": [FIELD]},
        branch_names=["branch1"],
        expected=[{"infrahub.field.name": [FIELD]}, BRANCH_EXCLUSION_BRANCH1],
        expected_prefect_specifications=2,
    ),
    ExcludeBranchesCase(
        name="branches_are_sorted_so_the_automation_is_stable",
        match_related={"infrahub.field.name": [FIELD]},
        branch_names=["branch2", "branch1"],
        expected=[{"infrahub.field.name": [FIELD]}, BRANCH_EXCLUSION_BRANCH1, BRANCH_EXCLUSION_BRANCH2],
        expected_prefect_specifications=3,
    ),
    ExcludeBranchesCase(
        name="an_empty_match_related_is_dropped",
        match_related={},
        branch_names=["branch1"],
        expected=[BRANCH_EXCLUSION_BRANCH1],
    ),
    ExcludeBranchesCase(
        name="an_existing_list_is_extended",
        match_related=[{"infrahub.field.name": [FIELD]}, BRANCH_EXCLUSION_BRANCH1],
        branch_names=["branch2"],
        expected=[{"infrahub.field.name": [FIELD]}, BRANCH_EXCLUSION_BRANCH1, BRANCH_EXCLUSION_BRANCH2],
        expected_prefect_specifications=3,
    ),
]


@pytest.mark.parametrize("case", EXCLUDE_BRANCHES_CASES, ids=lambda case: case.name)
def test_exclude_branches(case: ExcludeBranchesCase) -> None:
    event_trigger = EventTrigger(events={NodeUpdatedEvent.event_name}, match_related=case.match_related)

    event_trigger.exclude_branches(case.branch_names)

    assert event_trigger.match_related == case.expected

    prefect_match_related = event_trigger.get_prefect().match_related
    if case.expected_prefect_specifications == 1:
        assert not isinstance(prefect_match_related, list)
    else:
        assert isinstance(prefect_match_related, list)
        assert len(prefect_match_related) == case.expected_prefect_specifications
