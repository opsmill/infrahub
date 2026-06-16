from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub import config
from infrahub.core.constants import MutationAction
from infrahub.events.branch_action import BranchMergedEvent
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.events.node_action import get_node_event
from infrahub.log import get_logger
from infrahub.workflows.catalogue import (
    BRANCH_CANCEL_PROPOSED_CHANGES,
    BRANCH_DELETE,
    BRANCH_MERGE_POST_PROCESS,
    IPAM_RECONCILIATION,
)

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.changelog.models import NodeChangelog
    from infrahub.core.constants import DiffAction
    from infrahub.core.diff.ipam_diff_parser import IpamNodeDetails
    from infrahub.log import InfrahubLogger
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.workflows.models import WorkflowDefinition

    from .repository_merge_dispatcher import RepositoryMergeDispatcher


class PostMergeDispatcher:
    """Run the post-MERGED follow-ups and dispatch the merge events once a merge has committed.

    Follow-ups run after the merge is irreversibly committed, so a single failing submission must not
    abort the remaining ones or surface as a merge failure: each is logged and skipped on error.
    """

    def __init__(
        self,
        repository_merge_dispatcher: RepositoryMergeDispatcher,
        workflow: InfrahubWorkflow,
        event_service: InfrahubEventService,
        default_branch: Branch,
        global_branch: Branch,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.repository_merge_dispatcher = repository_merge_dispatcher
        self.workflow = workflow
        self.event_service = event_service
        self.default_branch = default_branch
        self.global_branch = global_branch
        self.log = logger or get_logger()

    async def run_follow_ups(
        self,
        *,
        branch: Branch,
        context: InfrahubContext,
        proposed_change_id: str | None,
        ipam_node_details: list[IpamNodeDetails] | None,
    ) -> None:
        # The repository merge issues a GraphQL write to the default branch, so it must run after the
        # write block is lifted; while protected it would be rejected as a write to the merging branch.
        try:
            await self.repository_merge_dispatcher.merge_repositories()
        except Exception:
            self.log.exception("Repository merge failed after branch merge committed")

        # Trigger the reconciliation of IPAM data now that the graph merge is complete.
        if ipam_node_details:
            await self._submit_workflow(
                context=context,
                workflow_definition=IPAM_RECONCILIATION,
                parameters={"branch": self.default_branch.name, "ipam_node_details": ipam_node_details},
            )

        await self._submit_workflow(
            context=context,
            workflow_definition=BRANCH_CANCEL_PROPOSED_CHANGES,
            parameters={"branch_name": branch.name},
        )

        if config.SETTINGS.main.delete_branch_after_merge and not branch.is_default:
            await self._submit_workflow(
                context=context,
                workflow_definition=BRANCH_DELETE,
                parameters={"branch": branch.name, "proposed_change_id": proposed_change_id},
            )

        await self._submit_workflow(
            context=context,
            workflow_definition=BRANCH_MERGE_POST_PROCESS,
            parameters={"source_branch": branch.name, "target_branch": self.default_branch.name},
        )

    async def dispatch_events(
        self,
        *,
        branch: Branch,
        proposed_change_id: str | None,
        node_events: Sequence[tuple[DiffAction, NodeChangelog]],
        context: InfrahubContext,
    ) -> None:
        event_context = context.to_event_context()
        merge_event = BranchMergedEvent(
            branch_name=branch.name,
            branch_id=str(branch.get_uuid()),
            proposed_change_id=proposed_change_id,
            meta=EventMeta.from_context(context=event_context, branch=self.global_branch),
        )

        events: list[InfrahubEvent] = [merge_event]
        for action, node_changelog in node_events:
            meta = EventMeta.from_parent(parent=merge_event, branch=self.default_branch)
            node_event_class = get_node_event(MutationAction.from_diff_action(diff_action=action))
            mutate_event = node_event_class(
                kind=node_changelog.node_kind,
                node_id=node_changelog.node_id,
                changelog=node_changelog,
                fields=node_changelog.updated_fields,
                meta=meta,
            )
            events.append(mutate_event)

        for event in events:
            await self.event_service.send(event=event)

    async def _submit_workflow(
        self,
        *,
        context: InfrahubContext,
        workflow_definition: WorkflowDefinition,
        parameters: dict[str, Any],
    ) -> None:
        try:
            await self.workflow.submit_workflow(workflow=workflow_definition, context=context, parameters=parameters)
        except Exception:
            self.log.exception("Failed to enqueue post-merge workflow '%s'", workflow_definition.name)
