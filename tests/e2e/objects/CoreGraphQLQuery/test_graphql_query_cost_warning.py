"""The cost level of a stored GraphQL query in the web UI.

The cost level needs the GraphQL query cost statistics, so the class first runs the statistics refresh in the
task worker of the Docker Compose stack, then creates a stored query on its own branch. The query goes from
the interfaces to their device and back twice, which multiplies the worst-case database rows above the
default limit of 250,000 on the devices and interfaces of the sites slice. The tests check the level through
the API before they check the web UI.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from helpers import generate_random_branch_name, get_data_table_row
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from infrahub_testcontainers.container import InfrahubDockerCompose
    from playwright.async_api import Page

QUERY_NAME = "e2e-interface-device-loop"

HIGH_COST_QUERY = """query e2e_interface_device_loop {
  InfraInterface {
    edges {
      node {
        name { value }
        device {
          node {
            interfaces {
              edges {
                node {
                  name { value }
                  device {
                    node {
                      interfaces { edges { node { name { value } } } }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}"""

STATISTICS_REFRESH_COMMAND = [
    "prefect",
    "deployment",
    "run",
    "graphql-cost-statistics-refresh/graphql-cost-statistics-refresh",
    "--watch",
]


@pytest.fixture(scope="session")
def compose_stack(
    request: pytest.FixtureRequest, infrahub_provisioned_externally: bool
) -> InfrahubDockerCompose | None:
    """The Docker Compose stack the suite started, or None when INFRAHUB_ADDRESS points at another Infrahub."""
    if infrahub_provisioned_externally:
        return None
    return request.getfixturevalue("infrahub_app")


@pytest.fixture(scope="session")
async def query_cost_statistics(compose_stack: InfrahubDockerCompose | None, data_sites: SitesHandle) -> None:
    """Compute the GraphQL query cost statistics of the default branch once its devices and interfaces exist."""
    if compose_stack is None:
        pytest.skip("Running the statistics refresh needs the Docker Compose stack that the suite starts")
    await asyncio.to_thread(
        compose_stack.exec_in_container, command=STATISTICS_REFRESH_COMMAND, service_name="task-worker"
    )


class TestGraphQLQueryCostWarning:
    @pytest.fixture(scope="class")
    async def branch(self, infrahub_client: InfrahubClient, query_cost_statistics: None) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("query-cost")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    @pytest.fixture(scope="class")
    async def high_cost_query(self, infrahub_client: InfrahubClient, branch: str) -> InfrahubNode:
        query = await infrahub_client.create(
            kind="CoreGraphQLQuery", branch=branch, name=QUERY_NAME, query=HIGH_COST_QUERY
        )
        await query.save()
        stored_query = await infrahub_client.get(kind="CoreGraphQLQuery", id=query.id, branch=branch)
        estimate: dict[str, Any] = stored_query.cost_estimate.value
        assert stored_query.cost_level.value == "high", f"Expected the high cost level, got the estimate {estimate}"
        return stored_query

    async def test_details_page_shows_the_high_cost_warning(
        self, admin_page: Page, branch: str, high_cost_query: InfrahubNode
    ) -> None:
        estimate: dict[str, Any] = high_cost_query.cost_estimate.value

        await admin_page.goto(f"/objects/CoreGraphQLQuery/{high_cost_query.id}?branch={branch}")

        warning = admin_page.get_by_test_id("graphql-query-cost-warning")
        await expect(warning).to_be_visible()
        await expect(warning).to_contain_text("High estimated cost")
        await expect(warning).to_contain_text(f"{estimate['worst_case']['database_rows']:,} database rows")
        await expect(warning).to_contain_text(f"{estimate['expected']['database_rows']:,} database rows")
        await expect(warning).to_contain_text(f"{estimate['high_cost_database_rows']:,} database rows")
        await expect(warning).to_contain_text(estimate["costliest_fields"][0]["path"])
        await expect(warning.get_by_role("link", name="How the cost level is estimated")).to_be_visible()

    async def test_list_shows_the_cost_level(
        self, admin_page: Page, branch: str, high_cost_query: InfrahubNode
    ) -> None:
        await admin_page.goto(f"/objects/CoreGraphQLQuery?branch={branch}")

        row = get_data_table_row(admin_page, QUERY_NAME)
        await expect(row.get_by_text("high", exact=True)).to_be_visible()
