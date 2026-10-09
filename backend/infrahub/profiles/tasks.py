from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.recompute.dispatch import build_recompute_chain
from infrahub.core.registry import registry
from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.exceptions import BranchNotFoundError, ProfileRefreshError
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_event_service, get_workflow
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_profile_refresh
from .graphql_queries import ProfileNodeIDQuery
from .node_applier import ChunkProfilesApplier
from .refresh import NodeProfilesRefresher
from .submission import submit_profile_refresh

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


@flow(name="object-profiles-refresh", flow_run_name="Refresh profiles for {node_id}")
async def object_profiles_refresh(branch_name: str, node_id: str) -> None:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name], nodes=[node_id], db_change=True)
    await client.execute_graphql(query=REFRESH_PROFILES_MUTATION, variables={"id": node_id}, branch_name=branch_name)
    log.info(f"Profiles refreshed for {node_id}")


@flow(name="objects-profiles-refresh-multiple", flow_run_name="Refresh profiles for multiple objects")
async def objects_profiles_refresh_multiple(
    branch_name: str,
    node_ids: list[str],
    context: EventContext | None = None,
) -> None:
    """Refresh the profiles of a chunk of nodes and templates, then recompute the values that read them.

    Raises:
        ProfileRefreshError: If the refresh of one or more nodes fails, after the refresh of all the other
            nodes of the chunk.

    """
    log = get_run_logger()
    database = await get_database()
    try:
        branch = await registry.get_branch(db=database, branch=branch_name)
    except BranchNotFoundError:
        log.info(f"Branch {branch_name} does not exist, no profile to refresh")
        return

    event_context = context or EventContext(
        branch=EventBranchContext(name=branch.name, id=str(branch.uuid)), account_id=SYSTEM_USER_ID
    )
    schema_name = branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    refresher = NodeProfilesRefresher(
        db=database,
        event_service=await get_event_service(),
        chain=await build_recompute_chain(
            schema_branch=registry.schema.get_schema_branch(name=schema_name), db=database
        ),
        applier_class=ChunkProfilesApplier,
    )
    failed_node_ids = await refresher.refresh(branch=branch, node_ids=node_ids, context=event_context)

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
