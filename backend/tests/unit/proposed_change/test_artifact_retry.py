from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.core.constants import ValidatorConclusion
from infrahub.exceptions import ValidationError
from infrahub.proposed_change.artifact_retry import (
    ArtifactCheckState,
    ArtifactRunPlan,
    ArtifactRunPlanner,
    ArtifactTarget,
)

ARTIFACT_NAME = "config"
TARGETS = [
    ArtifactTarget(target_id="router-1", label="router-1", artifact_id="artifact-1"),
    ArtifactTarget(target_id="router-2", label="router-2", artifact_id="artifact-2"),
    ArtifactTarget(target_id="router-3", label="router-3", artifact_id=None),
    ArtifactTarget(target_id="switch-a", label="switch", artifact_id="artifact-a"),
    ArtifactTarget(target_id="switch-b", label="switch", artifact_id="artifact-b"),
]
FAILED_BY_ARTIFACT = ArtifactCheckState(
    check_id="failed-1", artifact_id="artifact-1", name="config: router-1", conclusion=ValidatorConclusion.FAILURE.value
)
UNFINISHED_BY_ARTIFACT = ArtifactCheckState(
    check_id="unfinished-2",
    artifact_id="artifact-2",
    name="config: router-2",
    conclusion=ValidatorConclusion.UNKNOWN.value,
)
FAILED_BY_NAME = ArtifactCheckState(
    check_id="failed-3", artifact_id=None, name="config: router-3", conclusion=ValidatorConclusion.FAILURE.value
)
FAILED_OF_REMOVED_TARGET = ArtifactCheckState(
    check_id="failed-removed",
    artifact_id="artifact-removed",
    name="config: router-1",
    conclusion=ValidatorConclusion.FAILURE.value,
)
PASSED_SWITCH = ArtifactCheckState(
    check_id="passed-a", artifact_id="artifact-a", name="config: switch", conclusion=ValidatorConclusion.SUCCESS.value
)


def make_planner(*unresolved_checks: ArtifactCheckState) -> ArtifactRunPlanner:
    return ArtifactRunPlanner(artifact_name=ARTIFACT_NAME, targets=TARGETS, unresolved_checks=unresolved_checks)


def test_failed_retry_renders_the_targets_of_unresolved_checks() -> None:
    planner = make_planner(FAILED_BY_ARTIFACT, UNFINISHED_BY_ARTIFACT, FAILED_BY_NAME, FAILED_OF_REMOVED_TARGET)

    assert planner.plan_failed_retry(requested_checks=None) == ArtifactRunPlan(
        target_ids=["router-1", "router-2", "router-3"],
        check_ids={"router-1": "failed-1", "router-2": "unfinished-2", "router-3": "failed-3"},
        obsolete_check_ids=["failed-removed"],
        keeps_failure=False,
    )


def test_a_check_with_an_artifact_never_matches_a_target_by_name() -> None:
    plan = make_planner(FAILED_OF_REMOVED_TARGET).plan_failed_retry(requested_checks=None)

    assert plan.target_ids == []
    assert plan.obsolete_check_ids == ["failed-removed"]


@dataclass
class SharedNameCase:
    name: str
    unresolved_check_ids: list[str]
    expected: ArtifactRunPlan


