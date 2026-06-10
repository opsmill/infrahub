"""Port of frontend/app/tests/e2e/objects/object-metadata.spec.ts.

Object attribute metadata: open the metadata tooltip on a device attribute,
edit it (set the protected flag and an owner), and verify the change persists;
plus that a read-only (computed) attribute has no metadata edit button. Operates
on the demo device atl1-core2 on main, hence the data_sites dependency (the
Architecture Team owner option comes via the transitive rbac slice). The source
runs directly on main without a branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.sync_api import Page


class TestObjectMetadata:
    def test_contain_initial_values_and_update_them(self, admin_page: Page, data_sites: SitesHandle) -> None:
        admin_page.goto("/objects/InfraDevice")

        # Access device details
        admin_page.get_by_role("link", name="atl1-core2").click()

        # Acces type metadata
        type_row = admin_page.get_by_text("TypeMX204")
        type_row.get_by_test_id("view-metadata-button").click()
        metadata_tooltip = admin_page.get_by_test_id("metadata-tooltip")
        metadata_tooltip.get_by_test_id("edit-metadata-button").click()

        # Owner should be empty
        expect(admin_page.get_by_label("Kind").first.get_by_test_id("select-value")).not_to_be_visible()

        # Is protected should not be checked
        expect(admin_page.get_by_label("is protected *")).not_to_be_checked()

        # Check is protected
        admin_page.get_by_label("is protected *").check()

        # Select Architecture team
        admin_page.get_by_label("Kind").first.click()
        admin_page.get_by_role("option", name="Account group").click()
        admin_page.get_by_label("Account group").click()
        admin_page.get_by_role("option", name="Architecture Team").click()

        # Save
        admin_page.get_by_role("button", name="Save").click()

        # Verify the alert
        expect(admin_page.get_by_text("Metadata updated")).to_be_visible()

        # Access all devices
        admin_page.goto("/objects/InfraDevice")

        # Access device details
        admin_page.get_by_role("link", name="atl1-core2").click()

        # Acces type metadata
        type_row_updated = admin_page.get_by_text("TypeMX204")
        type_row_updated.get_by_test_id("view-metadata-button").click()
        metadata_tooltip_updated = admin_page.get_by_test_id("metadata-tooltip")
        metadata_tooltip_updated.get_by_test_id("edit-metadata-button").click()

        # Source should be Account + Pop-Builder
        expect(admin_page.get_by_test_id("select-value").nth(0)).to_contain_text("Account group")
        expect(admin_page.get_by_test_id("select-value").nth(1)).to_contain_text("Architecture Team")

        # Is protected should be checked
        expect(admin_page.get_by_label("is protected *")).to_be_checked()

    def test_read_only_attribute_should_not_have_metadata_edit_button(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        admin_page.goto("/objects/InfraDevice")
        admin_page.get_by_role("link", name="atl1-core2").click()

        description_row = admin_page.get_by_text("Computed DescriptionMX204")
        description_row.get_by_test_id("view-metadata-button").click()
        expect(admin_page.get_by_role("cell", name="Source")).to_be_visible()
        expect(admin_page.get_by_test_id("edit-metadata-button")).not_to_be_visible()
