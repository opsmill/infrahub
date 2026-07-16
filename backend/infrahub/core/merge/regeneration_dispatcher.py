from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.exceptions import ResourceNotFoundError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub.context import InfrahubContext
    from infrahub.core.diff.summary_cache import DiffSummaryCache
    from infrahub.services.adapters.workflow import InfrahubWorkflow

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

        # Re-dispatching a definition already submitted is safe over-execution, so any failure here
        # falls back to the blanket path rather than risk leaving the merge under-regenerated.
        try:
            plan = await self.selector.build_plan(diff_summary=diff_summary, target_branch=target_branch)
            self.log.info(
                f"Selective post-merge execution: "
                f"{len(plan.generator_runs)} generator run(s), {len(plan.artifact_generates)} artifact generation(s)"
            )
            for generator_run in plan.generator_runs:
                await self.workflow.submit_workflow(
                    workflow=REQUEST_GENERATOR_DEFINITION_RUN, context=context, parameters={"model": generator_run}
                )
            for artifact_generate in plan.artifact_generates:
                await self.workflow.submit_workflow(
                    workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                    context=context,
                    parameters={"model": artifact_generate},
                )
        except Exception:
            self.log.exception("Selective regeneration failed during the selection phase")
            await self._full_regeneration(
                context=context, target_branch=target_branch, reason=FullRegenerationReason.SELECTION_FAILED
            )

    async def _full_regeneration(
        self, context: InfrahubContext, target_branch: str, reason: FullRegenerationReason
    ) -> None:
        self.log.info(f"{reason}; regenerating all definitions")
        await submit_full_regeneration(workflow=self.workflow, context=context, target_branch=target_branch)
