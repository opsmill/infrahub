"""Port of tutorials/tutorial-4_integration-with-git.spec.ts.

Generate device configuration: create a Git-synced branch (update-ethernet1) and
update the Ethernet1 interface of atl1-edge1 on it. Needs the demo data (the
device) and registers the demo-edge repo so the Git-sync branch is meaningful.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page, Response


class TestTutorial4GitIntegration:
    def test_generate_the_configuration_of_a_device(
        self, admin_page: Page, infrastructure_menu: None, demo_edge_repo: None
    ) -> None:
        # regression guard: fail on any 500 response (mirrors the TS beforeEach)
        server_errors: list[str] = []

        def _record_500(response: Response) -> None:
            if response.status == 500:
                server_errors.append(response.url)

        admin_page.on("response", _record_500)

        admin_page.goto("/")

        # create a new branch update-ethernet1 (synced with Git)
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_test_id("create-branch-button").click()
        admin_page.get_by_label("New branch name").fill("update-ethernet1")
        admin_page.get_by_label("Sync with Git").click()
        save_screenshot_for_docs(admin_page, "tutorial_6_branch_creation")
        admin_page.get_by_role("button", name="Create").click()
        expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text("update-ethernet1")

        # go to interface Ethernet1 for atl1-edge1
        admin_page.get_by_test_id("sidebar").get_by_role("button", name="Device Management").click()
        admin_page.get_by_role("menuitem", name="Device", exact=True).click()
        expect(admin_page.get_by_text("Generic Device object")).to_be_visible()
        admin_page.get_by_role("link", name="atl1-edge1").click()
        admin_page.get_by_text("Interfaces15").click()
        admin_page.get_by_role("link", name="Ethernet1", exact=True).first.click()

        # update the interface Ethernet1 for atl1-edge1
        admin_page.get_by_test_id("edit-button").click()
        admin_page.get_by_label("Description").fill("New description in the branch")
        save_screenshot_for_docs(admin_page, "tutorial_6_interface_update")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.locator("#alert-success-updated")).to_contain_text("InterfaceL3 updated")

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"
