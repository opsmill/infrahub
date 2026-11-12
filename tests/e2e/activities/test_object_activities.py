"""Port of frontend/app/tests/e2e/activities/object-activities.spec.ts.

Object activity log: open atl1-edge1's activity timeline (reloading until the
activity appears) and the per-event "View more" popover. Reads the activity
timeline populated by the data_sites load itself, so depends on data_sites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestObjectActivities:
    async def test_display_activity_log_details_for_atl1_edge1(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # Navigate to InfraDevice page
        await admin_page.goto("/objects/InfraDevice")
        await admin_page.get_by_role("link", name="atl1-edge1").click()

        # The page fetches the activities once, so it shows none until a reload after the events are stored.
        view_more_button = admin_page.get_by_role("button", name="View more").first
        deadline = Deadline("the atl1-edge1 activity log to be populated")
        while await view_more_button.is_hidden():
            await deadline.tick()
            if await admin_page.get_by_text("No activity found for this object.").is_visible():
                await admin_page.reload()

        await save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_device")

        # Open additional details via the 'View more' button
        await view_more_button.click()

        popover_content = admin_page.get_by_role("dialog")
        # Assert that the popover contains the expected text "Primary Node"
        await expect(popover_content).to_contain_text("Primary Node")
        # To be sure we load the data, checking if we do have a link to the device
        await expect(popover_content.get_by_role("link", name="atl1-edge1")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_device_popover")
