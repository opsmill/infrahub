"""Port of frontend/app/tests/e2e/proposed-changes/proposed-changes_diff.spec.ts.

/proposed-changes diff data (a serial flow): create a proposed change against
the pre-seeded `den1-maintenance-conflict` branch, refresh the data diff, verify
the diffed nodes / conflict, resolve the conflict, comment on the diff, then
delete the proposed change.

Serial handling: all three tests share the `conflict-test` proposed change the
first one creates. They live in one class and every method depends on the SAME
`demo_edge_repo` fixture, so pytest preserves their definition order. The
`den1-maintenance-conflict` source branch and its data diff come from the demo
dataset / demo-edge repository, hence the `demo_edge_repo` dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestProposedChangesDiff:
    def test_should_verify_the_diff_data_with_conflicts(self, admin_page: Page, demo_edge_repo: None) -> None:
        # create a new proposed change with reviewers
        admin_page.goto("/proposed-changes")
        admin_page.get_by_test_id("add-proposed-changes-button").click()
        admin_page.get_by_label("Source Branch *").click()
        admin_page.get_by_role("option", name="den1-maintenance-conflict").click()
        admin_page.get_by_label("Name *").fill("conflict-test")
        admin_page.get_by_label("Reviewers").click()
        admin_page.get_by_role("option", name="Admin").click()
        admin_page.get_by_label("Reviewers").click()
        admin_page.get_by_role("button", name="Open", exact=True).click()
        expect(admin_page.get_by_text("Proposed change created")).to_be_visible()
        admin_page.get_by_text("Data").click()

        # trigger the diff update
        admin_page.get_by_role("button", name="Refresh").click()
        expect(admin_page.get_by_text("Diff updated!")).to_be_visible()

        # check diff data
        expect(admin_page.get_by_text("Infra ›Interface L3")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Ethernet1")).to_be_visible()
        expect(admin_page.get_by_text("Infra ›Deviceden1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_tab_data")
        admin_page.get_by_text("Infra ›Interface L3").click()
        admin_page.get_by_label("diff tree").get_by_text("den1-edge1").click()
        admin_page.get_by_text(
            "main den1-maintenance-conflictstatusConflictactiveprovisioningmaintenanceChoose"
        ).click()
        hash_value = admin_page.evaluate("() => window.location.hash")
        highlighted_node_diff = admin_page.locator(f"id={hash_value[1:]}")
        expect(highlighted_node_diff).to_be_in_viewport()
        expect(highlighted_node_diff).to_contain_class("ring-2 ring-custom-blue-500")

        # resolve conflict
        expect(
            admin_page.get_by_text("Choose the branch to resolve the conflict:mainden1-maintenance-conflict")
        ).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_conflict_resolution")
        admin_page.get_by_role("checkbox", name="main", exact=True).click()
        expect(admin_page.get_by_text("Conflict marked as resolved")).to_be_visible()

    def test_should_comment_a_proposed_changes(self, admin_page: Page, demo_edge_repo: None) -> None:
        # access proposed change diff tab
        admin_page.goto("/proposed-changes")
        admin_page.get_by_role("link", name="conflict-test").click()
        expect(admin_page.get_by_role("heading", name="conflict-test")).to_be_visible()
        admin_page.get_by_text("Data").click()
        expect(admin_page.get_by_role("button", name="Refresh diff")).to_be_visible()

        # comment proposed changes
        admin_page.locator("span").filter(has_text="Infra ›Deviceden1-edge1").hover()
        admin_page.locator("span").filter(has_text="Infra ›Deviceden1-edge1").get_by_test_id(
            "data-diff-add-comment"
        ).click()
        expect(admin_page.get_by_text("Add a comment")).to_be_visible()
        admin_page.get_by_role("textbox").click()
        admin_page.get_by_role("textbox").fill("Some comment ")
        admin_page.get_by_role("button", name="Comment", exact=True).click()
        expect(admin_page.get_by_test_id("comment").get_by_text("AAdmin")).to_be_visible()
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_comments")

        expect(admin_page.get_by_label("Resolve thread")).not_to_be_checked()
        admin_page.get_by_label("Resolve thread").click()
        admin_page.get_by_role("button", name="Confirm", exact=True).click()
        expect(admin_page.get_by_label("Resolved")).to_be_checked()

    def test_should_delete_the_proposed_change(self, admin_page: Page, demo_edge_repo: None) -> None:
        admin_page.goto("/proposed-changes")
        admin_page.get_by_test_id("actions-row-button-conflict-test").click()
        admin_page.get_by_test_id("delete-row-button").click()
        expect(admin_page.get_by_test_id("modal-delete")).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Proposed changes conflict-test deleted")).to_be_visible()
