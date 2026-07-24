from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.timestamp import Timestamp
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
    from infrahub.git.models import RequestArtifactDefinitionGenerate
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .selective_regen.generator_diff_capturer import GeneratorMutationDiffCapturer
    from .selective_regen.models import SelectiveRegenerationPlan
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


def _consolidate_artifact_generates(
    artifact_generates: list[RequestArtifactDefinitionGenerate],
) -> list[RequestArtifactDefinitionGenerate]:
    """Merge requests for the same artifact definition into one, unioning their member/limit filters.

    An artifact selected from both the merge diff and a generator's output would otherwise be dispatched
    twice; an empty filter means "all members", so it subsumes any specific filter.
    """
    consolidated: dict[str, RequestArtifactDefinitionGenerate] = {}
    for request in artifact_generates:
        merged = consolidated.get(request.artifact_definition_id)
        if merged is None:
            consolidated[request.artifact_definition_id] = request
            continue
        members = [] if not merged.members or not request.members else sorted({*merged.members, *request.members})
        limit = [] if not merged.limit or not request.limit else sorted({*merged.limit, *request.limit})
        consolidated[request.artifact_definition_id] = merged.model_copy(update={"members": members, "limit": limit})
    return list(consolidated.values())


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
        generator_diff_capturer: GeneratorMutationDiffCapturer,
        log: Logger | LoggerAdapter[Logger],
    ) -> None:
        self.workflow = workflow
        self.selector = selector
        self.summary_cache = summary_cache
        self.generator_diff_capturer = generator_diff_capturer
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
        self.log.info(
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
        generator_cascade = bool(plan.generator_runs)
        cascade_started_at = Timestamp() if generator_cascade else None

        self.log.info(
            f"Selective post-merge execution: {len(plan.generator_runs)} generator run(s), "
            f"{len(plan.artifact_generates)} artifact generation(s)"
            + ("; generator cascade engaged" if generator_cascade else "")
        )

        if cascade_started_at is None:
            await self._submit_artifacts(context=context, artifact_generates=plan.artifact_generates)
            return

        generator_failed = False
        for generator_run in plan.generator_runs:
            try:
                # Await each generator so its writes have landed before they are captured.
                await self.workflow.execute_workflow(
                    workflow=REQUEST_GENERATOR_DEFINITION_RUN, context=context, parameters={"model": generator_run}
                )
            except Exception:
                generator_failed = True
                self.log.exception("Post-merge generator run failed")

        if generator_failed:
            # A failed generator's consuming artifacts cannot be selected from its output, so regenerate
            # every artifact -- but never re-run the generators, which would fail the same way again.
            await self._submit_full_artifact_regeneration(context=context, target_branch=target_branch)
            return

        targeted = await self._artifacts_from_generator_output(
            context=context,
            target_branch=target_branch,
            since=cascade_started_at,
            generator_definition_names=[run.generator_definition.definition_name for run in plan.generator_runs],
        )
        if targeted is None:
            # Every artifact was already regenerated wholesale, which covers the merge-diff selection too.
            return
        # Dispatched only after the capture, so the capture window never sees these artifact generations'
        # own writes.
        await self._submit_artifacts(context=context, artifact_generates=[*plan.artifact_generates, *targeted])

    async def _submit_artifacts(
        self, *, context: InfrahubContext, artifact_generates: list[RequestArtifactDefinitionGenerate]
    ) -> None:
        for artifact_generate in _consolidate_artifact_generates(artifact_generates):
            await self.workflow.submit_workflow(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"model": artifact_generate}
            )

    async def _artifacts_from_generator_output(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        since: Timestamp,
        generator_definition_names: list[str],
    ) -> list[RequestArtifactDefinitionGenerate] | None:
        """Select the artifacts the just-run generators' writes require be regenerated.

        Returns ``None`` after regenerating every artifact wholesale when the generator output cannot be
        captured or selected, so a generator's writes can never leave a consuming artifact stale.
        """
        try:
            generator_diff = await self.generator_diff_capturer.capture(
                since=since, generator_definition_names=generator_definition_names
            )
            targeted = await self.selector.select_artifacts(diff_summary=generator_diff, target_branch=target_branch)
        except Exception:
            self.log.exception("Failed to target artifacts from generator output; regenerating all artifacts instead")
            await self._submit_full_artifact_regeneration(context=context, target_branch=target_branch)
            return None
        self.log.info(f"Targeted {len(targeted)} artifact definition(s) from generator output")
        return targeted

    async def _full_regeneration(
        self, context: InfrahubContext, target_branch: str, reason: FullRegenerationReason
    ) -> None:
        self.log.info(f"{reason}; regenerating all definitions")
        await submit_full_regeneration(workflow=self.workflow, context=context, target_branch=target_branch)

    async def _submit_full_artifact_regeneration(self, context: InfrahubContext, target_branch: str) -> None:
        await self.workflow.submit_workflow(
            workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"branch": target_branch}
        )
