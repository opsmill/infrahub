"""Port of tutorials/tutorial-2_data-lineage-and-metadata.spec.ts.

Explore and update object metadata (make a device's Description protected, owned
by the Admin account) as a read-write user. Operates on the demo device
atl1-core2, so it needs data_sites; uses the read-write role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestTutorial2Metadata:
    async def test_explore_and_update_object_metadata(self, read_write_page: Page, data_sites: SitesHandle) -> None:
        # go to the detailed page of a device
        await read_write_page.goto("/objects/InfraDevice")
        await read_write_page.get_by_role("link", name="atl1-core2").click()

        # explore Description attribute metadata
        await expect(read_write_page.get_by_text("Siteatl1")).to_be_visible()
        await read_write_page.get_by_text("Description-").get_by_test_id("view-metadata-button").click()
        await expect(read_write_page.get_by_text("Is protectedFalse")).to_be_visible()
        await save_screenshot_for_docs(read_write_page, "tutorial_4_metadata")

        # update the Description attribute to make it protected
        await read_write_page.get_by_test_id("edit-metadata-button").click()
        await read_write_page.get_by_label("Kind").first.click()
        await read_write_page.get_by_role("option", name="Account").first.click()
        await read_write_page.get_by_label("Account").click()
        await read_write_page.get_by_role("option", name="Admin").click()
        await read_write_page.get_by_role("group", name="is protected").locator("label").filter(has_text="True").click()
        await save_screenshot_for_docs(read_write_page, "tutorial_4_metadata_edit")
        await read_write_page.get_by_role("button", name="Save").click()

        await expect(read_write_page.get_by_text("Metadata updated")).to_be_visible()

        # wait for the metadata edit slide-over to close before checking updated data
        await expect(read_write_page.get_by_test_id("side-panel-container")).to_be_hidden()

        await read_write_page.get_by_text("Description-").get_by_test_id("view-metadata-button").click()
        await expect(read_write_page.get_by_text("Is protectedTrue")).to_be_visible()
