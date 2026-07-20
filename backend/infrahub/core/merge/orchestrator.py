from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config, lock
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.changelog.diff import DiffChangelogCollector
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.registry import registry
from infrahub.core.schema.update_coordinator import MigrationExecutor
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger

from .rollback_handler import PreMergeState
from .write_blocker import MergeProtectionState

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.diff.summary_cache import DiffSummaryCache
    from infrahub.core.diff.summary_serializer import DiffSummarySerializer
    from infrahub.core.models import SchemaDiff
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.update_coordinator import SchemaUpdateCoordinator
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger

    from .graph_merger import GraphMerger
    from .post_merge import PostMergeDispatcher
    from .rollback_handler import MergeRollbackHandler
    from .schema_analyzer import MergeSchemaAnalyzer
    from .write_blocker import MergeWriteBlocker


class BranchMergeOrchestrator:
    """Drive a branch merge: pre-checks, graph merge, migrations, status transitions, follow-ups."""

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        graph_merger: GraphMerger,
        schema_analyzer: MergeSchemaAnalyzer,
        schema_manager: SchemaManager,
        schema_update_coordinator: SchemaUpdateCoordinator,
        rollback_handler: MergeRollbackHandler,
        post_merge_dispatcher: PostMergeDispatcher,
        merge_write_blocker: MergeWriteBlocker,
        ipam_diff_parser: IpamDiffParser,
        diff_repository: DiffRepository,
        diff_serializer: DiffSummarySerializer,
        diff_summary_cache: DiffSummaryCache,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.graph_merger = graph_merger
        self.schema_analyzer = schema_analyzer
        self.schema_manager = schema_manager
        self.schema_update_coordinator = schema_update_coordinator
        self.rollback_handler = rollback_handler
        self.post_merge_dispatcher = post_merge_dispatcher
        self.merge_write_blocker = merge_write_blocker
        self.ipam_diff_parser = ipam_diff_parser
        self.diff_repository = diff_repository
        self.diff_serializer = diff_serializer
        self.diff_summary_cache = diff_summary_cache
        self.log = logger or get_logger()

    async def merge(self, *, context: InfrahubContext, proposed_change_id: str | None = None) -> None:
        user_id = context.account.account_id

        protection = await self.merge_write_blocker.get()
        if protection is not None and protection.branch != self.source_branch.name:
            raise ValidationError("Cannot merge a branch while a merge is in progress.")

        # Publish the shared write-protection key before any graph write
        await self.merge_write_blocker.set(branch=self.source_branch.name, state=MergeProtectionState.MERGING)

        # The merge timestamp is stamped after the write-protection key is set so that a write
        # slipping in ahead of the block is stamped before merge_at and stays out of the rollback
        # range. Nothing has been written yet, so a failure here only needs to lift the protection.
        try:
            merge_at = Timestamp()
            pre_merge_state = PreMergeState(
                destination_schema=registry.schema.get_schema_branch(name=self.destination_branch.name).duplicate(),
                destination_schema_changed_at=self.destination_branch.schema_changed_at,
                destination_schema_hash=self.destination_branch.schema_hash,
                source_branched_from=self.source_branch.branched_from,
            )
        except BaseException:
            await self.merge_write_blocker.delete()
            raise

        schema_diff: SchemaDiff | None = None
        schema_updated_hash: str | None = None

        try:
            async with lock.registry.global_graph_lock():
                # Record when the merge started so a recovery can roll back from this point.
                self.source_branch.status = BranchStatus.MERGING
                self.source_branch.merge_started_at = merge_at.to_string()
                await self.source_branch.save(db=self.db, user_id=user_id)
                registry.branch[self.source_branch.name] = self.source_branch
                await self.graph_merger.merge(at=merge_at)

            self.log.info("Loading enriched diff for changelog collection")
            branch_diff = await self.diff_repository.get_one(
                diff_branch_name=self.source_branch.name,
                tracking_id=BranchTrackingId(name=self.source_branch.name),
            )
            changelog_collector = DiffChangelogCollector(diff=branch_diff, branch=self.source_branch, db=self.db)
            node_events = changelog_collector.collect_changelogs()

            if await self.schema_analyzer.has_schema_changes():
                self.log.info("Applying schema migrations after merge")
                # Schema nodes were already written by the graph merge; load that post-merge schema
                # and apply only the migrations it implies. Rollback is deferred to the merge handler.
                candidate_schema = await self.schema_manager.load_schema_from_db(
                    db=self.db, branch=self.destination_branch
                )
                # Scope for the post-merge derived-value refresh: what the merge changed on the destination.
                schema_diff = pre_merge_state.destination_schema.diff(other=candidate_schema)
                schema_updated_hash = candidate_schema.get_hash()
                migrations = await self.schema_analyzer.calculate_migrations(target_schema=candidate_schema)
                await self.schema_update_coordinator.execute(
                    branch=self.destination_branch,
                    origin_schema=pre_merge_state.destination_schema,
                    candidate_schema=candidate_schema,
                    at=merge_at,
                    context=context,
                    migration_executor=MigrationExecutor.WORKFLOW,
                    migrations=migrations,
                    update_db=False,
                    update_registry=True,
                    user_id=user_id,
                    manage_rollback=False,
                )

            # Compute the IPAM reconciliation details while the diff is still live. Submission is
            # deferred until after the MERGED transition because recovery cannot completely roll back
            # the changes made during reconciliation.
            ipam_node_details = await self.ipam_diff_parser.get_changed_ipam_node_details(
                source_branch_name=self.source_branch.name,
                target_branch_name=self.destination_branch.name,
            )
        except BaseException as exc:
            self.log.error("Merge failed, beginning rollback", extra={"error": str(exc)})
            await self.rollback_handler.rollback(
                merge_started_at=merge_at,
                pre_merge_state=pre_merge_state,
                user_id=user_id,
            )
            raise

        # Failing to update diffs must not fail the merge or trigger a rollback of correct data.
        try:
            await self.diff_repository.mark_tracking_ids_merged(
                tracking_ids=[BranchTrackingId(name=self.source_branch.name)]
            )
            await self.diff_repository.freeze_diffs_for_branch(branch_name=self.source_branch.name)
        except Exception:
            self.log.exception("Diff finalization failed after merge; merge is committed, continuing")

        # Point of no return: merge fully succeeded. Advance to MERGED.
        self.source_branch.status = BranchStatus.MERGED
        await self.source_branch.save(db=self.db, user_id=user_id)
        registry.branch[self.source_branch.name] = self.source_branch

        # Lift the write protection now that the merge has fully succeeded.
        await self.merge_write_blocker.delete()

        # Persisted only past the point of no return, so a rolled-back merge leaves no entry behind.
        merge_diff_cache_key = await self._cache_diff_summary(branch_diff=branch_diff)

        await self.post_merge_dispatcher.run_follow_ups(
            branch=self.source_branch,
            context=context,
            proposed_change_id=proposed_change_id,
            ipam_node_details=ipam_node_details,
            merge_diff_cache_key=merge_diff_cache_key,
        )

        await self.post_merge_dispatcher.dispatch_events(
            branch=self.source_branch,
            proposed_change_id=proposed_change_id,
            node_events=node_events,
            context=context,
            schema_diff=schema_diff,
            schema_hash=schema_updated_hash,
        )

    async def _cache_diff_summary(self, branch_diff: EnrichedDiffRoot) -> str | None:
        """Serialize the merge diff and persist its summary to the cache, returning the cache key.

        Returns None when selective execution is disabled, or when serialization or the cache write fails.
        """
        if not config.SETTINGS.main.selective_execution_after_merge:
            return None
        try:
            diff_summary = self.diff_serializer.serialize(
                root=branch_diff, target_branch_name=self.destination_branch.name
            )
        except Exception:
            self.log.exception("Failed to serialize merge diff summary; falling back to full regeneration")
            return None
        try:
            await self.diff_summary_cache.set(diff_id=branch_diff.uuid, diff_summary=diff_summary)
            return branch_diff.uuid
        except Exception:
            self.log.exception("Failed to cache merge diff summary; falling back to full regeneration")
            return None
