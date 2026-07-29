from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.proposed_change.branch_diff import get_modified_kinds

from .definition_selector.artifact_selector import ArtifactSelector
from .definition_selector.generator_selector import GeneratorSelector
from .fallbacks import repositories_forcing_full_regeneration
from .gate import DefinitionGate
from .generator_output import GeneratorCascadeOutput
from .impacted import ImpactedSubscriberResolver
from .models import CascadeRole, PlannedRegeneration, SelectiveRegenerationPlan
from .participant import CascadeSource, CascadeTerminal

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from .generator_output import GeneratorMutationDiffCapturer
    from .models import DefinitionModel, RegenerationRequest
    from .participant import CascadeParticipant


class RegenerationSelector(Protocol):
    """Computes which definitions and members a merge diff requires be regenerated."""

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan: ...

    async def reselect_from_cascade_output(
        self, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]: ...

    def consolidate_submissions(self, entries: Sequence[PlannedRegeneration]) -> list[PlannedRegeneration]: ...


class MergeSelectiveRegeneration:
    """Select the definitions a merge changed, narrowed to affected members, across every participant.

    Runs each injected participant's selector over a single computation of the diff's modified kinds and
    one shared repository-escalation set, returning one plan entry per participant for the follow-up to
    dispatch. Adding a definition kind is one new participant in the injected list, with no change here.
    """

    def __init__(self, participants: Sequence[CascadeParticipant]) -> None:
        self.participants = participants

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan:
        entries = await self._plan(self.participants, diff_summary=diff_summary, target_branch=target_branch)
        return SelectiveRegenerationPlan(entries=entries)

    async def reselect_from_cascade_output(
        self, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]:
        """Re-select the definitions a cascade source's own output requires be regenerated.

        Given the diff of what the just-run cascade sources wrote, re-run every non-source participant so
        the definitions that read that output are regenerated. The sources are excluded on purpose: they
        produced this diff, so re-running them on it would repeat runs already completed.
        """
        participants = [participant for participant in self.participants if participant.role is not CascadeRole.SOURCE]
        return await self._plan(participants, diff_summary=diff_summary, target_branch=target_branch)

    async def _plan(
        self, participants: Sequence[CascadeParticipant], *, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]:
        modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=target_branch)
        loaded_by_participant = [
            (participant, await participant.selector.load_definitions(target_branch=target_branch))
            for participant in participants
        ]

        # Aggregated over every participant's definitions so a repository escalated by any missing
        # fingerprint regenerates all of its definitions, not only the kind that carried the null one.
        all_definitions: list[DefinitionModel] = [
            loaded.definition for _, loaded_definitions in loaded_by_participant for loaded in loaded_definitions
        ]
        forced_repositories = repositories_forcing_full_regeneration(definitions=all_definitions)

        entries: list[PlannedRegeneration] = []
        for participant, loaded_definitions in loaded_by_participant:
            requests = await participant.selector.select(
                loaded_definitions=loaded_definitions,
                forced_repositories=forced_repositories,
                diff_summary=diff_summary,
                target_branch=target_branch,
                modified_kinds=modified_kinds,
            )
            entries.append(participant.to_entry(requests))
        return entries

    def consolidate_submissions(self, entries: Sequence[PlannedRegeneration]) -> list[PlannedRegeneration]:
        """Combine the given entries' requests through the participant that owns each, one batch per workflow.

        Requests are grouped by workflow, so each participant's selector consolidates its own kind -- an
        artifact selected by both the merge diff and a generator's output collapses to a single request --
        without the follow-up knowing how to merge them.
        """
        participant_by_workflow = {participant.selector.workflow.name: participant for participant in self.participants}
        requests_by_workflow: dict[str, list[RegenerationRequest]] = {}
        for entry in entries:
            requests_by_workflow.setdefault(entry.workflow.name, []).extend(entry.requests)
        submissions: list[PlannedRegeneration] = []
        for workflow_name, requests in requests_by_workflow.items():
            participant = participant_by_workflow[workflow_name]
            submissions.append(
                PlannedRegeneration(
                    workflow=participant.selector.workflow,
                    cascade_role=participant.role,
                    requests=participant.selector.consolidate(requests),
                )
            )
        return submissions


def build_merge_selective_regeneration(
    *,
    client: InfrahubClient,
    log: logging.Logger | logging.LoggerAdapter[logging.Logger],
    output_capturer: GeneratorMutationDiffCapturer,
) -> MergeSelectiveRegeneration:
    """Wire the participants for one merge follow-up, sharing the gate and impact resolver.

    The generator participant runs before the artifact participant so the plan awaits generator output
    before the artifacts that may read it are selected. The generator participant is the cascade source
    and carries the output capture built from the capturer, so the follow-up need not own that.
    """
    gate = DefinitionGate(log=log)
    impacted_resolver = ImpactedSubscriberResolver(client=client)
    return MergeSelectiveRegeneration(
        participants=[
            CascadeSource(
                GeneratorSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log),
                output=GeneratorCascadeOutput(capturer=output_capturer),
            ),
            CascadeTerminal(ArtifactSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log)),
        ]
    )
