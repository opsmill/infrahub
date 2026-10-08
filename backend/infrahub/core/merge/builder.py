from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.regeneration.impact import FieldLevelImpactResolver
from infrahub.core.registry import registry
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.update_coordinator import SchemaUpdateCoordinator
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.git.writeback.constants import NARROWED_HOLD_MAX_BYTES, NARROWED_HOLD_TTL_SECONDS
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.workers.dependencies import get_cache, get_client, get_event_service, get_workflow

from .constraints import MergeConstraintValidator
from .graph_merger import GraphMerger
from .orchestrator import BranchMergeOrchestrator
from .post_merge import PostMergeDispatcher
from .python_target_sources import build_python_target_resolver
from .recompute_coalescing import CoalescedRecomputeSubmitter
from .regeneration_barrier import NarrowedHoldCache, RegenerationBarrier
from .regeneration_dispatcher import PostMergeRegenerationDispatcher
from .regeneration_release import HeldDefinitionResolver, HeldRegenerationReleaser
from .repository_merge_dispatcher import RepositoryMergeDispatcher
from .rollback_handler import MergeRollbackHandler
from .schema_analyzer import MergeSchemaAnalyzer
from .selective_regen.definition_selector.artifact_selector import ArtifactSelector
from .selective_regen.definition_selector.generator_selector import GeneratorSelector
from .selective_regen.gate import DefinitionGate
from .selective_regen.generator_output import GeneratorCascadeOutput, GeneratorTrackingGroupDiffCapturer
from .selective_regen.orchestrator import build_merge_selective_regeneration
from .write_blocker import MergeWriteBlocker

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.ports import DeliveryStatePort
    from infrahub.services.adapters.workflow import InfrahubWorkflow


async def build_branch_merge_orchestrator(
    *,
    db: InfrahubDatabase,
    source_branch: Branch,
    destination_branch: Branch,
    logger: Logger | LoggerAdapter[Logger] | None = None,
) -> BranchMergeOrchestrator:
    """Wire a fully-injected branch merge orchestrator for a single merge of the source branch.

    When invoked inside a Prefect flow, pass the flow-run logger so it is used through the whole merge.
    """
    component_registry = get_component_registry()
    workflow = get_workflow()
    event_service = await get_event_service()
    cache = await get_cache()
    merge_write_blocker = MergeWriteBlocker(cache=cache)
    diff_summary_serializer = DiffSummarySerializer()

    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=source_branch)
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=source_branch)
    if logger is not None:
        diff_coordinator.set_logger(logger)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=source_branch)
    ipam_diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=source_branch)

    schema_analyzer = MergeSchemaAnalyzer(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_repository=diff_repository,
        schema_manager=registry.schema,
    )
    constraint_validator = MergeConstraintValidator(
        branch=source_branch,
        diff_repository=diff_repository,
        determiner=build_constraint_validator_determiner(db=db, branch=source_branch),
        constraint_info_merger=build_constraint_info_merger(),
        migration_validator=schema_validate_migrations,
    )
    graph_merger = GraphMerger(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_coordinator=diff_coordinator,
        diff_merger=diff_merger,
        diff_repository=diff_repository,
        diff_locker=DiffLocker(),
        schema_analyzer=schema_analyzer,
        constraint_validator=constraint_validator,
        logger=logger,
    )
    delivery_state = WritebackIntentStore(
        db=db, lock_registry=lock.registry, default_branch=destination_branch, clock=partial(datetime.now, UTC)
    )
    repository_merge_dispatcher = RepositoryMergeDispatcher(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        workflow=workflow,
        state=delivery_state,
        sleep=asyncio.sleep,
        logger=logger,
    )
    schema_update_coordinator = SchemaUpdateCoordinator(
        db=db,
        schema_manager=registry.schema,
        rollbacker=GraphRollbacker(db=db),
        workflow=workflow,
        logger=logger,
    )
    rollback_handler = MergeRollbackHandler(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_merger=diff_merger,
        merge_write_blocker=merge_write_blocker,
        schema_manager=registry.schema,
        logger=logger,
    )
    post_merge_dispatcher = PostMergeDispatcher(
        repository_merge_dispatcher=repository_merge_dispatcher,
        workflow=workflow,
        event_service=event_service,
        default_branch=destination_branch,
        python_resolver=await build_python_target_resolver(db=db),
        barrier=await build_regeneration_barrier(state=delivery_state, default_branch_name=destination_branch.name),
        logger=logger,
    )

    return BranchMergeOrchestrator(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        graph_merger=graph_merger,
        schema_analyzer=schema_analyzer,
        schema_manager=registry.schema,
        schema_update_coordinator=schema_update_coordinator,
        rollback_handler=rollback_handler,
        post_merge_dispatcher=post_merge_dispatcher,
        merge_write_blocker=merge_write_blocker,
        ipam_diff_parser=ipam_diff_parser,
        diff_repository=diff_repository,
        diff_serializer=diff_summary_serializer,
        diff_summary_cache=DiffSummaryCache(
            cache=cache, serializer=diff_summary_serializer, key_namespace="branch_merge"
        ),
        logger=logger,
    )


