from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.models import EventMeta
from infrahub.exceptions import ValidationError
from infrahub.workflows.catalogue import BRANCH_CANCEL_PROPOSED_CHANGES, GIT_REPOSITORIES_DELETE_BRANCH

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.core.branch.data_deleter import BranchDataDeleterInterface, BranchDeleteResult, LoggerInterface
    from infrahub.core.branch.models import Branch
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow


class DiffFreezerInterface(Protocol):
    """Interface for freezing diffs."""

    async def freeze_diffs_for_branch(self, branch_name: str) -> None: ...


class BranchDeleteOrchestrator:
    """Delete a branch and do the work that follows from it.

    Holds no database of its own: the deletion is delegated, which is what keeps the ordering and the
    post-delete decisions here testable without one.
    """

    def __init__(
        self,
        data_deleter: BranchDataDeleterInterface,
        diff_freezer: DiffFreezerInterface,
        event_service: InfrahubEventService,
        workflow: InfrahubWorkflow,
        log: LoggerInterface,
        global_branch: Branch,
        delete_git_branch_after_merge: bool,
    ) -> None:
        self.data_deleter = data_deleter
        self.diff_freezer = diff_freezer
        self.event_service = event_service
        self.workflow = workflow
        self.log = log
        self.global_branch = global_branch
        self.delete_git_branch_after_merge = delete_git_branch_after_merge

    async def delete(
        self,
        branch: Branch,
        context: InfrahubContext,
        delete_from_git: bool = False,
        proposed_change_id: str | None = None,
    ) -> BranchDeleteResult:
        """Remove the branch, then cancel its proposed changes, announce it, and drop its Git branch.

        Raises:
            ValidationError: When the branch is the default branch or an internal one.

        """
        # Before the freeze, not after: a refused delete has to leave the branch's diffs alone.
        if branch.is_default:
            raise ValidationError(f"Unable to delete {branch.name} it is the default branch.")
        if branch.is_global:
            raise ValidationError(f"Unable to delete {branch.name} this is an internal branch.")

        # Freezing has to precede the deletion, which takes away the branch name they are found by.
        await self.diff_freezer.freeze_diffs_for_branch(branch_name=branch.name)

        result = await self.data_deleter.delete(branch=branch)

        if result.branch_deleted:
            await self.workflow.submit_workflow(
                workflow=BRANCH_CANCEL_PROPOSED_CHANGES, context=context, parameters={"branch_name": branch.name}
            )
            await self.event_service.send(
                event=BranchDeletedEvent(
                    branch_name=branch.name,
                    branch_id=str(branch.uuid),
                    sync_with_git=branch.sync_with_git,
                    meta=EventMeta.from_context(context=context.to_event_context(), branch=self.global_branch),
                    proposed_change_id=proposed_change_id,
                )
            )
        else:
            # Another attempt removed the branch, so the work above is already its responsibility.
            self.log.info(f"Branch '{branch.name}' was already deleted")

        # Always execute in case concurrent delete process with delete_from_git=False won the delete race.
        if (self.delete_git_branch_after_merge or delete_from_git) and branch.sync_with_git:
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_DELETE_BRANCH, context=context, parameters={"branch": branch.name}
            )

        return result
