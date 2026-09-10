from uuid import uuid4

import pytest

from infrahub.auth.session import AccountSession, AnonymousSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDeleteResult
from infrahub.core.branch.delete_coordinator import BranchDeleteOrchestrator
from infrahub.core.constants import GLOBAL_BRANCH_NAME, SYSTEM_USER_ID
from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.workflows.catalogue import BRANCH_CANCEL_PROPOSED_CHANGES, GIT_REPOSITORIES_DELETE_BRANCH
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.log import FakeLogger
from tests.adapters.workflow import WorkflowRecorder


class RecordingDataDeleter:
    """Reports a fixed outcome and remembers which branches it was asked to delete, and on whose behalf."""

    def __init__(self, result: BranchDeleteResult) -> None:
        self.result = result
        self.deleted: list[str] = []
        self.actors: list[str] = []

    async def delete(self, branch: Branch, user_id: str = SYSTEM_USER_ID) -> BranchDeleteResult:
        self.deleted.append(branch.name)
        self.actors.append(user_id)
        return self.result


class RecordingDiffFreezer:
    def __init__(self) -> None:
        self.frozen: list[str] = []

    async def freeze_diffs_for_branch(self, branch_name: str) -> None:
        self.frozen.append(branch_name)


@pytest.fixture
def context() -> InfrahubContext:
    return InfrahubContext(
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        branch=BranchContext(name="main", id="placeholder"),
    )


def _build(
    *,
    branch_deleted: bool,
    delete_git_branch_after_merge: bool = False,
) -> tuple[
    BranchDeleteOrchestrator,
    RecordingDataDeleter,
    RecordingDiffFreezer,
    WorkflowRecorder,
    MemoryInfrahubEvent,
    FakeLogger,
]:
    data_deleter = RecordingDataDeleter(
        result=BranchDeleteResult(branch_deleted=branch_deleted, edges_removed=7 if branch_deleted else 0)
    )
    diff_freezer = RecordingDiffFreezer()
    workflow = WorkflowRecorder()
    events = MemoryInfrahubEvent()
    log = FakeLogger()
    orchestrator = BranchDeleteOrchestrator(
        data_deleter=data_deleter,
        diff_freezer=diff_freezer,
        event_service=events,
        workflow=workflow,
        log=log,
        global_branch=Branch(name=GLOBAL_BRANCH_NAME, is_global=True, uuid=uuid4()),
        delete_git_branch_after_merge=delete_git_branch_after_merge,
    )
    return orchestrator, data_deleter, diff_freezer, workflow, events, log


def _branch(name: str = "some-branch", sync_with_git: bool = True) -> Branch:
    return Branch(name=name, sync_with_git=sync_with_git, uuid=uuid4())


async def test_delete_runs_post_delete_work(context: InfrahubContext) -> None:
    """The attempt that removes the branch cancels its proposed changes and announces it."""
    orchestrator, data_deleter, diff_freezer, workflow, events, _ = _build(branch_deleted=True)
    branch = _branch()

    result = await orchestrator.delete(branch=branch, context=context, delete_from_git=True)

    assert result == BranchDeleteResult(branch_deleted=True, edges_removed=7)
    # The diffs are frozen before the delete, since they are found by a branch name it takes away.
    assert diff_freezer.frozen == [branch.name]
    assert data_deleter.deleted == [branch.name]
    assert [type(event) for event in events.events] == [BranchDeletedEvent]
    assert [call["parameters"] for call in workflow.get_submit_calls_for(BRANCH_CANCEL_PROPOSED_CHANGES)] == [
        {"branch_name": branch.name}
    ]
    assert [call["parameters"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_DELETE_BRANCH)] == [
        {"branch": branch.name}
    ]


async def test_delete_names_the_requesting_account_to_the_data_deleter(context: InfrahubContext) -> None:
    """The delete's actor comes from the request context, so the edges it closes name a real account."""
    orchestrator, data_deleter, _, _, _, _ = _build(branch_deleted=True)

    await orchestrator.delete(branch=_branch(), context=context)

    assert data_deleter.actors == [context.account.account_id]
    assert data_deleter.actors != [SYSTEM_USER_ID]


async def test_delete_names_the_system_actor_when_the_request_has_no_account() -> None:
    """An anonymous context carries no account id, and an empty actor is not a name."""
    orchestrator, data_deleter, _, _, _, _ = _build(branch_deleted=True)
    anonymous = InfrahubContext(account=AnonymousSession(), branch=BranchContext(name="main", id="placeholder"))

    await orchestrator.delete(branch=_branch(), context=anonymous)

    assert data_deleter.actors == [SYSTEM_USER_ID]


async def test_delete_skips_post_delete_work_when_another_attempt_won(context: InfrahubContext) -> None:
    """An attempt that removed nothing must not repeat what belongs to the one that did."""
    orchestrator, _, _, workflow, events, log = _build(branch_deleted=False)
    branch = _branch()

    result = await orchestrator.delete(branch=branch, context=context, delete_from_git=False)

    assert result.branch_deleted is False
    assert events.events == []
    assert workflow.submit_calls == []
    assert log.info_logs == [f"Branch '{branch.name}' was already deleted"]


async def test_delete_from_git_survives_losing_the_race(context: InfrahubContext) -> None:
    """The attempt that won may not have been asked to remove the Git branch."""
    orchestrator, _, _, workflow, events, _ = _build(branch_deleted=False)
    branch = _branch()

    await orchestrator.delete(branch=branch, context=context, delete_from_git=True)

    assert [call["parameters"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_DELETE_BRANCH)] == [
        {"branch": branch.name}
    ]
    # Still nothing that belongs to the winning attempt.
    assert events.events == []
    assert workflow.get_submit_calls_for(BRANCH_CANCEL_PROPOSED_CHANGES) == []


async def test_delete_from_git_is_ignored_for_a_branch_that_does_not_track_git(context: InfrahubContext) -> None:
    orchestrator, _, _, workflow, events, _ = _build(branch_deleted=True)
    branch = _branch(sync_with_git=False)

    await orchestrator.delete(branch=branch, context=context, delete_from_git=True)

    assert workflow.get_submit_calls_for(GIT_REPOSITORIES_DELETE_BRANCH) == []
    # The rest of the post-delete work still ran.
    assert [type(event) for event in events.events] == [BranchDeletedEvent]


async def test_delete_git_branch_after_merge_setting_deletes_without_an_explicit_request(
    context: InfrahubContext,
) -> None:
    orchestrator, _, _, workflow, _, _ = _build(branch_deleted=True, delete_git_branch_after_merge=True)
    branch = _branch()

    await orchestrator.delete(branch=branch, context=context, delete_from_git=False)

    assert [call["parameters"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_DELETE_BRANCH)] == [
        {"branch": branch.name}
    ]
