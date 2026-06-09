"""Port of frontend/app/tests/e2e/proposed-changes/proposed-changes_checks.spec.ts.

/proposed-changes checks (a serial flow): create a proposed change against the
pre-seeded `atl1-delete-upstream` branch, open its Checks tab and verify the
checks summary lists every check category, then delete the proposed change.

Serial handling: both tests share the `pc-checks` proposed change the first one
creates. They live in one class and every method depends on the SAME
`demo_edge_repo` fixture, so pytest preserves their definition order. The checks
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

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestProposedChangesChecks:
    def test_should_display_checks_on_a_proposed_change(self, admin_page: Page, demo_edge_repo: None) -> None:
        admin_page.goto("/proposed-changes/new")

        # create a new proposed change
        expect(admin_page.get_by_role("heading", name="Create a proposed change")).to_be_visible()
        admin_page.get_by_label("Name *").fill("pc-checks")
        admin_page.get_by_label("Source Branch *").click()
        admin_page.get_by_role("option", name="atl1-delete-upstream").click()
        admin_page.get_by_role("button", name="Open").click()
        expect(admin_page.get_by_text("Proposed change created")).to_be_visible()

        # go to Checks tab and see summary for all checks
        admin_page.get_by_label("Tabs").get_by_text("Checks").click()
        if os.environ.get("UPDATE_DOCS_SCREENSHOTS"):
            expect(admin_page.get_by_test_id("checks-summary")).to_be_visible()
            while (
                admin_page.get_by_text("Data Integrity").is_hidden()
                or admin_page.get_by_text("Schema Integrity").is_hidden()
            ):
                # checks are async, we must wait for them
                admin_page.reload()
                expect(admin_page.get_by_label("Tabs").get_by_text("Checks")).to_be_visible()
                expect(admin_page.get_by_test_id("checks-summary")).to_be_visible()
        checks_summary = admin_page.get_by_test_id("checks-summary")
        expect(checks_summary.get_by_text("Retry")).to_be_visible()
        expect(checks_summary.get_by_text("Artifact")).to_be_visible()
        expect(checks_summary.get_by_text("Data")).to_be_visible()
        expect(checks_summary.get_by_text("Generator")).to_be_visible()
        expect(checks_summary.get_by_text("Repository")).to_be_visible()
        expect(checks_summary.get_by_text("Schema")).to_be_visible()
        expect(checks_summary.get_by_text("User")).to_be_visible()
        assert "tab=checks" in admin_page.url

        admin_page.wait_for_timeout(3000)  # wait for circle animation to finish
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_tab_checks")

    def test_should_delete_proposed_changes(self, admin_page: Page, demo_edge_repo: None) -> None:
        admin_page.goto("/proposed-changes")
        admin_page.get_by_test_id("actions-row-button-pc-checks").click()
        admin_page.get_by_test_id("delete-row-button").click()
        expect(admin_page.get_by_test_id("modal-delete")).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Proposed changes pc-checks deleted")).to_be_visible()
