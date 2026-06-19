"""Port of frontend/app/tests/e2e/tasks/tasks-view.spec.ts.

Preserved as skipped: the source describe is `test.describe.fixme` (the Tasks
list/detail flow is disabled in the legacy suite), so the coverage maps 1:1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page


@pytest.mark.skip(reason="`test.describe.fixme` in the source (Tasks - READ); preserved as skipped.")
class TestTasksRead:
    async def test_access_tasks_list_and_details(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "tasks_list")
        await admin_page.get_by_role("row", name="COMPLETED").get_by_role("link").nth(1).click()
        await expect(admin_page.get_by_role("link", name="All tasks")).to_be_visible()
        await expect(admin_page.get_by_text("StateCOMPLETED")).to_be_visible()
        await expect(admin_page.get_by_role("heading", name="Task Logs")).to_be_visible()
