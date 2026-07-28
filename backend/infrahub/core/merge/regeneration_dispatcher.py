from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.merge.selective_regen.models import CascadeRole
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ResourceNotFoundError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.workflows.catalogue import (
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub_sdk.diff import NodeDiff

    from infrahub.context import InfrahubContext
    from infrahub.core.diff.summary_cache import DiffSummaryCache
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .selective_regen.models import PlannedRegeneration, SelectiveRegenerationPlan
    from .selective_regen.orchestrator import RegenerationSelector


class FullRegenerationReason(StrEnum):
    """Why the merge follow-up fell back to regenerating every definition."""

    FEATURE_DISABLED = "Selective post-merge execution disabled"
    NO_SUMMARY_CAPTURED = "No merge diff summary captured"
    SUMMARY_UNAVAILABLE = "Merge diff summary unavailable"
    SELECTION_FAILED = "Selective post-merge regeneration failed"


async def submit_full_regeneration(*, workflow: InfrahubWorkflow, context: InfrahubContext, target_branch: str) -> None:
    """Regenerate every generator and artifact definition on the branch."""
    await workflow.submit_workflow(
        workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"branch": target_branch}
    )
    await workflow.submit_workflow(
        workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
        context=context,
        parameters={"branch": target_branch, "source": GeneratorDefinitionRunSource.MERGE},
    )


class PostMergeRegenerationDispatcher:
    """Decide and submit which generators and artifacts a committed merge should regenerate.

    Runs the selective path only when the feature is enabled and a merge diff summary is available;
    every other outcome -- feature disabled, no captured summary, an unloadable summary, or any
    failure during selection or dispatch -- falls back to the blanket regeneration the merge
    follow-up has always performed, so no path can leave an affected artifact stale.
    """

    def __init__(
        self,
        workflow: InfrahubWorkflow,
        selector: RegenerationSelector,
        summary_cache: DiffSummaryCache,
        log: Logger | LoggerAdapter[Logger],
    ) -> None:
        self.workflow = workflow
        self.selector = selector
        self.summary_cache = summary_cache
        self.log = log

    async def dispatch(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        merge_diff_cache_key: str | None,
    ) -> None:
        if not config.SETTINGS.main.selective_execution_after_merge:
            return await self._full_regeneration(
                context=context, target_branch=target_branch, reason=FullRegenerationReason.FEATURE_DISABLED
            )
        if merge_diff_cache_key is None:
            return await self._full_regeneration(
                context=context, target_branch=target_branch, reason=FullRegenerationReason.NO_SUMMARY_CAPTURED
            )

        try:
            diff_summary = await self.summary_cache.get(diff_id=merge_diff_cache_key)
        except ResourceNotFoundError:
            return await self._full_regeneration(
                context=context, target_branch=target_branch, reason=FullRegenerationReason.SUMMARY_UNAVAILABLE
            )

        kind_counts = Counter(entry["kind"] for entry in diff_summary)
        field_counts = Counter(element["name"] for entry in diff_summary for element in entry.get("elements", []))
        self.log.debug(
            f"SELECTIVE_REGEN merge-diff: nodes={len(diff_summary)} "
            f"kinds={dict(kind_counts)} changed_fields={dict(field_counts)}"
        )

        # A failure to build or dispatch the plan falls back to blanket regeneration rather than risk
        # leaving the merge under-regenerated. A single generator run failing is handled granularly in
        # _dispatch_plan and does not reach here.
        try:
            plan = await self.selector.build_plan(diff_summary=diff_summary, target_branch=target_branch)
            await self._dispatch_plan(context=context, target_branch=target_branch, plan=plan)
        except Exception:
            self.log.exception("Selective post-merge regeneration failed; falling back to full regeneration")
            await self._full_regeneration(
                context=context, target_branch=target_branch, reason=FullRegenerationReason.SELECTION_FAILED
            )

    async def _dispatch_plan(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        plan: SelectiveRegenerationPlan,
    ) -> None:
        sources = plan.for_role(CascadeRole.SOURCE)
        terminals = plan.for_role(CascadeRole.TERMINAL)
        source_runs = [request for entry in sources for request in entry.requests]
        generator_cascade = bool(source_runs)
        cascade_started_at = Timestamp() if generator_cascade else None

        self.log.debug(
            f"Selective post-merge execution: {len(source_runs)} cascade-source run(s), "
            f"{sum(len(entry.requests) for entry in terminals)} terminal generation(s)"
            + ("; generator cascade engaged" if generator_cascade else "")
        )

        if cascade_started_at is None:
            await self._submit(context=context, entries=terminals)
            return

        generator_failed = False
        for entry in sources:
            for run in entry.requests:
                try:
                    # Await each generator so its writes have landed before they are captured.
                    await self.workflow.execute_workflow(
                        workflow=entry.workflow, context=context, parameters={"model": run}
                    )
                except Exception:
                    generator_failed = True
                    self.log.exception("Post-merge generator run failed")

        if generator_failed:
            # A failed generator's consuming artifacts cannot be selected from its output, so regenerate
            # every artifact -- but never re-run the generators, which would fail the same way again.
            await self._submit_full_artifact_regeneration(context=context, target_branch=target_branch)
            return

        targeted = await self._reselect_from_cascade_output(
            context=context, target_branch=target_branch, sources=sources, since=cascade_started_at
        )
        if targeted is None:
            # Every artifact was already regenerated wholesale, which covers the merge-diff selection too.
            return
        # Dispatched only after the capture, so the capture window never sees these generations' own writes.
        await self._submit(context=context, entries=[*terminals, *targeted])

    async def _submit(self, *, context: InfrahubContext, entries: list[PlannedRegeneration]) -> None:
        """Submit each fire-and-forget request, letting the owning selector consolidate its own kind."""
        for entry in self.selector.consolidate_submissions(entries):
            for request in entry.requests:
                await self.workflow.submit_workflow(
                    workflow=entry.workflow, context=context, parameters={"model": request}
                )

    async def _reselect_from_cascade_output(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        sources: list[PlannedRegeneration],
        since: Timestamp,
    ) -> list[PlannedRegeneration] | None:
        """Reselect the fire-and-forget generations the just-run sources' own output requires.

        Each source captures its own output; the terminals that read it are then reselected from the
        combined diff. Returns ``None`` after regenerating every artifact wholesale when that output
        cannot be captured or selected, so a source's writes can never leave a consuming artifact stale.
        """
        try:
            captured: list[NodeDiff] = []
            for entry in sources:
                if entry.output is not None:
                    captured.extend(await entry.output.capture(since=since))
            targeted = await self.selector.reselect_from_cascade_output(
                diff_summary=captured, target_branch=target_branch
            )
        except Exception:
            self.log.exception("Failed to target artifacts from generator output; regenerating all artifacts instead")
            await self._submit_full_artifact_regeneration(context=context, target_branch=target_branch)
            return None
        targeted_count = sum(len(entry.requests) for entry in targeted)
        self.log.debug(f"Targeted {targeted_count} artifact definition(s) from generator output")
        return targeted

    async def _full_regeneration(
        self, context: InfrahubContext, target_branch: str, reason: FullRegenerationReason
    ) -> None:
        self.log.debug(f"{reason}; regenerating all definitions")
        await submit_full_regeneration(workflow=self.workflow, context=context, target_branch=target_branch)

    async def _submit_full_artifact_regeneration(self, context: InfrahubContext, target_branch: str) -> None:
        await self.workflow.submit_workflow(
            workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"branch": target_branch}
        )
