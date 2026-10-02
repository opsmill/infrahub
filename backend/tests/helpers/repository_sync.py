"""Drive the repository add and synchronization flows against a local remote and read what they recorded."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from infrahub_sdk.uuidt import UUIDT
from prefect.client.schemas.objects import State
from prefect.flow_engine import run_flow_async

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, RepositoryOperationalStatus
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.git.models import GitRepositoryAdd
from infrahub.git.tasks import add_git_repository, sync_git_repo_with_origin_and_tag_on_failure
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from uuid import UUID

    import pytest
    from infrahub_sdk import InfrahubClient
    from prefect import Flow
    from prefect.client.orchestration import PrefectClient

    from infrahub.database import InfrahubDatabase

FLOW_RUN_LOGGER = "prefect.flow_runs"
SKIPPED_BRANCH_WARNING_PREFIX = "Skipped remote branch"


def skipped_branch_warning(*, branch_name: str, repository_name: str, default_branch: str) -> str:
    return (
        f"Skipped remote branch '{branch_name}' of repository {repository_name}: its name collides with the "
        f"Infrahub default branch, which is mapped to this repository's default branch '{default_branch}'."
    )


async def create_repository_node(
    db: InfrahubDatabase, name: str, location: str, default_branch: str, operational_status: str
) -> Node:
    node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await node.new(
        db=db,
        name=name,
        location=location,
        default_branch=default_branch,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        operational_status=operational_status,
    )
    await node.save(db=db)
    return node


async def run_add_flow(node: Node, name: str, location: str) -> State:
    model = GitRepositoryAdd(
        location=location,
        repository_id=node.id,
        repository_name=name,
        infrahub_branch_name=registry.default_branch,
        infrahub_branch_id=str(UUIDT()),
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    return await run_flow_for_state(add_git_repository, parameters={"model": model})


async def run_sync_flow(
    client: InfrahubClient,
    repository_id: str,
    name: str,
    location: str,
    operational_status: str = RepositoryOperationalStatus.ONLINE.value,
) -> State:
    return await run_flow_for_state(
        sync_git_repo_with_origin_and_tag_on_failure,
        parameters={
            "client": client,
            "repository_id": repository_id,
            "repository_name": name,
            "repository_location": location,
            "operational_status": operational_status,
            "infrahub_branch": registry.default_branch,
        },
    )


async def run_flow_for_state(flow: Flow[..., Any], parameters: dict[str, Any]) -> State:
    """Run a flow to completion and return its final state rather than raising its failure.

    Raises:
        TypeError: When the engine returns something other than a state.

    """
    state = await run_flow_async(flow=flow, parameters=parameters, return_type="state")
    if not isinstance(state, State):
        raise TypeError(f"Expected the final state of flow {flow.name}, got {state!r}")
    return state


def flow_run_id_of(state: State) -> UUID:
    """Return the id of the flow run the state belongs to.

    Raises:
        ValueError: When the state belongs to no flow run.

    """
    flow_run_id = state.state_details.flow_run_id
    if flow_run_id is None:
        raise ValueError("The state does not belong to a flow run")
    return flow_run_id


def skipped_branch_warnings(caplog: pytest.LogCaptureFixture, state: State) -> list[str]:
    """Return the skipped-branch warnings the flow run sent to its run log, in order.

    The records are read where the flow's run logger emits them, which is what the task log is fed
    from, so the capture has to be at WARNING or below on the flow-run logger.
    """
    flow_run_id = str(flow_run_id_of(state))
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == FLOW_RUN_LOGGER
        and record.levelno == logging.WARNING
        and vars(record).get("flow_run_id") == flow_run_id
        and record.getMessage().startswith(SKIPPED_BRANCH_WARNING_PREFIX)
    ]


async def flow_run_tags(prefect_client: PrefectClient, state: State) -> set[str]:
    flow_run = await prefect_client.read_flow_run(flow_run_id_of(state))
    return set(flow_run.tags)


async def is_linked_to_node(prefect_client: PrefectClient, state: State, node_id: str) -> bool:
    return WorkflowTag.RELATED_NODE.render(identifier=node_id) in await flow_run_tags(prefect_client, state)
