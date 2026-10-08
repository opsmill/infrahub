from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Literal, assert_never

from infrahub import config
from infrahub.core.constants import FullRegenerationReason
from infrahub.core.merge.regeneration_barrier import OwnedRegeneration
from infrahub.core.merge.selective_regen.models import CascadeRole, PlannedRegeneration, SelectiveRegenerationPlan
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ResourceNotFoundError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.generators.models import RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.writeback.models import HeldItem, HeldRegeneration
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger, LoggerAdapter

    from infrahub_sdk.diff import NodeDiff
    from pydantic import BaseModel

    from infrahub.context import InfrahubContext
    from infrahub.core.diff.summary_cache import DiffSummaryCache
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .regeneration_barrier import RegenerationBarrier
    from .selective_regen.models import RegenerationRequest
    from .selective_regen.orchestrator import RegenerationPlanner


async def submit_full_regeneration(
    *,
    workflow: InfrahubWorkflow,
    context: InfrahubContext,
    target_branch: str,
    exclude_repository_ids: list[str] | None = None,
    include_repository_ids: list[str] | None = None,
) -> None:
    """Regenerate every generator and artifact definition on the branch whose repository the lists allow.

    An empty or missing list allows every repository.
    """
    repository_filters = _repository_filters(
        exclude_repository_ids=exclude_repository_ids, include_repository_ids=include_repository_ids
    )
    await workflow.submit_workflow(
        workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
        context=context,
        parameters={"branch": target_branch, **repository_filters},
    )
    await workflow.submit_workflow(
        workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
        context=context,
        parameters={"branch": target_branch, "source": GeneratorDefinitionRunSource.MERGE, **repository_filters},
    )


def _repository_filters(
    *, exclude_repository_ids: list[str] | None, include_repository_ids: list[str] | None = None
) -> dict[str, list[str]]:
    """Keep only the lists that are not empty, so that a run with no filter keeps the parameters of a blanket run."""
    filters = {"exclude_repository_ids": exclude_repository_ids, "include_repository_ids": include_repository_ids}
    return {name: repository_ids for name, repository_ids in filters.items() if repository_ids}


