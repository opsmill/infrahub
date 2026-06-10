"""Port of frontend/app/tests/e2e/objects/object-update.spec.ts.

Edit an InfraDevice from its detail form: set/update attributes, relationships
(status, role, ASN) and a many-relationship (tags), then assert both the view
and the re-opened form; and a second flow that clears relationship values.
Operates on the demo devices atl1-core1 / atl1-leaf1 on a throwaway branch,
hence the data_sites dependency (the tags and ASNs come via its transitive
slices).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectUpdate:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-update")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_contain_initial_values_and_update_them(self, admin_page: Page, branch: str) -> None:
        # access the object
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        # go to device edit form
        await admin_page.get_by_role("link", name="atl1-core1").click()
        await admin_page.get_by_test_id("edit-button").click()

        # update the object
        await admin_page.get_by_label("Name *").fill("atl1-core1-new-name")
        await admin_page.get_by_label("Description").fill("New description")

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Status").click()
        await admin_page.get_by_role("option", name="Maintenance").click()

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Role").click()
        await admin_page.get_by_role("option", name="Edge Router").click()

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Asn").click()
        await admin_page.get_by_role("option", name="AS174 174").click()

        await admin_page.get_by_label("Tags").click()
        await admin_page.get_by_text("blue").get_by_label("Remove").click()  # Removes blue
        await admin_page.get_by_role("option", name="green").click()  # Adds green
        await admin_page.get_by_role("option", name="red", exact=True).click()  # Adds red
        await admin_page.get_by_label("Tags").click()  # to close the combobox

        await admin_page.get_by_role("button", name="Save").click()

        # assert the updates
        # Verify the alert and the closed panel
        await expect(admin_page.get_by_text("Device updated")).to_be_visible()
        await expect(admin_page.get_by_test_id("side-panel-background")).not_to_be_visible()

        # Verify updates in view
        await expect(admin_page.get_by_text("Nameatl1-core1-new-name")).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_text("New description")).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="AS174 174")).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_text("StatusMaintenance")).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_text("Edge Router")).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="green")).to_be_visible()
        await expect(
            admin_page.get_by_test_id("object-details").get_by_role("link", name="red", exact=True)
        ).to_be_visible()
        await expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="blue")).not_to_be_visible()

        # Verify updates in form
        await admin_page.get_by_test_id("edit-button").click()
        await expect(admin_page.get_by_label("Name *")).to_have_value("atl1-core1-new-name")
        await expect(admin_page.get_by_label("Description")).to_have_value("New description")
        await expect(admin_page.get_by_label("Type *")).to_have_value("MX204")
        await expect(admin_page.get_by_label("Status")).to_have_text("Maintenance")
        await expect(admin_page.get_by_label("Role")).to_have_text("Edge Router")
        await expect(admin_page.get_by_label("Asn")).to_have_text("AS174 174")

        tab_input = admin_page.get_by_test_id("side-panel-container").get_by_text("green×red×")
        await tab_input.scroll_into_view_if_needed()
        await expect(tab_input).to_be_visible()

    async def test_should_correctly_remove_values_from_selector(self, admin_page: Page, branch: str) -> None:
        # access the object
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_role("link", name="atl1-leaf1").click()

        # assert initial object values
        await expect(admin_page.get_by_text("Nameatl1-leaf1")).to_be_visible()
        await expect(admin_page.get_by_text("RoleLeaf Switch")).to_be_visible()
        await expect(admin_page.get_by_text("AsnAS64496 64496")).to_be_visible()

        # edit object values
        await admin_page.get_by_test_id("edit-button").click()

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Status").click()
        await admin_page.get_by_role("option", name="Active").click()

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Role").click()
        await admin_page.get_by_role("option", name="Leaf Switch").click()

        await admin_page.get_by_test_id("side-panel-container").get_by_label("Asn").click()
        await admin_page.get_by_role("option", name="AS64496 64496").click()

        await admin_page.get_by_role("button", name="Save").click()

        # assert new empty values
        await expect(admin_page.get_by_text("Status-")).to_be_visible()
        await expect(admin_page.get_by_text("Role-")).to_be_visible()
        await expect(admin_page.get_by_text("Asn-")).to_be_visible()