async def build_regeneration_barrier(*, state: DeliveryStatePort, default_branch_name: str) -> RegenerationBarrier:
    return RegenerationBarrier(
        state=state,
        narrowed=NarrowedHoldCache(
            cache=await get_cache(), ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES
        ),
        default_branch_name=default_branch_name,
        sleep=asyncio.sleep,
    )


async def build_default_branch_barrier(*, db: InfrahubDatabase) -> RegenerationBarrier:
    """Wire the barrier with a delivery state that reads through `db`."""
    default_branch = registry.get_branch_from_registry()
    return await build_regeneration_barrier(
        state=WritebackIntentStore(
            db=db, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
        ),
        default_branch_name=default_branch.name,
    )


async def build_post_merge_regeneration_dispatcher(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    barrier: RegenerationBarrier,
    workflow: InfrahubWorkflow,
    log: Logger | LoggerAdapter[Logger],
) -> PostMergeRegenerationDispatcher:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    output_capturer = GeneratorTrackingGroupDiffCapturer(
        diff_coordinator=diff_coordinator,
        diff_repository=diff_repository,
        serializer=DiffSummarySerializer(),
        client=get_client(),
        branch=branch,
    )
    generator_output = GeneratorCascadeOutput(capturer=output_capturer)
    return PostMergeRegenerationDispatcher(
        workflow=workflow,
        planner=build_merge_selective_regeneration(
            db=db, client=get_client(), log=log, generator_output=generator_output
        ),
        summary_cache=DiffSummaryCache(
            cache=await get_cache(), serializer=DiffSummarySerializer(), key_namespace="branch_merge"
        ),
        barrier=barrier,
        log=log,
    )


async def build_held_regeneration_releaser(
    *,
    db: InfrahubDatabase,
    state: DeliveryStatePort,
    default_branch: Branch,
    context: InfrahubContext,
    log: Logger | LoggerAdapter[Logger],
) -> HeldRegenerationReleaser:
    """Wire the release of the regeneration held for a repository, which dispatches on the default branch only."""
    client = get_client()
    workflow = get_workflow()
    barrier = await build_regeneration_barrier(state=state, default_branch_name=default_branch.name)
    gate = DefinitionGate(log=log)
    impacted_resolver = FieldLevelImpactResolver(db=db, client=client)
    return HeldRegenerationReleaser(
        dispatcher=await build_post_merge_regeneration_dispatcher(
            db=db, branch=default_branch, barrier=barrier, workflow=workflow, log=log
        ),
        python_submitter=CoalescedRecomputeSubmitter(workflow=workflow),
        definitions=HeldDefinitionResolver(
            artifact_selector=ArtifactSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log),
            generator_selector=GeneratorSelector(
                client=client, gate=gate, impacted_resolver=impacted_resolver, log=log
            ),
            client=client,
            schema_manager=registry.schema,
        ),
        narrowed=barrier.narrowed,
        default_branch_name=default_branch.name,
        context=context,
    )
