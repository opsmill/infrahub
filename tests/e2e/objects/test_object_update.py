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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectUpdate:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-update")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_contain_initial_values_and_update_them(self, admin_page: Page, branch: str) -> None:
        # access the object
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        # go to device edit form
        admin_page.get_by_role("link", name="atl1-core1").click()
        admin_page.get_by_test_id("edit-button").click()

        # update the object
        admin_page.get_by_label("Name *").fill("atl1-core1-new-name")
        admin_page.get_by_label("Description").fill("New description")

        admin_page.get_by_test_id("side-panel-container").get_by_label("Status").click()
        admin_page.get_by_role("option", name="Maintenance").click()

        admin_page.get_by_test_id("side-panel-container").get_by_label("Role").click()
        admin_page.get_by_role("option", name="Edge Router").click()

        admin_page.get_by_test_id("side-panel-container").get_by_label("Asn").click()
        admin_page.get_by_role("option", name="AS174 174").click()

        admin_page.get_by_label("Tags").click()
        admin_page.get_by_text("blue").get_by_label("Remove").click()  # Removes blue
        admin_page.get_by_role("option", name="green").click()  # Adds green
        admin_page.get_by_role("option", name="red", exact=True).click()  # Adds red
        admin_page.get_by_label("Tags").click()  # to close the combobox

        admin_page.get_by_role("button", name="Save").click()

        # assert the updates
        # Verify the alert and the closed panel
        expect(admin_page.get_by_text("Device updated")).to_be_visible()
        expect(admin_page.get_by_test_id("side-panel-background")).not_to_be_visible()

        # Verify updates in view
        expect(admin_page.get_by_text("Nameatl1-core1-new-name")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_text("New description")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="AS174 174")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_text("StatusMaintenance")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_text("Edge Router")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="green")).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="red", exact=True)).to_be_visible()
        expect(admin_page.get_by_test_id("object-details").get_by_role("link", name="blue")).not_to_be_visible()

        # Verify updates in form
        admin_page.get_by_test_id("edit-button").click()
        expect(admin_page.get_by_label("Name *")).to_have_value("atl1-core1-new-name")
        expect(admin_page.get_by_label("Description")).to_have_value("New description")
        expect(admin_page.get_by_label("Type *")).to_have_value("MX204")
        expect(admin_page.get_by_label("Status")).to_have_text("Maintenance")
        expect(admin_page.get_by_label("Role")).to_have_text("Edge Router")
        expect(admin_page.get_by_label("Asn")).to_have_text("AS174 174")

        tab_input = admin_page.get_by_test_id("side-panel-container").get_by_text("green×red×")
        tab_input.scroll_into_view_if_needed()
        expect(tab_input).to_be_visible()

    def test_should_correctly_remove_values_from_selector(self, admin_page: Page, branch: str) -> None:
        # access the object
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        admin_page.get_by_role("link", name="atl1-leaf1").click()

        # assert initial object values
        expect(admin_page.get_by_text("Nameatl1-leaf1")).to_be_visible()
        expect(admin_page.get_by_text("RoleLeaf Switch")).to_be_visible()
        expect(admin_page.get_by_text("AsnAS64496 64496")).to_be_visible()

        # edit object values
        admin_page.get_by_test_id("edit-button").click()

        admin_page.get_by_test_id("side-panel-container").get_by_label("Status").click()
        admin_page.get_by_role("option", name="Active").click()

        admin_page.get_by_test_id("side-panel-container").get_by_label("Role").click()
        admin_page.get_by_role("option", name="Leaf Switch").click()

        admin_page.get_by_test_id("side-panel-container").get_by_label("Asn").click()
        admin_page.get_by_role("option", name="AS64496 64496").click()

        admin_page.get_by_role("button", name="Save").click()

        # assert new empty values
        expect(admin_page.get_by_text("Status-")).to_be_visible()
        expect(admin_page.get_by_text("Role-")).to_be_visible()
        expect(admin_page.get_by_text("Asn-")).to_be_visible()
