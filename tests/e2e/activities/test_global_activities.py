"""Port of frontend/app/tests/e2e/activities/global-activities.spec.ts.

Global activity log: navigate from the sidebar, filter by a primary node tag
(blue) and by has-children, then open event details (reloading until the
activity appears), and load more while new activities arrive. Reads the
activity log populated by the data_sites load itself (the blue tag comes
transitively, and it holds more than one page of activities), so depends on
data_sites.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page, Request

NEW_EVENT_COUNT = 5

EVENTS_BY_PRIMARY_NODE_QUERY = """
query EventsByPrimaryNode($ids: [String!]) {
  InfrahubEvent(primary_node__ids: $ids, limit: 50) {
    edges { node { id } }
  }
}
"""


def _is_events_request(request: Request) -> bool:
    return "GET_INFRAHUB_EVENTS" in (request.post_data or "")


async def _wait_for_stored_events(client: InfrahubClient, node_ids: list[str]) -> None:
    """Wait until the activity log holds one event per node; task workers store events asynchronously."""
    deadline = Deadline("the new activities to be stored")
    while True:
        response = await client.execute_graphql(query=EVENTS_BY_PRIMARY_NODE_QUERY, variables={"ids": node_ids})
        if len(response["InfrahubEvent"]["edges"]) >= len(node_ids):
            return
        await deadline.tick()


class TestGlobalActivities:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("activities-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

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

    async def test_load_more_while_new_activities_arrive_shows_each_activity_once(
        self, admin_page: Page, infrahub_client: InfrahubClient, data_sites: SitesHandle, branch: str
    ) -> None:
        await admin_page.goto("/activities")
        await expect(admin_page.get_by_role("heading", name="Activities")).to_be_visible()
        details_links = admin_page.get_by_role("link", name="View details", exact=True)
        await expect(details_links.first).to_be_visible()
        first_page_count = await details_links.count()

        # New activities arrive after the first page is shown, which shifts every older activity down.
        tags = []
        for index in range(NEW_EVENT_COUNT):
            tag = await infrahub_client.create(kind="BuiltinTag", name=f"{branch}-tag-{index}", branch=branch)
            await tag.save()
            tags.append(tag)
        await _wait_for_stored_events(infrahub_client, node_ids=[tag.id for tag in tags])

        deadline = Deadline("the next page of activities to load")
        async with admin_page.expect_request(_is_events_request) as load_more_request:
            while await details_links.count() <= first_page_count:
                await details_links.last.scroll_into_view_if_needed()
                await deadline.tick()

        hrefs = [await link.get_attribute("href") for link in await details_links.all()]
        repeated = sorted({href for href in hrefs if hrefs.count(href) > 1})
        assert not repeated, f"Activities shown more than once: {repeated}"

        # The next page continues from the time of the oldest activity shown, not from a position.
        variables = json.loads((await load_more_request.value).post_data or "{}")["variables"]
        assert "offset" not in variables
        assert variables.get("until")
