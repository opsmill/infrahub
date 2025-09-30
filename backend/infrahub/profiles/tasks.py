from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.workers.dependencies import get_client, get_workflow
from infrahub.workflows.catalogue import PROFILE_REFRESH
from infrahub.workflows.utils import add_tags

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


@flow(
    name="object-profiles-refresh",
    flow_run_name="Refresh profiles for {node_id}",
)
async def object_profiles_refresh(
    branch_name: str,
    node_id: str,
) -> None:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name], nodes=[node_id], db_change=True)
    await client.execute_graphql(
        query=REFRESH_PROFILES_MUTATION,
        variables={"id": node_id},
        branch_name=branch_name,
    )
    log.info(f"Profiles refreshed for {node_id}")


@flow(
    name="objects-profiles-refresh-multiple",
    flow_run_name="Refresh profiles for multiple objects",
)
async def objects_profiles_refresh_multiple(
    branch_name: str,
    node_ids: list[str],
) -> None:
    log = get_run_logger()

    await add_tags(branches=[branch_name])

    for node_id in node_ids:
        log.info(f"Requesting profile refresh for {node_id}")
        await get_workflow().submit_workflow(
            workflow=PROFILE_REFRESH,
            parameters={
                "branch_name": branch_name,
                "node_id": node_id,
            },
        )
