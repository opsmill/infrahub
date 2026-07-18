"""Port of frontend/app/tests/e2e/proposed-changes/proposed-changes_checks.spec.ts.

/proposed-changes checks (a serial flow): create a proposed change against the
pre-seeded `atl1-delete-upstream` branch, open its Checks tab and verify the
checks summary lists every check category, then delete the proposed change.

Serial handling: both tests share the `pc-checks` proposed change the first one
creates. They live in one class and every method depends on the SAME
`demo_edge_repo` fixture and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha). The checks
(repository / data / schema / artifact / generator / user validators) and the
`atl1-delete-upstream` source branch come from the demo-edge repository and the
demo dataset behind it, hence the `demo_edge_repo` dependency.

The screenshot-only reload/poll loop (gated on UPDATE_DOCS_SCREENSHOTS in the
source, where checks are async and the page is reloaded until they appear) is
ported faithfully.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestProposedChangesChecks:
    async def test_should_display_checks_on_a_proposed_change(self, admin_page: Page, demo_edge_repo: None) -> None:
        await admin_page.goto("/proposed-changes/new")

        # create a new proposed change
        await expect(admin_page.get_by_role("heading", name="Create a proposed change")).to_be_visible()
        await admin_page.get_by_label("Name *").fill("pc-checks")
        await admin_page.get_by_label("Source Branch *").click()
        await admin_page.get_by_role("option", name="atl1-delete-upstream").click()
        await admin_page.get_by_role("button", name="Open").click()
        await expect(admin_page.get_by_text("Proposed change created")).to_be_visible()

        # go to Checks tab and see summary for all checks
        await admin_page.get_by_label("Tabs").get_by_text("Checks").click()
        if os.environ.get("UPDATE_DOCS_SCREENSHOTS"):
            await expect(admin_page.get_by_test_id("checks-summary")).to_be_visible()
            while (
                await admin_page.get_by_text("Data Integrity").is_hidden()
                or await admin_page.get_by_text("Schema Integrity").is_hidden()
            ):
                # checks are async, we must wait for them
                await admin_page.reload()
                await expect(admin_page.get_by_label("Tabs").get_by_text("Checks")).to_be_visible()
                await expect(admin_page.get_by_test_id("checks-summary")).to_be_visible()
        checks_summary = admin_page.get_by_test_id("checks-summary")
        await expect(checks_summary.get_by_text("Retry")).to_be_visible()
        await expect(checks_summary.get_by_text("Artifact")).to_be_visible()
        await expect(checks_summary.get_by_text("Data")).to_be_visible()
        await expect(checks_summary.get_by_text("Generator")).to_be_visible()
        await expect(checks_summary.get_by_text("Repository")).to_be_visible()
        await expect(checks_summary.get_by_text("Schema")).to_be_visible()
        await expect(checks_summary.get_by_text("User")).to_be_visible()
        assert "/checks" in admin_page.url

        await admin_page.wait_for_timeout(3000)  # wait for circle animation to finish
        await save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_tab_checks")

    async def test_should_delete_proposed_changes(self, admin_page: Page, demo_edge_repo: None) -> None:
        await admin_page.goto("/proposed-changes")
        await admin_page.get_by_test_id("actions-row-button-pc-checks").click()
        await admin_page.get_by_test_id("delete-row-button").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_be_visible()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Proposed changes pc-checks deleted")).to_be_visible()
