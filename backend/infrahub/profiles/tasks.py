from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import GraphQLError
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.exceptions import ProfileRefreshError
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_profile_refresh
from .graphql_queries import ProfileNodeIDQuery
from .submission import submit_profile_refresh

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

REFRESH_PROFILES_MUTATION = """
mutation RefreshProfiles(
    $id: String!,
  ) {
  InfrahubProfilesRefresh(
    data: {id: $id}
  ) {
    ok
  }
}
"""


async def _refresh_node_profiles(client: InfrahubClient, branch_name: str, node_id: str) -> None:
    await client.execute_graphql(query=REFRESH_PROFILES_MUTATION, variables={"id": node_id}, branch_name=branch_name)


@flow(name="object-profiles-refresh", flow_run_name="Refresh profiles for {node_id}")
async def object_profiles_refresh(branch_name: str, node_id: str) -> None:
    """Refresh the profiles of one node.

    No code submits this flow. It stays registered so that the runs queued before an upgrade can still finish.
    """
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name], nodes=[node_id], db_change=True)
    await _refresh_node_profiles(client=client, branch_name=branch_name, node_id=node_id)
    log.info(f"Profiles refreshed for {node_id}")


@flow(name="objects-profiles-refresh-multiple", flow_run_name="Refresh profiles for multiple objects")
async def objects_profiles_refresh_multiple(
    branch_name: str,
    node_ids: list[str],
    # None lets the runs queued before an upgrade, which carry no context, still start.
    context: EventContext | None = None,
) -> None:
    """Refresh the profiles of a chunk of nodes, one node after the other.

    Raises:
        ProfileRefreshError: If the refresh of one or more nodes returns a GraphQL error, after the refresh of
            all the other nodes of the chunk.

    """
    log = get_run_logger()
    client = get_client()
    if context is not None:
        client.request_context = context.to_request_context()

    failed_node_ids: list[str] = []
    for node_id in node_ids:
        try:
            await _refresh_node_profiles(client=client, branch_name=branch_name, node_id=node_id)
        except GraphQLError as exc:
            log.warning(f"Profile refresh failed for {node_id}: {exc.errors}")
            failed_node_ids.append(node_id)

    log.info(f"Profiles refreshed for {len(node_ids) - len(failed_node_ids)} of {len(node_ids)} nodes")
    if failed_node_ids:
        raise ProfileRefreshError(node_ids=failed_node_ids)


@flow(name="profile-refresh-setup", flow_run_name="Setup profile refresh triggers")
async def profile_refresh_setup(
    context: EventContext,  # noqa: ARG001
    branch_name: str | None = None,
    event_name: str | None = None,  # noqa: ARG001
) -> None:
    """Setup Prefect automations for profile refresh triggers.

    This flow is triggered by schema changes and sets up automations that will
    listen for profile updates. When a profile's attributes or relationships
    change, the corresponding automation will trigger profile refresh for all
    related nodes.
    """
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_profile_refresh, trigger_type=TriggerType.PROFILE
        )

        log.info(f"{report.in_use_count} Profile refresh automation configuration completed")


@flow(name="profile-refresh-process", flow_run_name="Process profile refresh for {profile_kind}")
async def profile_refresh_process(
    branch_name: str,
    profile_kind: str,
    profile_id: str,
    context: EventContext,
) -> None:
    """Process profile refresh when a profile's attributes or relationships change.

    This flow reads the ids of the nodes and templates linked to the profile in pages, and submits
    one profile refresh flow for each chunk of ids.
    """
    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    await add_tags(branches=[branch_name])

    profile_schema = await client.schema.get(kind=profile_kind, branch=branch_name)
    peer_kinds = [profile_schema.get_relationship(name="related_nodes").peer]
    if related_templates := profile_schema.get_relationship_or_none(name="related_templates"):
        peer_kinds.append(related_templates.peer)

    workflow = get_workflow()
    chunk_size = get_submission_chunk_size()
    for peer_kind in peer_kinds:
        node_query = ProfileNodeIDQuery(kind=peer_kind, profile_id=profile_id)
        submitted = 0
        async for node_ids in node_query.fetch_all_chunked(
            client=client, branch_name=branch_name, chunk_size=chunk_size
        ):
            await submit_profile_refresh(
                workflow=workflow, branch_name=branch_name, node_ids=node_ids, context=context, profile_id=profile_id
            )
            submitted += len(node_ids)
        log.info(f"Submitted the profile refresh of {submitted} {peer_kind} node(s) for profile {profile_id}")
