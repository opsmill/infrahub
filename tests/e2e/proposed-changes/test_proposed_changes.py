"""Port of frontend/app/tests/e2e/proposed-changes/proposed-changes.spec.ts.

/proposed-changes (a serial flow): unauthenticated users cannot create a
proposed change; as Admin the create form is reachable and validates required
fields; then a full create + display + edit cycle on a proposed change opened
against a throwaway copy of main.

Serial handling: the create/edit/merge sub-flow shares one source branch and
the generated proposed-change names (pc / pc-edit). Those tests live in their
own class whose every method depends on the SAME class-scoped fixtures (the
shared `pc_branch` + `pc_names`) and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha).
The standalone "not logged in" / "as Admin" tests are independent.

The proposed-change form's source-branch selector and the checks/validators
come from the demo-edge Git repository (and the demo dataset behind it), hence
the `demo_edge_repo` dependency.

The "add a comment" and "merge and delete" sub-tests are `test.fixme` in the
source (the proposed change has failing checks in CI so it cannot be merged);
they are preserved here as skipped. The active create/edit parts are ported.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestProposedChangesNotLoggedIn:
    def test_should_not_be_able_to_create_a_proposed_changes(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/proposed-changes")

        expect(page.get_by_role("heading", name="Proposed Change")).to_be_visible()
        expect(page.get_by_test_id("add-proposed-changes-button")).to_be_disabled()


class TestProposedChangesAsAdmin:
    def test_allow_to_create_a_proposed_change(self, admin_page: Page, demo_edge_repo: None) -> None:
        admin_page.goto("/proposed-changes")

        expect(admin_page.get_by_role("heading", name="Proposed Change")).to_be_visible()
        expect(admin_page.get_by_test_id("add-proposed-changes-button")).to_be_enabled()
        admin_page.get_by_test_id("add-proposed-changes-button").click()
        expect(admin_page.get_by_role("heading", name="Create a proposed change")).to_be_visible()

    def test_display_validation_errors_when_form_is_submitted_with_wrong_value(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/proposed-changes/new")

        expect(admin_page.get_by_role("heading", name="Create a proposed change")).to_be_visible()
        admin_page.get_by_role("button", name="Open").click()
        expect(admin_page.get_by_label("Name *").locator("..")).to_contain_text("Required")
        expect(admin_page.get_by_text("Source Branch *").locator("..")).to_contain_text("Required")


class TestProposedChangesCreateEditMerge:
    @pytest.fixture(scope="class")
    def pc_names(self) -> dict[str, str]:
        return {
            "name": generate_random_branch_name("pc-e2e"),
            "name_edit": generate_random_branch_name("pc-e2e-edit"),
        }

    @pytest.fixture(scope="class")
    def pc_branch(
        self,
        infrahub_client: InfrahubClientSync,
        demo_edge_repo: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("main-copy-for-pc-e2e")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_create_new_proposed_change(self, admin_page: Page, pc_branch: str, pc_names: dict[str, str]) -> None:
        admin_page.goto("/proposed-changes/new")
        expect(admin_page.get_by_text("Create a proposed Change")).to_be_visible()

        admin_page.get_by_label("Source Branch *").click()
        admin_page.get_by_role("option", name=pc_branch).click()
        admin_page.get_by_label("Name *").fill(pc_names["name"])
        admin_page.get_by_test_id("codemirror-editor").get_by_role("textbox").fill("My description")
        admin_page.get_by_label("Reviewers").click()
        admin_page.get_by_role("option", name="Olivia Carter").click()
        admin_page.get_by_role("option", name="CRM Synchronization").click()
        admin_page.get_by_label("Reviewers").click()  # to close the combobox
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_create_form")

        admin_page.get_by_role("button", name="Open").click()
        expect(admin_page.get_by_text("Proposed change created")).to_be_visible()

    def test_display_and_edit_proposed_change(self, admin_page: Page, pc_branch: str, pc_names: dict[str, str]) -> None:
        admin_page.goto("/proposed-changes")

        # display created proposed change details
        admin_page.get_by_text(pc_names["name"], exact=True).click()
        expect(admin_page.get_by_text("Source branch" + pc_branch)).to_be_visible()
        expect(admin_page.get_by_role("row", name="State open")).to_be_visible()
        expect(admin_page.get_by_role("cell", name="Created by")).to_be_visible()
        expect(admin_page.get_by_role("cell", name="Created at")).to_be_visible()
        expect(admin_page.get_by_role("cell", name="Updated by")).to_be_visible()
        expect(admin_page.get_by_role("cell", name="Updated at")).to_be_visible()
        # Validate the buttons are showing as intended
        expect(admin_page.get_by_role("button", name="Approve")).not_to_be_disabled()
        save_screenshot_for_docs(admin_page, "topics/proposed_change/pc_tab_overview")
        admin_page.get_by_test_id("proposed-change-action-button-select").nth(1).click()
        expect(admin_page.get_by_role("option", name="Merge")).not_to_be_disabled()
        expect(admin_page.get_by_role("option", name="Close")).not_to_be_disabled()
        expect(admin_page.get_by_role("option", name="Move to draft")).not_to_be_disabled()

        # edit proposed change reviewers
        admin_page.get_by_test_id("edit-button").click()
        admin_page.get_by_label("Name").fill(pc_names["name_edit"])
        admin_page.get_by_test_id("side-panel-container").get_by_test_id("codemirror-editor").get_by_role(
            "textbox"
        ).fill("My description edit")
        admin_page.locator("span").filter(has_text="CRM Synchronization").get_by_label("Remove").click()
        admin_page.locator("span").filter(has_text="Olivia Carter").get_by_label("Remove").click()
        admin_page.get_by_label("Reviewers").click()  # to close the combobox
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("ProposedChange updated")).to_be_visible()

        expect(admin_page.get_by_role("heading", name=pc_names["name_edit"], exact=True)).to_be_visible()
        expect(admin_page.get_by_test_id("pc-description")).to_contain_text("My description edit")
        expect(admin_page.get_by_text("OC", exact=True)).not_to_be_visible()
        expect(admin_page.get_by_text("CS", exact=True)).not_to_be_visible()

    @pytest.mark.skip(reason="test.fixme in the source; preserved as skipped.")
    def test_add_a_comment_on_overview_tab(self, admin_page: Page, pc_branch: str, pc_names: dict[str, str]) -> None:
        admin_page.goto("/proposed-changes")
        admin_page.get_by_text(pc_names["name_edit"], exact=True).first.click()

        admin_page.get_by_test_id("codemirror-editor").get_by_role("textbox").fill("comment on overview tab")
        admin_page.get_by_role("button", name="Comment", exact=True).click()
        expect(admin_page.get_by_test_id("comment").get_by_text("comment on overview tab")).to_be_visible()
        expect(admin_page.get_by_test_id("codemirror-editor").get_by_role("textbox")).to_contain_text(
            "Add your comment here..."
        )

    # The proposed change has currently failing checks in the CI, so it cannot be merged
    @pytest.mark.skip(reason="test.fixme in the source; preserved as skipped.")
    def test_merge_and_delete_proposed_change(self, admin_page: Page, pc_branch: str, pc_names: dict[str, str]) -> None:
        admin_page.goto("/proposed-changes")
        admin_page.get_by_text(pc_names["name_edit"], exact=True).first.click()

        # ensure the checks are fine
        expect(admin_page.get_by_test_id("checks-tab").get_by_test_id("Loading...")).to_be_hidden()
        admin_page.get_by_text("Checks").click()

        # Reload page until we have successful checks
        while (
            admin_page.get_by_text("Retry all").is_visible()
            and admin_page.get_by_test_id("validator-success").is_hidden()
        ):
            admin_page.reload()

        # merge proposed change and update UI
        admin_page.get_by_test_id("proposed-change-action-button-select").click()
        admin_page.get_by_role("option", name="Merge")
        expect(admin_page.get_by_text("Proposed changes merged successfully!")).to_be_visible()
        expect(admin_page.get_by_text("Statemerged")).to_be_visible()

        # not able to edit proposed change
        expect(admin_page.get_by_role("button", name="Approve")).to_be_disabled()
        expect(admin_page.get_by_test_id("proposed-change-action-button-select")).to_be_disabled()
        expect(admin_page.get_by_test_id("edit-button")).to_be_disabled()

        # delete proposed change
        admin_page.goto("/proposed-changes?pr_state=close")
        admin_page.get_by_test_id(f"actions-row-{pc_names['name']}").first.click()
        admin_page.get_by_test_id("delete-row-button").click()
        expect(admin_page.get_by_test_id("modal-delete")).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text(f"Proposed changes {pc_names['name_edit']} deleted")).to_be_visible()
