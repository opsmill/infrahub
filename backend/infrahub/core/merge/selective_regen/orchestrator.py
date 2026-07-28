from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from infrahub.proposed_change.branch_diff import get_modified_kinds

from .definition_selector.artifact_selector import ArtifactSelector
from .definition_selector.generator_selector import GeneratorSelector
from .fallbacks import repositories_forcing_full_regeneration
from .gate import DefinitionGate
from .impacted import ImpactedSubscriberResolver
from .models import CascadeRole, PlannedRegeneration, SelectiveRegenerationPlan

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from .definition_selector.base import DefinitionSelectorBase
    from .generator_diff_capturer import GeneratorMutationDiffCapturer
    from .models import DefinitionModel, RegenerationRequest


class RegenerationSelector(Protocol):
    """Computes which definitions and members a merge diff requires be regenerated."""

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan: ...

    async def reselect_from_cascade_output(
        self, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]: ...

    def consolidate_submissions(self, entries: Sequence[PlannedRegeneration]) -> list[PlannedRegeneration]: ...


class MergeSelectiveRegeneration:
    """Select the definitions a merge changed, narrowed to affected members, across every selector.

    Runs each injected selector over a single computation of the diff's modified kinds and one shared
    repository-escalation set, returning one plan entry per selector for the follow-up to dispatch.
    Adding a definition kind is one new selector in the injected list, with no change here.
    """

    def __init__(self, selectors: Sequence[DefinitionSelectorBase[Any, Any]]) -> None:
        self.selectors = selectors

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan:
        modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=target_branch)
        loaded_by_selector = [
            (selector, await selector.load_definitions(target_branch=target_branch)) for selector in self.selectors
        ]

        # Computed over every selector's definitions so a repository escalated by any missing fingerprint
        # regenerates all of its definitions, not only those of the kind that carried the null fingerprint.
        all_definitions: list[DefinitionModel] = [
            loaded.definition for _, loaded_definitions in loaded_by_selector for loaded in loaded_definitions
        ]
        forced_repositories = repositories_forcing_full_regeneration(definitions=all_definitions)

        entries: list[PlannedRegeneration] = []
        for selector, loaded_definitions in loaded_by_selector:
            requests = await selector.select(
                loaded_definitions=loaded_definitions,
                forced_repositories=forced_repositories,
                diff_summary=diff_summary,
                target_branch=target_branch,
                modified_kinds=modified_kinds,
            )
            entries.append(
                PlannedRegeneration(
                    workflow=selector.workflow,
                    cascade_role=selector.cascade_role,
                    requests=requests,
                    output=selector.output_capture(requests),
                )
            )
        return SelectiveRegenerationPlan(entries=entries)

    async def reselect_from_cascade_output(
        self, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]:
        """Re-select the definitions a cascade source's own output requires be regenerated.

        Given the diff of what the just-run cascade sources wrote, re-run every non-source selector so
        the definitions that read that output are regenerated. The sources are excluded on purpose:
        they produced this diff, so re-running them on it would repeat runs already completed.
        """
        modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=target_branch)
        entries: list[PlannedRegeneration] = []
        for selector in self.selectors:
            if selector.cascade_role is CascadeRole.SOURCE:
                continue
            loaded_definitions = await selector.load_definitions(target_branch=target_branch)
            forced_repositories = repositories_forcing_full_regeneration(
                definitions=[loaded.definition for loaded in loaded_definitions]
            )
            requests = await selector.select(
                loaded_definitions=loaded_definitions,
                forced_repositories=forced_repositories,
                diff_summary=diff_summary,
                target_branch=target_branch,
                modified_kinds=modified_kinds,
            )
            entries.append(
                PlannedRegeneration(
                    workflow=selector.workflow,
                    cascade_role=selector.cascade_role,
                    requests=requests,
                    output=selector.output_capture(requests),
                )
            )
        return entries

    def consolidate_submissions(self, entries: Sequence[PlannedRegeneration]) -> list[PlannedRegeneration]:
        """Combine the given entries' requests through the selector that owns each, one batch per selector.

        Requests are grouped by their selector (matched on workflow), so each selector consolidates its
        own kind -- an artifact selected by both the merge diff and a generator's output collapses to a
        single request -- without the follow-up knowing how to merge them.
        """
        selector_by_workflow = {selector.workflow.name: selector for selector in self.selectors}
        requests_by_workflow: dict[str, list[RegenerationRequest]] = {}
        for entry in entries:
            requests_by_workflow.setdefault(entry.workflow.name, []).extend(entry.requests)
        return [
            PlannedRegeneration(
                workflow=selector_by_workflow[workflow_name].workflow,
                cascade_role=selector_by_workflow[workflow_name].cascade_role,
                requests=selector_by_workflow[workflow_name].consolidate(requests),
            )
            for workflow_name, requests in requests_by_workflow.items()
        ]


def build_merge_selective_regeneration(
    *,
    client: InfrahubClient,
    log: logging.Logger | logging.LoggerAdapter[logging.Logger],
    output_capturer: GeneratorMutationDiffCapturer,
) -> MergeSelectiveRegeneration:
    """Wire a fully-injected selector for one merge follow-up, sharing the gate and impact resolver.

    The generator selector runs before the artifact selector so the plan awaits generator output
    before the artifacts that may read it are selected. The generator selector also holds the output
    capturer, so it -- not the follow-up -- owns capturing what its generators wrote.
    """
    gate = DefinitionGate(log=log)
    impacted_resolver = ImpactedSubscriberResolver(client=client)
    return MergeSelectiveRegeneration(
        selectors=[
            GeneratorSelector(
                client=client,
                gate=gate,
                impacted_resolver=impacted_resolver,
                log=log,
                output_capturer=output_capturer,
            ),
            ArtifactSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log),
        ]
    )
