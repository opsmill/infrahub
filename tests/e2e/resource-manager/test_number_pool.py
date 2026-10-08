"""Port of frontend/app/tests/e2e/resource-manager/number-pool.spec.ts.

Creates number pools for a generic schema and for a node schema, verifies a pool's details,
confirms the edit form shows the node and attribute as read-only text, opens the number-pool
attribute-kind page, then creates an InterfaceL3 that allocates from a pool and verifies the pool
assignment.

Each test runs on its own branch; a test that needs an existing pool creates it through the SDK.
Depends on data_sites (the atl1-core1 device); the InterfaceL3 schema and the InfraService number
pool come from the schema, not the data.
"""

from __future__ import annotations

import contextlib
import re
import secrets
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Locator, Page

SERVICE_POOL = "InfraService.service_identifier"


def unique_pool_name(prefix: str) -> str:
    # Number pools are branch-agnostic, so a fixed name collides with the same pool created by another test.
    return f"{prefix} {secrets.token_hex(3)}"


def allocates_block(page: Page) -> Locator:
    return page.get_by_role("group", name="What it allocates")


def range_input(page: Page, label: str, row: int) -> Locator:
    return page.get_by_role("textbox", name=f"{label}, range {row}", exact=True)


async def create_number_pool(
    client: InfrahubClient, branch: str, name: str, node: str, bounds: tuple[int, int]
) -> None:
    pool = await client.create(
        kind="CoreNumberPool",
        branch=branch,
        name=name,
        node=node,
        node_attribute="speed",
        start_range=bounds[0],
        end_range=bounds[1],
    )
    await pool.save()


class TestNumberPool:
    @pytest.fixture
    async def number_pool_branch(
        self, infrahub_client: InfrahubClient, data_sites: SitesHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("number-pool")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    @pytest.fixture
    async def generic_pool(self, infrahub_client: InfrahubClient, number_pool_branch: str) -> str:
        name = unique_pool_name("number pool test for generic")
        await create_number_pool(infrahub_client, number_pool_branch, name, "InfraInterface", (1, 10))
        return name

    @pytest.fixture
    async def node_pool(self, infrahub_client: InfrahubClient, number_pool_branch: str) -> str:
        name = unique_pool_name("number pool test for node")
        await create_number_pool(infrahub_client, number_pool_branch, name, "InfraInterfaceL3", (11, 20))
        return name

    async def test_create_number_pool_for_generic_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await expect(admin_page.get_by_text("Name *")).to_be_visible()
        await admin_page.get_by_label("Name *").fill(unique_pool_name("number pool test for generic"))
        await admin_page.get_by_label("Node *").click()
        await expect(admin_page.get_by_role("option", name="Interface Infra", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("option", name="Artifact Check Core", exact=True)).to_be_visible()
        await admin_page.get_by_role("option", name="Interface Infra", exact=True).click()
        await admin_page.get_by_label("Attribute *", exact=True).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await range_input(admin_page, "Start", 1).fill("1")
        await range_input(admin_page, "End", 1).fill("10")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_create_number_pool_for_node_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill(unique_pool_name("number pool test for node"))
        await admin_page.get_by_label("Node *").click()
        await admin_page.get_by_role("option", name="Interface L3 Infra", exact=True).click()
        await admin_page.get_by_label("Attribute *", exact=True).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await range_input(admin_page, "Start", 1).fill("11")
        await range_input(admin_page, "End", 1).fill("20")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_displays_correct_details_for_created_number_pool(
        self, admin_page: Page, number_pool_branch: str, generic_pool: str
    ) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name=generic_pool).click()
        await admin_page.get_by_role("cell", name=generic_pool).first.click()
        await expect(admin_page.get_by_role("cell", name="speed")).to_be_visible()
        await expect(admin_page.get_by_role("cell", name="1", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("cell", name="10", exact=True)).to_be_visible()

    async def test_update_form_should_not_include_node_and_attribute_selects(
        self, admin_page: Page, number_pool_branch: str, generic_pool: str
    ) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name=generic_pool).click()
        await admin_page.get_by_test_id("edit-button").click()
        allocates = allocates_block(admin_page)
        await expect(allocates).to_contain_text("Interface")
        await expect(allocates).to_contain_text("Speed")
        await expect(allocates.get_by_role("combobox")).to_have_count(0)
        await expect(admin_page.get_by_text("Node *")).not_to_be_visible()
        await expect(admin_page.get_by_text("Attribute *")).not_to_be_visible()

    async def test_number_pool_attribute_kind_resource_manager(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        service_pool = admin_page.get_by_test_id("object-items").get_by_role("link", name=SERVICE_POOL)
        await expect(service_pool).to_be_visible()
        await service_pool.click()
        await admin_page.get_by_role("link", name="View", exact=True).click()
        await save_screenshot_for_docs(admin_page, "numberpool_attribute_kind_resource_manager")

    async def test_create_node_using_number_pool_and_verify_pool_assignment(
        self, admin_page: Page, number_pool_branch: str, generic_pool: str, node_pool: str
    ) -> None:
        # Navigate to interface creation page
        await admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        # Fill in interface details
        await admin_page.get_by_role("combobox", name="Device *").click()
        await admin_page.get_by_role("option", name="atl1-core1").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test interface with pool")

        # Select number pool
        await admin_page.get_by_role("tab", name="From pool").click()
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await expect(admin_page.get_by_role("option", name=generic_pool)).to_be_visible()
        await expect(admin_page.get_by_role("option", name=node_pool)).to_be_visible()
        await admin_page.get_by_role("option", name=generic_pool).click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()

        # Save interface
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InterfaceL3 created")).to_be_visible()

        # Verify pool assignment
        await admin_page.get_by_role("searchbox", name="Search").fill("interface with pool")
        await admin_page.get_by_role("link", name="test interface with pool").click()
        await admin_page.get_by_text("Speed1").get_by_test_id("view-metadata-button").click()
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name=generic_pool)
        ).to_be_visible()


