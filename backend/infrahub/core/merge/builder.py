from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.registry import registry
from infrahub.core.schema.update_coordinator import SchemaUpdateCoordinator
from infrahub.dependencies.registry import get_component_registry
from infrahub.workers.dependencies import get_cache, get_event_service, get_workflow

from .graph_merger import GraphMerger
from .merge_locker import MergeLocker
from .orchestrator import BranchMergeOrchestrator
from .post_merge import PostMergeDispatcher
from .repository_merge_dispatcher import RepositoryMergeDispatcher
from .rollback_handler import MergeRollbackHandler
from .schema_analyzer import MergeSchemaAnalyzer
from .write_blocker import MergeWriteBlocker

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


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
    merge_write_blocker = MergeWriteBlocker(cache=await get_cache())

    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=source_branch)
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=source_branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=source_branch)
    ipam_diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=source_branch)

    graph_merger = GraphMerger(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_coordinator=diff_coordinator,
        diff_merger=diff_merger,
        diff_repository=diff_repository,
        diff_locker=DiffLocker(),
        logger=logger,
    )
    repository_merge_dispatcher = RepositoryMergeDispatcher(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        workflow=workflow,
        logger=logger,
    )
    schema_analyzer = MergeSchemaAnalyzer(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_repository=diff_repository,
        schema_manager=registry.schema,
    )
    schema_update_coordinator = SchemaUpdateCoordinator(
        db=db, schema_manager=registry.schema, workflow=workflow, logger=logger
    )
    rollback_handler = MergeRollbackHandler(
        db=db, graph_merger=graph_merger, merge_write_blocker=merge_write_blocker, logger=logger
    )
    post_merge_dispatcher = PostMergeDispatcher(
        repository_merge_dispatcher=repository_merge_dispatcher,
        workflow=workflow,
        event_service=event_service,
        default_branch=destination_branch,
        global_branch=registry.get_global_branch(),
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
        merge_locker=MergeLocker(),
        merge_write_blocker=merge_write_blocker,
        ipam_diff_parser=ipam_diff_parser,
        diff_repository=diff_repository,
        logger=logger,
    )
