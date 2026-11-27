from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.artifacts.checks import artifact_check_name
from infrahub.core.constants import ValidatorConclusion
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

UNRESOLVED_CHECK_CONCLUSIONS = (ValidatorConclusion.FAILURE.value, ValidatorConclusion.UNKNOWN.value)


@dataclass(frozen=True)
class ArtifactCheckState:
    check_id: str
    artifact_id: str | None
    name: str | None
    conclusion: str | None

    @property
    def is_unresolved(self) -> bool:
        return self.conclusion in UNRESOLVED_CHECK_CONCLUSIONS


@dataclass(frozen=True)
class ArtifactTarget:
    target_id: str
    label: str | None
    artifact_id: str | None


@dataclass(frozen=True)
class ArtifactRunPlan:
    target_ids: list[str]
    """Targets to render, in the order of the definition's targets."""

    check_ids: dict[str, str]
    """The existing check that the render of a target updates, for targets whose check is already known."""

    obsolete_check_ids: list[str]
    """Unresolved checks that match no current target of the definition."""

    keeps_failure: bool
    """An unresolved check remains that this run neither renders again nor deletes."""


class ArtifactRunPlanner:
    """Choose the targets of an artifact validation run from the unresolved checks of the previous run.

    A check matches its target through the artifact it reports on, or by its name when it has no artifact.
    """

    def __init__(
        self, *, artifact_name: str, targets: Sequence[ArtifactTarget], unresolved_checks: Sequence[ArtifactCheckState]
    ) -> None:
        self._target_ids = [target.target_id for target in targets]
        self._targets_by_artifact = {target.artifact_id: target.target_id for target in targets if target.artifact_id}
        self._targets_by_name: dict[str, list[str]] = defaultdict(list)
        for target in targets:
            if target.label is not None:
                name = artifact_check_name(artifact_name=artifact_name, target_name=target.label)
                self._targets_by_name[name].append(target.target_id)
        self._unresolved_checks = list(unresolved_checks)

    def plan_failed_retry(self, requested_checks: Sequence[ArtifactCheckState] | None) -> ArtifactRunPlan:
        """Plan a run of the unresolved targets, limited to the targets of `requested_checks` when given."""
        if requested_checks is None:
            return self._plan(candidates=self._unresolved_check_by_target(), scoped=False, requested={})
        requested = self._requested_check_by_target(requested_checks=requested_checks)
        unresolved_ids = {check.check_id for check in requested_checks if check.is_unresolved}
        unresolved_requested = {
            target_id: check_id for target_id, check_id in requested.items() if check_id in unresolved_ids
        }
        return self._plan(candidates=unresolved_requested, scoped=True, requested=unresolved_requested)

    def plan_changes(
        self, changed_target_ids: Collection[str], requested_checks: Sequence[ArtifactCheckState] | None
    ) -> ArtifactRunPlan:
        """Plan a run of the changed targets, limited to the targets of `requested_checks` when given."""
        if requested_checks is None:
            return self._plan(candidates=changed_target_ids, scoped=False, requested={})
        requested = self._requested_check_by_target(requested_checks=requested_checks)
        changed = set(changed_target_ids)
        return self._plan(
            candidates=[target_id for target_id in requested if target_id in changed], scoped=True, requested=requested
        )

    def _target_ids_of(self, check: ArtifactCheckState) -> list[str]:
        if check.artifact_id:
            target_id = self._targets_by_artifact.get(check.artifact_id)
            return [target_id] if target_id else []
        return self._targets_by_name.get(check.name or "", [])

    def _unresolved_check_by_target(self) -> dict[str, str]:
        check_by_target: dict[str, str] = {}
        for check in self._unresolved_checks:
            for target_id in self._target_ids_of(check):
                check_by_target.setdefault(target_id, check.check_id)
        return check_by_target

    def _requested_check_by_target(self, requested_checks: Sequence[ArtifactCheckState]) -> dict[str, str]:
        check_by_target: dict[str, str] = {}
        for check in requested_checks:
            target_ids = self._target_ids_of(check)
            if not target_ids:
                raise ValidationError(
                    f"The artifact check {check.check_id} matches no current target of the artifact definition. "
                    "Refresh the checks view."
                )
            for target_id in target_ids:
                check_by_target.setdefault(target_id, check.check_id)
        return check_by_target

    def _plan(self, *, candidates: Collection[str], scoped: bool, requested: Mapping[str, str]) -> ArtifactRunPlan:
        selected = [target_id for target_id in self._target_ids if target_id in candidates]
        selected_ids = set(selected)
        obsolete_check_ids = (
            [] if scoped else [check.check_id for check in self._unresolved_checks if not self._target_ids_of(check)]
        )
        keeps_failure = any(
            not selected_ids.intersection(self._target_ids_of(check))
            for check in self._unresolved_checks
            if check.check_id not in obsolete_check_ids
        )

        unresolved = self._unresolved_check_by_target()
        check_ids: dict[str, str] = {}
        assigned_check_ids: set[str] = set()
        for target_id in selected:
            check_id = requested.get(target_id) or unresolved.get(target_id)
            # A check matched by a shared name is updated by one target only, so each target keeps its own check.
            if check_id and check_id not in assigned_check_ids:
                check_ids[target_id] = check_id
                assigned_check_ids.add(check_id)

        return ArtifactRunPlan(
            target_ids=selected,
            check_ids=check_ids,
            obsolete_check_ids=obsolete_check_ids,
            keeps_failure=keeps_failure,
        )
