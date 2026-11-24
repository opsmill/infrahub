"""Branch scoping of the per-node trigger families.

A branch whose definition differs from the default branch owns its own automation. The
default-branch automation must then skip the events of that branch, or the work runs twice.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    def test_default_automation_without_diverged_branch_covers_every_branch(self, case: BuilderCase) -> None:
        """With nothing diverged, one automation owns every branch, including future ones."""
        assert _covered_branches({DEFAULT_BRANCH: case.build(DEFAULT_BRANCH, [])}) == {
            DEFAULT_BRANCH: [DEFAULT_BRANCH],
            "branch1": [DEFAULT_BRANCH],
            "branch2": [DEFAULT_BRANCH],
            UNKNOWN_BRANCH: [DEFAULT_BRANCH],
        }


@dataclass
class ExcludeBranchesCase:
    name: str
    branch_names: list[str]
    expected: dict | list[dict]


EXCLUDE_BRANCHES_CASES = [
    ExcludeBranchesCase(
        name="nothing_to_exclude_leaves_the_shape_alone",
        branch_names=[],
        expected={"infrahub.field.name": [FIELD]},
    ),
    ExcludeBranchesCase(
        name="exclusions_are_sorted",
        branch_names=["branch2", "branch1"],
        expected=[{"infrahub.field.name": [FIELD]}, BRANCH_EXCLUSION_BRANCH1, BRANCH_EXCLUSION_BRANCH2],
    ),
]


@pytest.mark.parametrize("case", EXCLUDE_BRANCHES_CASES, ids=lambda case: case.name)
def test_exclude_branches_keeps_the_automation_stable(case: ExcludeBranchesCase) -> None:
    """An automation is reconciled by comparing model dumps, so the output has to be stable.

    Registry order is insertion order, so unsorted exclusions would rewrite the automation on
    every setup run, and an untouched filter has to keep the shape it had.
    """
    event_trigger = EventTrigger(events={NodeUpdatedEvent.event_name}, match_related={"infrahub.field.name": [FIELD]})

    event_trigger.exclude_branches(case.branch_names)

    assert event_trigger.match_related == case.expected
