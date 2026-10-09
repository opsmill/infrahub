"""Port of frontend/app/tests/e2e/resource-manager/number-pool.spec.ts.

Serial: create a number pool for a generic schema and for a node schema, verify
its details, confirm the update form omits the node/attribute selects, open the
number-pool attribute-kind page, then create an InterfaceL3 that allocates from
the pool and verify the pool assignment.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the number pools it creates on that branch. Every test depends on the SAME
fixtures (admin_page + number_pool_branch) and the chain relies on pytest's
default definition-order collection (see the README's serial-specs gotcha).
Depends on data_sites (the atl1-core1 device); the InterfaceL3 schema and the
InfraService number pool come from the schema, not the data.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestNumberPool:
    @pytest.fixture(scope="class")
    async def number_pool_branch(
        self, infrahub_client: InfrahubClient, data_sites: SitesHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("number-pool")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_number_pool_for_generic_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await expect(admin_page.get_by_text("Name *")).to_be_visible()
        await admin_page.get_by_label("Name *").fill("number pool test for generic")
        await admin_page.get_by_label("Node *").click()
        await expect(admin_page.get_by_role("option", name="Interface Infra", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("option", name="Artifact Check Core", exact=True)).to_be_visible()
        await admin_page.get_by_role("option", name="Interface Infra", exact=True).click()
        await admin_page.get_by_text("Number Attribute *").click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start range *").fill("1")
        await admin_page.get_by_label("End range *").fill("10")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_create_number_pool_for_node_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill("number pool test for node")
        await admin_page.get_by_label("Node *").click()
        await admin_page.get_by_role("option", name="Interface L3 Infra", exact=True).click()
        await admin_page.get_by_text("Number Attribute *").click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start range *").fill("11")
        await admin_page.get_by_label("End range *").fill("20")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_header_for_user_created_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name="number pool test for generic").click()

        header = admin_page.locator("header").filter(has=admin_page.get_by_role("heading", level=1))
        await expect(header.get_by_role("heading", level=1, name="number pool test for generic")).to_be_visible()
        await expect(header.get_by_text("Managed by")).to_have_count(0)
        await expect(header.get_by_text("Allocates to")).to_be_visible()
        await expect(header.get_by_role("button", name="InfraInterface", exact=True)).to_be_visible()

        await header.get_by_role("button", name="Actions").click()
        await expect(admin_page.get_by_role("menuitem", name="Edit")).not_to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Delete")).not_to_have_attribute("aria-disabled", "true")

    async def test_update_form_should_not_include_node_and_attribute_selects(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name="number pool test for generic").click()
        await expect(admin_page.get_by_role("heading", level=1, name="number pool test for generic")).to_be_visible()
        await expect(admin_page.get_by_text("Node *")).not_to_be_visible()
        await expect(admin_page.get_by_text("Attribute *")).not_to_be_visible()

    async def test_header_for_schema_created_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_role("link", name="InfraService.").click()

        header = admin_page.locator("header").filter(has=admin_page.get_by_role("heading", level=1))
        await expect(header.get_by_role("button", name="Managed by schema")).to_be_visible()
        await expect(header.get_by_text("Allocates to")).to_be_visible()
        await expect(header.get_by_role("button", name="InfraService", exact=True)).to_be_visible()
        await expect(header.get_by_role("button", name="service_identifier", exact=True)).to_be_visible()

        await header.get_by_role("button", name="InfraService", exact=True).click()
        await expect(admin_page.get_by_role("dialog", name="Schema viewer")).to_be_visible()
        await admin_page.keyboard.press("Escape")
        await expect(admin_page.get_by_role("dialog", name="Schema viewer")).to_have_count(0)

        await header.get_by_role("button", name="Actions").click()
        await expect(admin_page.get_by_role("menuitem", name="Edit")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Delete")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="View schema")).to_have_attribute(
            "href", re.compile(r"kind=CoreNumberPool")
        )

    async def test_number_pool_attribute_kind_resource_manager(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await expect(admin_page.get_by_role("link", name="InfraService.")).to_be_visible()
        await admin_page.get_by_role("link", name="InfraService.").click()
        await expect(admin_page.get_by_role("heading", level=1)).to_be_visible()
        await save_screenshot_for_docs(admin_page, "numberpool_attribute_kind_resource_manager")

    async def test_create_node_using_number_pool_and_verify_pool_assignment(
        self, admin_page: Page, number_pool_branch: str
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
        await expect(admin_page.get_by_role("option", name="number pool test for generic")).to_be_visible()
        await expect(admin_page.get_by_role("option", name="number pool test for node")).to_be_visible()
        await admin_page.get_by_role("option", name="number pool test for generic").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()

        # Save interface
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InterfaceL3 created")).to_be_visible()

        # Verify pool assignment
        await admin_page.get_by_role("searchbox", name="Search").fill("interface with pool")
        await admin_page.get_by_role("link", name="test interface with pool").click()
        await admin_page.get_by_text("Speed1").get_by_test_id("view-metadata-button").click()
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="number pool test for generic")
        ).to_be_visible()