RANGES_QUERY = """
query ($name: String!) {
  CoreNumberPool(name__value: $name) {
    edges { node { ranges { edges { node {
      start { value } end { value } allocation_weight { value }
    } } } } }
  }
}
"""


async def get_pool_ranges(client: InfrahubClient, branch: str, pool_name: str) -> list[tuple[int, int, int | None]]:
    response = await client.execute_graphql(query=RANGES_QUERY, variables={"name": pool_name}, branch_name=branch)
    (pool,) = response["CoreNumberPool"]["edges"]
    return sorted(
        (
            edge["node"]["start"]["value"],
            edge["node"]["end"]["value"],
            edge["node"]["allocation_weight"]["value"],
        )
        for edge in pool["node"]["ranges"]["edges"]
    )


class TestNumberPoolRanges:
    @pytest.fixture
    async def ranges_branch(self, infrahub_client: InfrahubClient) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("number-pool-ranges")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_pool_with_several_ranges_then_edit(
        self, admin_page: Page, infrahub_client: InfrahubClient, ranges_branch: str
    ) -> None:
        pool_name = unique_pool_name("multi range pool")
        await admin_page.goto(f"/resource-manager?branch={ranges_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill(pool_name)
        await admin_page.get_by_label("Node *").click()
        await admin_page.get_by_role("option", name="Interface L3 Infra", exact=True).click()
        await admin_page.get_by_label("Attribute *", exact=True).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await range_input(admin_page, "Start", 1).fill("100")
        await range_input(admin_page, "End", 1).fill("199")
        await range_input(admin_page, "Weight", 1).fill("10")
        await admin_page.get_by_role("button", name="Add range").click()
        await range_input(admin_page, "Start", 2).fill("300")
        await range_input(admin_page, "End", 2).fill("399")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()
        assert await get_pool_ranges(infrahub_client, ranges_branch, pool_name) == [
            (100, 199, 10),
            (300, 399, None),
        ]

        await admin_page.goto(f"/resource-manager?branch={ranges_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name=pool_name).click()
        await admin_page.get_by_test_id("edit-button").click()
        await expect(range_input(admin_page, "Start", 1)).to_have_value("100")
        await expect(range_input(admin_page, "Start", 2)).to_have_value("300")
        await expect(range_input(admin_page, "Start", 3)).to_have_count(0)
        await admin_page.get_by_role("button", name="Remove range 1", exact=True).click()
        await expect(range_input(admin_page, "Start", 1)).to_have_value("300")
        await expect(range_input(admin_page, "Start", 2)).to_have_count(0)
        await range_input(admin_page, "Weight", 1).fill("5")
        await admin_page.get_by_role("button", name="Add range").click()
        await range_input(admin_page, "Start", 2).fill("500")
        await range_input(admin_page, "End", 2).fill("599")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool updated")).to_be_visible()
        assert await get_pool_ranges(infrahub_client, ranges_branch, pool_name) == [
            (300, 399, 5),
            (500, 599, None),
        ]

    async def test_schema_defined_pool_ranges_are_read_only(self, admin_page: Page, ranges_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={ranges_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name=SERVICE_POOL).click()
        await admin_page.get_by_test_id("edit-button").click()

        await expect(
            admin_page.get_by_text(
                "These ranges come from the schema. To change them, update the schema on the default branch."
            )
        ).to_be_visible()
        await expect(admin_page.get_by_text("100 – 10,000")).to_be_visible()
        await expect(admin_page.get_by_role("textbox", name=re.compile(r"^Start, range \d+$"))).to_have_count(0)
        await expect(admin_page.get_by_role("button", name="Add range")).to_have_count(0)

        await admin_page.get_by_label("Description").fill("pool for service identifiers")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool updated")).to_be_visible()
