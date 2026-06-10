"""Port of frontend/app/tests/e2e/activities/object-activities.spec.ts.

Object activity log: open atl1-edge1's activity timeline (reloading until the
activity appears) and the per-event "View more" popover. Reads the
demo-data-populated activity log, so depends on infrastructure_data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import Deadline, save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestObjectActivities:
    def test_display_activity_log_details_for_atl1_edge1(self, admin_page: Page, infrastructure_data: None) -> None:
        # Navigate to InfraDevice page
        admin_page.goto("/objects/InfraDevice")
        admin_page.get_by_role("link", name="atl1-edge1").click()

        deadline = Deadline("the atl1-edge1 activity log to be populated")
        while admin_page.get_by_text("No activity found for this").is_visible():
            deadline.tick()
            admin_page.reload()
            expect(admin_page.get_by_test_id("activities-container").get_by_text("Loading...")).to_be_hidden()

        save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_device")

        # Open additional details via the 'View more' button
        view_more_button = admin_page.get_by_role("button", name="View more").first
        expect(view_more_button).to_be_visible()
        view_more_button.click()

        popover_content = admin_page.get_by_role("dialog")
        # Assert that the popover contains the expected text "Primary Node"
        expect(popover_content).to_contain_text("Primary Node")
        # To be sure we load the data, checking if we do have a link to the device
        expect(popover_content.get_by_role("link", name="atl1-edge1")).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_device_popover")
