"""Port of frontend/app/tests/e2e/activities/global-activities.spec.ts.

Global activity log: navigate from the sidebar, filter by a primary node tag
(blue) and by has-children, then open event details (reloading until the
activity appears). Reads the activity log populated by the data_sites load
itself (the blue tag comes transitively), so depends on data_sites.
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


class TestGlobalActivities:
    async def test_navigate_to_global_activity_log_from_sidebar(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        await admin_page.goto("/")

        await admin_page.get_by_test_id("sidebar").get_by_role("button", name="Activity").click()
        await admin_page.get_by_role("menuitem", name="Activities").click()
        await expect(admin_page.get_by_role("heading", name="Activities")).to_be_visible()

    async def test_filter_activities_by_primary_node_tag(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # Navigate to activity log page
        await admin_page.goto("/activities")

        # Apply primary node filter for blue tag
        await admin_page.get_by_role("button", name="Primary Node").click()
        await admin_page.get_by_placeholder("Filter...").fill("tag")
        await admin_page.get_by_role("option", name="Tag", exact=True).click()
        await admin_page.get_by_role("option", name="blue").click()
        await admin_page.get_by_role("button", name="Apply").click()

        await expect(admin_page.get_by_role("button", name="Primary Node blue")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_filters_primary")

    async def test_filter_by_has_children_and_view_event_details(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        # Navigate to activity log page
        await admin_page.goto("/activities")
        await expect(admin_page.get_by_role("heading", name="Activities")).to_be_visible()

        # Apply has children filter set to true
        await admin_page.get_by_role("button", name="Has Children").click()
        await admin_page.get_by_text("True").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_role("button", name="Has Children true")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_filters_children")

        # Open event details and verify children are displayed
        await admin_page.get_by_role("link", name="View details").first.click()

        deadline = Deadline("the event details activity log to be populated")
        while await admin_page.get_by_text("No activity found for this object.").is_visible():
            await deadline.tick()
            await admin_page.reload()
            await expect(admin_page.get_by_test_id("activities-container").get_by_text("Loading...")).to_be_hidden()
        # Check that at least one "View more." button is present in the details page
        await expect(admin_page.get_by_role("button", name="View more").first).to_be_visible()
        await save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_details_children")