class PostMergeRegenerationDispatcher:
    """Decide and submit which generators and artifacts a committed merge should regenerate.

    Runs the selective path only when the feature is enabled and a merge diff summary is available;
    every other outcome -- feature disabled, no captured summary, an unloadable summary, or any
    failure during selection or dispatch -- falls back to the blanket regeneration the merge
    follow-up has always performed, so no path can leave an affected artifact stale.

    Every dispatch passes the barrier first: the work of a repository whose merges wait for their push
    is held, and a blanket regeneration excludes that repository and holds a marker for it instead.
    """

    def __init__(
        self,
        workflow: InfrahubWorkflow,
        planner: RegenerationPlanner,
        summary_cache: DiffSummaryCache,
        barrier: RegenerationBarrier,
        log: Logger | LoggerAdapter[Logger],
    ) -> None:
        self.workflow = workflow
        self.planner = planner
        self.summary_cache = summary_cache
        self.barrier = barrier
        self.log = log

    async def dispatch(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        merge_diff_cache_key: str | None,
        releasing: str | None,
    ) -> None:
        """Regenerate what the merge affected.

        Args:
            releasing: The repository whose held regeneration is being released, so the barrier admits its work.

        """
        if not config.SETTINGS.main.selective_execution_after_merge:
            return await self._full_regeneration(
                context=context,
                target_branch=target_branch,
                reason=FullRegenerationReason.FEATURE_DISABLED,
                releasing=releasing,
            )
        if merge_diff_cache_key is None:
            return await self._full_regeneration(
                context=context,
                target_branch=target_branch,
                reason=FullRegenerationReason.NO_SUMMARY_CAPTURED,
                releasing=releasing,
            )

        try:
            diff_summary = await self.summary_cache.get(diff_id=merge_diff_cache_key)
        except ResourceNotFoundError:
            return await self._full_regeneration(
                context=context,
                target_branch=target_branch,
                reason=FullRegenerationReason.SUMMARY_UNAVAILABLE,
                releasing=releasing,
            )

        # A failure to build or dispatch the plan falls back to blanket regeneration rather than risk
        # leaving the merge under-regenerated. A single generator run failing is handled granularly in
        # _dispatch_plan and does not reach here.
        try:
            plan = await self.planner.build_plan(diff_summary=diff_summary, target_branch=target_branch)
            await self._dispatch_plan(context=context, target_branch=target_branch, plan=plan, releasing=releasing)
        except Exception:
            self.log.exception("Selective post-merge regeneration failed; falling back to full regeneration")
            await self._full_regeneration(
                context=context,
                target_branch=target_branch,
                reason=FullRegenerationReason.SELECTION_FAILED,
                releasing=releasing,
            )

    async def dispatch_requests(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        generator_runs: Sequence[RequestGeneratorDefinitionRun],
        artifact_generates: Sequence[RequestArtifactDefinitionGenerate],
        releasing: str | None,
    ) -> None:
        """Dispatch the requests as a merge plan, so the generator cascade runs and every dispatch passes the barrier.

        A failed submission raises, with no fallback to a full regeneration.
        """
        entries = [
            PlannedRegeneration(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE, requests=generator_runs
            ),
            PlannedRegeneration(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                cascade_role=CascadeRole.TERMINAL,
                requests=artifact_generates,
            ),
        ]
        await self._dispatch_plan(
            context=context,
            target_branch=target_branch,
            plan=SelectiveRegenerationPlan(entries=self.planner.consolidate_submissions(entries)),
            releasing=releasing,
        )

    async def submit_repository_regeneration(
        self, *, context: InfrahubContext, target_branch: str, repository_id: str, scope: Literal["all", "terminals"]
    ) -> None:
        """Regenerate every definition of the repository, or only its terminal definitions.

        The barrier is not consulted: only the definitions of this repository run, so no other repository has work
        to hold.
        """
        match scope:
            case "all":
                await submit_full_regeneration(
                    workflow=self.workflow,
                    context=context,
                    target_branch=target_branch,
                    include_repository_ids=[repository_id],
                )
            case "terminals":
                for regeneration in self.planner.terminal_full_regenerations(target_branch):
                    await self.workflow.submit_workflow(
                        workflow=regeneration.workflow,
                        context=context,
                        parameters={**regeneration.parameters, "include_repository_ids": [repository_id]},
                    )
            case _:
                assert_never(scope)

    async def _dispatch_plan(
        self,
        *,
        context: InfrahubContext,
        target_branch: str,
        plan: SelectiveRegenerationPlan,
        releasing: str | None,
    ) -> None:
        admitted = SelectiveRegenerationPlan(
            entries=await self._admitted(entries=plan.entries, target_branch=target_branch, releasing=releasing)
        )
        sources = admitted.for_role(CascadeRole.SOURCE)
        terminals = admitted.for_role(CascadeRole.TERMINAL)
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
            # A failed source's consuming terminals cannot be selected from its output, so regenerate
            # every terminal -- but never re-run the sources, which would fail the same way again.
            await self._submit_full_terminal_regeneration(
                context=context, target_branch=target_branch, releasing=releasing
            )
            return

        targeted = await self._reselect_from_cascade_output(
            context=context, target_branch=target_branch, sources=sources, since=cascade_started_at, releasing=releasing
        )
        if targeted is None:
            # Every terminal was already regenerated wholesale, which covers the merge-diff selection too.
            return
        # The terminals of the plan passed the barrier already, so only the reselected entries consult it here.
        admitted_targeted = await self._admitted(entries=targeted, target_branch=target_branch, releasing=releasing)
        # Dispatched only after the capture, so the capture window never sees these generations' own writes.
        await self._submit(context=context, entries=[*terminals, *admitted_targeted])

    async def _submit(self, *, context: InfrahubContext, entries: list[PlannedRegeneration]) -> None:
        """Submit each fire-and-forget request, letting the owning selector consolidate its own kind."""
        for entry in self.planner.consolidate_submissions(entries):
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
        releasing: str | None,
    ) -> list[PlannedRegeneration] | None:
        """Reselect the fire-and-forget generations the just-run sources' own output requires.

        Each source captures its own output; the terminals that read it are then reselected from the
        combined diff. Returns ``None`` after regenerating every terminal wholesale when that output
        cannot be captured or selected, so a source's writes can never leave a consuming terminal stale.
        """
        try:
            captured: list[NodeDiff] = []
            for entry in sources:
                if entry.output is not None:
                    captured.extend(await entry.output.capture(since=since, requests=entry.requests))
            targeted = await self.planner.reselect_from_cascade_output(
                diff_summary=captured, target_branch=target_branch
            )
        except Exception:
            self.log.exception("Failed to target terminals from cascade output; regenerating all terminals instead")
            await self._submit_full_terminal_regeneration(
                context=context, target_branch=target_branch, releasing=releasing
            )
            return None
        targeted_count = sum(len(entry.requests) for entry in targeted)
        self.log.debug(f"Targeted {targeted_count} terminal definition(s) from cascade output")
        return targeted

    async def _full_regeneration(
        self, context: InfrahubContext, target_branch: str, reason: FullRegenerationReason, releasing: str | None
    ) -> None:
        self.log.debug(f"{reason}; regenerating all definitions")
        held = await self.barrier.hold_widen(branch=target_branch, scope="all", reason=reason, releasing=releasing)
        await submit_full_regeneration(
            workflow=self.workflow, context=context, target_branch=target_branch, exclude_repository_ids=held
        )

    async def _submit_full_terminal_regeneration(
        self, context: InfrahubContext, target_branch: str, releasing: str | None
    ) -> None:
        held = await self.barrier.hold_widen(
            branch=target_branch,
            scope="terminals",
            reason=FullRegenerationReason.TERMINAL_SELECTION_FAILED,
            releasing=releasing,
        )
        repository_filters = _repository_filters(exclude_repository_ids=held)
        for regeneration in self.planner.terminal_full_regenerations(target_branch):
            await self.workflow.submit_workflow(
                workflow=regeneration.workflow,
                context=context,
                parameters={**regeneration.parameters, **repository_filters},
            )

    async def _admitted(
        self, *, entries: list[PlannedRegeneration], target_branch: str, releasing: str | None
    ) -> list[PlannedRegeneration]:
        """Keep in each entry only the requests that the barrier admits; an entry can be left with none."""
        if not any(entry.requests for entry in entries):
            return entries
        candidates = [[self._owned(request=request) for request in entry.requests] for entry in entries]
        admitted = await self.barrier.admit(
            branch=target_branch,
            candidates=[candidate for entry_candidates in candidates for candidate in entry_candidates],
            releasing=releasing,
        )
        return [
            replace(entry, requests=[candidate.request for candidate in entry_candidates if candidate in admitted])
            for entry, entry_candidates in zip(entries, candidates, strict=True)
        ]

    def _owned(self, *, request: RegenerationRequest) -> OwnedRegeneration[RegenerationRequest]:
        match request:
            case RequestArtifactDefinitionGenerate():
                return OwnedRegeneration(
                    repository_id=request.repository_id,
                    held=HeldRegeneration(
                        artifact_definitions=(HeldItem(id=request.artifact_definition_id, hold_seq=0),)
                    ),
                    request=request,
                    union=self._join_artifact_requests,
                )
            case RequestGeneratorDefinitionRun():
                # No rule joins the target members of two runs, so a repeated hold releases the run unnarrowed.
                return OwnedRegeneration(
                    repository_id=request.generator_definition.repository_id,
                    held=HeldRegeneration(
                        generator_definitions=(HeldItem(id=request.generator_definition.definition_id, hold_seq=0),)
                    ),
                    request=request,
                    union=None,
                )
            case _:
                assert_never(request)

    def _join_artifact_requests(self, previous: BaseModel, new: BaseModel) -> BaseModel:
        if not isinstance(previous, RequestArtifactDefinitionGenerate) or not isinstance(
            new, RequestArtifactDefinitionGenerate
        ):
            raise TypeError(f"Cannot join a {type(previous).__name__} and a {type(new).__name__}")
        (consolidated,) = self.planner.consolidate_submissions(
            [
                PlannedRegeneration(
                    workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                    cascade_role=CascadeRole.TERMINAL,
                    requests=[previous, new],
                )
            ]
        )
        (joined,) = consolidated.requests
        return joined
