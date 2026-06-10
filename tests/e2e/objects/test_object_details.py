"""Port of frontend/app/tests/e2e/objects/object-details.spec.ts.

/objects/:objectKind/:objectId detail view: unauthenticated cannot edit, admin
can edit, relationship rendering, the two-step select, and the node metadata
popover. All work happens on a throwaway branch cut from main, hence the
data_topology dependency: Ethernet4's connected endpoint is a backbone Circuit
Endpoint built by the topology stage (the 203.111.0.2/29 BGP session label and
atl1-edge1's "Interfaces15" come via the transitive sites slice).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import TopologyHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectDetails:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_topology: TopologyHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-details")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    # --- when not logged in --------------------------------------------------
    async def test_should_not_be_able_to_edit_object(self, page: Page, branch: str) -> None:
        await page.goto(f"/objects/InfraBGPSession?branch={branch}")
        await page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        await expect(page.get_by_test_id("edit-button")).to_be_disabled()

        await page.get_by_test_id("object-details-menu").click()
        await expect(page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        await page.keyboard.press("Escape")

    # --- when logged in as Admin --------------------------------------------
    async def test_should_be_able_to_edit_object(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraBGPSession?branch={branch}")

        await admin_page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        await expect(admin_page.get_by_test_id("edit-button")).to_be_enabled()

        await admin_page.get_by_test_id("object-details-menu").click()
        await expect(admin_page.get_by_role("menuitem", name="Groups")).not_to_have_attribute("aria-disabled", "true")
        await admin_page.keyboard.press("Escape")

    async def test_should_display_relationships_correctly(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraBGPSession?branch={branch}")

        await admin_page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        # Attribute
        await expect(admin_page.get_by_text("Type", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Description", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Import Policies", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Export Policies", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Status", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Role", exact=True)).to_be_visible()

        # Relationships Attributes
        await expect(admin_page.get_by_text("Local As", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Remote As", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Local Ip", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Remote Ip", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Peer Group", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Peer Session", exact=True)).to_be_visible()

        # Relationships Generics
        await expect(admin_page.get_by_test_id("object-details").get_by_text("Device")).to_be_visible()

    async def test_should_display_the_select_2_steps_correctly(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        await admin_page.get_by_role("link", name="atl1-edge1").click()
        await admin_page.get_by_text("Interfaces15").click()
        await admin_page.get_by_role("link", name="Ethernet4").first.click()
        await admin_page.get_by_test_id("edit-button").click()

        kind_selector = admin_page.get_by_label("Kind").get_by_test_id("select-value")
        await expect(kind_selector).to_contain_text("Circuit Endpoint")

        node_selector = admin_page.get_by_label("Circuit Endpoint").get_by_test_id("select-value")
        await expect(node_selector).not_to_be_empty()  # ID is in the input but it's dynamic

    async def test_should_display_node_metadata_popover(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        await admin_page.get_by_role("link", name="atl1-edge1").click()

        await admin_page.get_by_role("button", name="View node metadata").click()

        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()
