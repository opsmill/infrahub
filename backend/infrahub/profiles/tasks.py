from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import PROFILE_REFRESH
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_profile_refresh

if TYPE_CHECKING:
    from infrahub_sdk.node.relationship import RelationshipManager

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
async def objects_profiles_refresh_multiple(branch_name: str, node_ids: list[str]) -> None:
    log = get_run_logger()

    await add_tags(branches=[branch_name])

    for node_id in node_ids:
        log.info(f"Requesting profile refresh for {node_id}")
        await get_workflow().submit_workflow(
            workflow=PROFILE_REFRESH, parameters={"branch_name": branch_name, "node_id": node_id}
        )


@flow(name="profile-refresh-setup", flow_run_name="Setup profile refresh triggers")
async def profile_refresh_setup(
    context: InfrahubContext,  # noqa: ARG001
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
        )  # type: ignore[misc]

        log.info(f"{report.in_use_count} Profile refresh automation configuration completed")


@flow(name="profile-refresh-process", flow_run_name="Process profile refresh for {profile_kind}")
async def profile_refresh_process(
    branch_name: str,
    profile_kind: str,
    profile_id: str,
    context: InfrahubContext,  # noqa: ARG001
) -> None:
    """Process profile refresh when a profile's attributes or relationships change.

    This flow fetches all nodes related to the profile via the `related_nodes`
    relationship and submits profile refresh workflows for each of them.
    """
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name])

    profile = await client.get(kind=profile_kind, ids=[profile_id], branch=branch_name, prefetch_relationships=True)
    related_nodes: RelationshipManager = profile.related_nodes  # type: ignore

    if not related_nodes.peer_ids:
        log.info(f"No related nodes found for profile {profile_id}")
        return

    log.info(f"Found {len(related_nodes.peer_ids)} related nodes for profile {profile_id}")

    for node_id in related_nodes.peer_ids:
        log.info(f"Requesting profile refresh for {node_id}")
        await get_workflow().submit_workflow(
            workflow=PROFILE_REFRESH, parameters={"branch_name": branch_name, "node_id": node_id}
        )
