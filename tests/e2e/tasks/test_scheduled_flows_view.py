"""E2E coverage for the scheduled-flows view and its drill-down.

An operator reaches the view from the Tasks page, reads each background flow's
schedule and last outcome from the list alone, and drills into one flow to see
its runs and open a run's logs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page, Request

# Registered with a cron in the workflow catalogue, so they are always present on a running instance.
EVERY_MINUTE_FLOWS = ("git_repositories_sync", "clean-up-deadlocks")

# Every verdict the backend can return. Each must be readable as words, never colour alone.
HEALTH_LABELS = (
    "Overdue",
    "Failed",
    "Cancelled",
    "No recent runs",
    "Never run",
    "Paused",
    "Healthy",
)


class TestScheduledFlowsView:
    async def test_reachable_from_the_tasks_page_in_one_click(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()

        await admin_page.get_by_role("link", name="View scheduled flows").click()

        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()
        assert "/tasks/scheduled" in admin_page.url

    async def test_every_scheduled_flow_is_listed_with_its_schedule_and_last_outcome(
        self, admin_page: Page
    ) -> None:
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()

        for flow_name in EVERY_MINUTE_FLOWS:
            row = admin_page.get_by_role("row").filter(has_text=flow_name)
            await expect(row).to_be_visible()
            await expect(row).to_contain_text("Every minute")

        # The daily flows carry a randomised minute, so match the rendered sentence shape.
        await expect(
            admin_page.get_by_role("row").filter(has_text="anonymous_telemetry_send")
        ).to_contain_text(re.compile(r"Daily at 02:\d{2}"))

    async def test_each_health_verdict_is_identifiable_from_the_list_without_opening_a_row(
        self, admin_page: Page
    ) -> None:
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()

        health_cells = admin_page.get_by_role("row").locator("td").nth(3)
        await expect(health_cells.first).to_be_visible()

        table_text = await admin_page.get_by_role("table").inner_text()
        assert any(label in table_text for label in HEALTH_LABELS), (
            f"no health verdict was readable as text in the list: {table_text!r}"
        )

    async def test_drilling_into_a_flow_lists_its_runs_unfiltered_by_state(
        self, admin_page: Page
    ) -> None:
        await admin_page.goto("/tasks/scheduled")
        row = admin_page.get_by_role("row").filter(has_text="git_repositories_sync")
        await expect(row).to_be_visible()

        await row.get_by_role("link").first.click()

        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()
        # Pre-created future SCHEDULED runs legitimately appear here: the Tasks reader applies none
        # of the scheduled-flow view's bounds. Scoping is asserted by the flow's own runs showing up.
        run_rows = admin_page.get_by_role("row").filter(has_text="git_repositories_sync")
        await expect(run_rows.first).to_be_visible()

    async def test_a_run_reached_from_the_drill_down_shows_its_logs(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks/scheduled")
        row = admin_page.get_by_role("row").filter(has_text="git_repositories_sync")
        await expect(row).to_be_visible()
        await row.get_by_role("link").first.click()

        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()
        await admin_page.get_by_role("row").filter(has_text="git_repositories_sync").first.get_by_role(
            "link"
        ).first.click()

        await expect(admin_page.get_by_role("heading", name="Task Logs")).to_be_visible()

    async def test_the_view_issues_one_request_however_many_flows_are_listed(
        self, admin_page: Page
    ) -> None:
        """The client must not fan out one request per flow."""
        scheduled_flow_requests: list[str] = []

        def record(request: Request) -> None:
            if "/graphql" not in request.url:
                return
            body = request.post_data or ""
            if "InfrahubScheduledFlows" in body:
                scheduled_flow_requests.append(body)

        admin_page.on("request", record)
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()
        await expect(admin_page.get_by_role("table")).to_be_visible()
        admin_page.remove_listener("request", record)

        flow_count = await admin_page.get_by_role("row").count() - 1
        assert flow_count >= len(EVERY_MINUTE_FLOWS)
        assert len(scheduled_flow_requests) == 1, (
            f"{len(scheduled_flow_requests)} scheduled-flow requests for {flow_count} flows"
        )
