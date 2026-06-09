"""Port of frontend/app/tests/e2e/activities/global-activities.spec.ts.

Global activity log: navigate from the sidebar, filter by a primary node tag
(blue) and by has-children, then open event details (reloading until the
activity appears). Reads the demo-data-populated activity log, so depends on
infrastructure_data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestGlobalActivities:
    def test_navigate_to_global_activity_log_from_sidebar(self, admin_page: Page, infrastructure_data: None) -> None:
        admin_page.goto("/")

        admin_page.get_by_test_id("sidebar").get_by_role("button", name="Activity").click()
        admin_page.get_by_role("menuitem", name="Activities").click()
        expect(admin_page.get_by_role("heading", name="Activities")).to_be_visible()

    def test_filter_activities_by_primary_node_tag(self, admin_page: Page, infrastructure_data: None) -> None:
        # Navigate to activity log page
        admin_page.goto("/activities")

        # Apply primary node filter for blue tag
        admin_page.get_by_role("button", name="Primary Node").click()
        admin_page.get_by_placeholder("Filter...").fill("tag")
        admin_page.get_by_role("option", name="Tag", exact=True).click()
        admin_page.get_by_role("option", name="blue").click()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("button", name="Primary Node blue")).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_filters_primary")

    def test_filter_by_has_children_and_view_event_details(self, admin_page: Page, infrastructure_data: None) -> None:
        # Navigate to activity log page
        admin_page.goto("/activities")
        expect(admin_page.get_by_role("heading", name="Activities")).to_be_visible()

        # Apply has children filter set to true
        admin_page.get_by_role("button", name="Has Children").click()
        admin_page.get_by_text("True").click()
        admin_page.get_by_role("button", name="Apply").click()
        expect(admin_page.get_by_role("button", name="Has Children true")).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_filters_children")

        # Open event details and verify children are displayed
        admin_page.get_by_role("link", name="View details").first.click()

        while admin_page.get_by_text("No activity found for this object.").is_visible():
            admin_page.reload()
            expect(admin_page.get_by_test_id("activities-container").get_by_text("Loading...")).to_be_hidden()
        # Check that at least one "View more." button is present in the details page
        expect(admin_page.get_by_role("button", name="View more").first).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/activity-logs/activity_log_global_details_children")
