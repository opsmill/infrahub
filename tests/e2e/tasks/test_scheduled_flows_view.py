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

# Every verdict the backend can return, most in need of attention first. Each must be readable as
# words, never colour alone, and the list is ordered by this ranking.
HEALTH_LABELS = (
    "Overdue",
    "Failed",
    "Cancelled",
    "No recent runs",
    "Never run",
    "Paused",
    "Healthy",
)

HEALTH_BADGE_SELECTOR = "[data-testid^='scheduled-flow-health-']"


class TestScheduledFlowsView:
    async def test_reachable_from_the_tasks_page_in_one_click(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()

        await admin_page.get_by_role("link", name="View scheduled flows").click()

        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()
        assert "/tasks/scheduled" in admin_page.url

    async def test_every_scheduled_flow_is_listed_with_its_schedule_and_last_outcome(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()

        for flow_name in EVERY_MINUTE_FLOWS:
            row = admin_page.get_by_role("row").filter(has_text=flow_name)
            await expect(row).to_be_visible()
            await expect(row).to_contain_text("Every minute")

        # The daily flows carry a randomised minute, so match the rendered sentence shape.
        await expect(admin_page.get_by_role("row").filter(has_text="anonymous_telemetry_send")).to_contain_text(
            re.compile(r"Daily at 02:\d{2}")
        )

    async def test_each_health_verdict_is_identifiable_from_the_list_without_opening_a_row(
        self, admin_page: Page
    ) -> None:
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()

        rows = admin_page.get_by_role("table").get_by_role("row").filter(has=admin_page.locator("td"))
        await expect(rows.first).to_be_visible()

        # Every row carries its own verdict as a word, not only as a colour, and the badge is read
        # from its own element so the "Last outcome" column cannot supply the word for it.
        verdicts: list[str] = []
        for index in range(await rows.count()):
            badge = rows.nth(index).locator(HEALTH_BADGE_SELECTOR)
            await expect(badge).to_be_visible()
            verdicts.append((await badge.inner_text()).strip())

        assert verdicts, "the list rendered no rows"
        unreadable = [verdict for verdict in verdicts if verdict not in HEALTH_LABELS]
        assert unreadable == [], f"health verdicts not readable as words: {unreadable}"

    async def test_a_flow_needing_attention_is_listed_above_the_healthy_ones(self, admin_page: Page) -> None:
        """An operator scanning the list top-down meets the flows needing attention first."""
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()

        rows = admin_page.get_by_role("table").get_by_role("row").filter(has=admin_page.locator("td"))
        await expect(rows.first).to_be_visible()

        ranks = []
        for index in range(await rows.count()):
            verdict = (await rows.nth(index).locator(HEALTH_BADGE_SELECTOR).inner_text()).strip()
            ranks.append(HEALTH_LABELS.index(verdict))

        assert ranks == sorted(ranks), f"rows are not ordered by how much attention they need: {ranks}"

    async def test_drilling_into_a_flow_lists_its_runs_unfiltered_by_state(self, admin_page: Page) -> None:
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
        await (
            admin_page.get_by_role("row")
            .filter(has_text="git_repositories_sync")
            .first.get_by_role("link")
            .first.click()
        )

        await expect(admin_page.get_by_role("heading", name="Task Logs")).to_be_visible()

    async def test_the_view_issues_one_request_however_many_flows_are_listed(self, admin_page: Page) -> None:
        """The client must not fan out one request per flow.

        Every GraphQL request made while the view loads is recorded, not only the summary one: a
        fan-out would be a different operation — a per-flow run or detail query — and counting only
        the summary operation would never see it.
        """
        graphql_requests: list[str] = []

        def record(request: Request) -> None:
            if "/graphql" in request.url and request.method == "POST":
                graphql_requests.append(request.post_data or "")

        admin_page.on("request", record)
        await admin_page.goto("/tasks/scheduled")
        await expect(admin_page.get_by_role("heading", name="Scheduled Flows")).to_be_visible()
        rows = admin_page.get_by_role("table").get_by_role("row").filter(has=admin_page.locator("td"))
        await expect(rows.first).to_be_visible()
        admin_page.remove_listener("request", record)

        flow_names = [
            (await rows.nth(index).locator("td").first.inner_text()).strip() for index in range(await rows.count())
        ]
        assert len(flow_names) >= len(EVERY_MINUTE_FLOWS)

        summary_requests = [body for body in graphql_requests if "InfrahubScheduledFlows" in body]
        assert len(summary_requests) == 1, f"{len(summary_requests)} summary requests for {len(flow_names)} flows"

        # A per-flow request has to name the flow it is about, whatever operation it uses.
        per_flow_requests = [body for body in graphql_requests if any(name in body for name in flow_names)]
        assert per_flow_requests == [], f"the view fanned out per flow: {per_flow_requests}"