SHARED_NAME_CASES: list[SharedNameCase] = [
    SharedNameCase(
        name="one_check_is_updated_by_one_target",
        unresolved_check_ids=["failed-switch-1"],
        expected=ArtifactRunPlan(
            target_ids=["switch-a", "switch-b"],
            check_ids={"switch-a": "failed-switch-1"},
            obsolete_check_ids=[],
            keeps_failure=False,
        ),
    ),
    SharedNameCase(
        name="each_target_updates_its_own_check",
        unresolved_check_ids=["failed-switch-1", "failed-switch-2"],
        expected=ArtifactRunPlan(
            target_ids=["switch-a", "switch-b"],
            check_ids={"switch-a": "failed-switch-1", "switch-b": "failed-switch-2"},
            obsolete_check_ids=[],
            keeps_failure=False,
        ),
    ),
    SharedNameCase(
        name="a_check_that_no_target_updates_keeps_the_failure",
        unresolved_check_ids=["failed-switch-1", "failed-switch-2", "failed-switch-3"],
        expected=ArtifactRunPlan(
            target_ids=["switch-a", "switch-b"],
            check_ids={"switch-a": "failed-switch-1", "switch-b": "failed-switch-2"},
            obsolete_check_ids=[],
            keeps_failure=True,
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SHARED_NAME_CASES])
def test_checks_matched_by_a_shared_name(test_case: SharedNameCase) -> None:
    planner = make_planner(
        *(
            ArtifactCheckState(
                check_id=check_id,
                artifact_id=None,
                name="config: switch",
                conclusion=ValidatorConclusion.FAILURE.value,
            )
            for check_id in test_case.unresolved_check_ids
        )
    )

    assert planner.plan_failed_retry(requested_checks=None) == test_case.expected


@dataclass
class ChangeRunCase:
    name: str
    unresolved_checks: list[ArtifactCheckState]
    changed_target_ids: set[str]
    expected: ArtifactRunPlan


CHANGE_RUN_CASES: list[ChangeRunCase] = [
    ChangeRunCase(
        name="unresolved_target_outside_the_changes_keeps_the_failure",
        unresolved_checks=[FAILED_BY_ARTIFACT, UNFINISHED_BY_ARTIFACT],
        changed_target_ids={"router-2", "switch-a"},
        expected=ArtifactRunPlan(
            target_ids=["router-2", "switch-a"],
            check_ids={"router-2": "unfinished-2"},
            obsolete_check_ids=[],
            keeps_failure=True,
        ),
    ),
    ChangeRunCase(
        name="every_unresolved_target_rendered_keeps_no_failure",
        unresolved_checks=[FAILED_BY_ARTIFACT, FAILED_BY_NAME],
        changed_target_ids={"router-1", "router-3"},
        expected=ArtifactRunPlan(
            target_ids=["router-1", "router-3"],
            check_ids={"router-1": "failed-1", "router-3": "failed-3"},
            obsolete_check_ids=[],
            keeps_failure=False,
        ),
    ),
    ChangeRunCase(
        name="check_of_a_removed_target_is_deleted_and_keeps_no_failure",
        unresolved_checks=[FAILED_OF_REMOVED_TARGET],
        changed_target_ids=set(),
        expected=ArtifactRunPlan(
            target_ids=[], check_ids={}, obsolete_check_ids=["failed-removed"], keeps_failure=False
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in CHANGE_RUN_CASES])
def test_change_run_renders_changed_targets(test_case: ChangeRunCase) -> None:
    planner = make_planner(*test_case.unresolved_checks)

    assert planner.plan_changes(changed_target_ids=test_case.changed_target_ids, requested_checks=None) == (
        test_case.expected
    )


def test_scoped_failed_retry_renders_only_requested_unresolved_checks() -> None:
    planner = make_planner(FAILED_BY_ARTIFACT, UNFINISHED_BY_ARTIFACT, FAILED_OF_REMOVED_TARGET)

    assert planner.plan_failed_retry(requested_checks=[FAILED_BY_ARTIFACT, PASSED_SWITCH]) == ArtifactRunPlan(
        target_ids=["router-1"],
        check_ids={"router-1": "failed-1"},
        obsolete_check_ids=[],
        keeps_failure=True,
    )


def test_scoped_change_run_renders_requested_targets_that_changed() -> None:
    planner = make_planner(FAILED_BY_ARTIFACT)

    plan = planner.plan_changes(
        changed_target_ids={"router-2", "switch-a"}, requested_checks=[FAILED_BY_ARTIFACT, PASSED_SWITCH]
    )

    assert plan == ArtifactRunPlan(
        target_ids=["switch-a"], check_ids={"switch-a": "passed-a"}, obsolete_check_ids=[], keeps_failure=True
    )


@dataclass
class RejectedRequestCase:
    name: str
    plan: Callable[[ArtifactRunPlanner, list[ArtifactCheckState]], ArtifactRunPlan]


REJECTED_REQUEST_CASES: list[RejectedRequestCase] = [
    RejectedRequestCase(
        name="failed_retry",
        plan=lambda planner, requested: planner.plan_failed_retry(requested_checks=requested),
    ),
    RejectedRequestCase(
        name="change_run",
        plan=lambda planner, requested: planner.plan_changes(
            changed_target_ids={"router-1"}, requested_checks=requested
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REJECTED_REQUEST_CASES])
def test_requested_check_without_a_current_target_is_rejected(test_case: RejectedRequestCase) -> None:
    planner = make_planner(FAILED_OF_REMOVED_TARGET)

    with pytest.raises(
        ValidationError,
        match=r"^The artifact check failed-removed matches no current target of the artifact definition\. "
        r"Refresh the checks view\.$",
    ):
        test_case.plan(planner, [FAILED_OF_REMOVED_TARGET])
