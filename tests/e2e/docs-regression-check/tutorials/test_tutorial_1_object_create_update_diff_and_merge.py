"""Port of tutorials/tutorial-1_object-create-update-diff-and-merge.spec.ts.

Serial getting-started walkthrough: create a Tenant on main, create branch
cr1234, update the Tenant on the branch, view the diff and MERGE cr1234 into
main, then browse historical data. Mutates main (the merge), so this docs-
regression group should run as its own step (see tests/e2e/README.md).

All tests share the same fixtures (admin_page + data_org_registry, which seeds
the Duff tenant + date_before) and rely on pytest's default definition-order
collection (see the README's serial-specs gotcha). `date_before` is captured
before the Tenant is created, for the historical-data step.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import OrgRegistryHandle
    from playwright.sync_api import Page


class TestTutorial1ObjectAndBranch:
    @pytest.fixture(scope="class")
    def date_before(self, data_org_registry: OrgRegistryHandle, infrastructure_menu: None) -> datetime:
        # Captured before test 1 creates the Tenant but AFTER the dataset exists
        # (local time, to match the UI's timeframe selector). The selector is
        # minute-granular and resolves to the minute START, so the seeded Duff
        # tenant must have been created in an EARLIER minute for the historical
        # view to show it: align the capture to the next minute boundary. (The
        # monolithic load took minutes and masked this; the narrowed
        # data_org_registry slice loads within seconds of the capture.)
        now = datetime.now().astimezone()
        boundary = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        time.sleep((boundary - now).total_seconds() + 1)
        return datetime.now().astimezone()

    def test_1_create_a_new_organization(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle, infrastructure_menu: None, date_before: datetime
    ) -> None:
        admin_page.goto("/")
        admin_page.get_by_test_id("sidebar").get_by_role("button", name="Organization").click()
        admin_page.get_by_role("menuitem", name="Tenant").click()
        expect(admin_page.get_by_role("heading", name="Tenant")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Duff")).to_be_visible()

        # fill and submit form for a new organization
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Name *").fill("my-first-tenant")
        admin_page.get_by_label("Description").fill("Testing Infrahub")
        save_screenshot_for_docs(admin_page, "tutorial_1_organization_create")
        admin_page.get_by_role("button", name="Save").click()

        # confirm creation
        # The toast id carries the created node's uuid suffix, so prefix-match it.
        expect(admin_page.locator('[id^="alert-success-Tenant-created"]')).to_contain_text("Tenant created")
        expect(admin_page.get_by_role("link", name="my-first-tenant")).to_be_visible()
        expect(admin_page.get_by_text("Testing Infrahub")).to_be_visible()

    def test_2_create_a_new_branch(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle, date_before: datetime
    ) -> None:
        admin_page.goto("/")
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_test_id("create-branch-button").click()

        expect(admin_page.get_by_text("Create a new branch")).to_be_visible()
        admin_page.get_by_label("New branch name *").fill("cr1234")
        save_screenshot_for_docs(admin_page, "tutorial_1_branch_creation")
        admin_page.get_by_role("button", name="Create a new branch").click()

        expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text("cr1234")
        expect(admin_page).to_have_url(re.compile(r".*?branch=cr1234"))

    def test_3_update_an_organization(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle, date_before: datetime
    ) -> None:
        # go to the newly created organization on branch cr1234
        admin_page.goto("/?branch=cr1234")
        admin_page.get_by_test_id("sidebar").get_by_role("button", name="Organization").click()
        admin_page.get_by_role("menuitem", name="Tenant").click()
        my_first_org_link = admin_page.get_by_test_id("object-items").get_by_role("link", name="my-first-tenant")
        expect(my_first_org_link).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_1_organizations")
        my_first_org_link.click()

        # edit the organization description on branch cr1234
        edit_button = admin_page.get_by_test_id("edit-button")
        expect(edit_button).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_1_organization_details")
        edit_button.click()
        admin_page.get_by_label("Description").fill("Changes from branch cr1234")
        save_screenshot_for_docs(admin_page, "tutorial_1_organization_edit")
        admin_page.get_by_role("button", name="Save").click()

        expect(admin_page.get_by_text("Tenant updated")).to_be_visible()
        expect(admin_page.get_by_text("Changes from branch cr1234")).to_be_visible()

        # see the initial value on the main branch
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_role("option", name="main default").click()
        expect(admin_page.get_by_test_id("object-details").get_by_text("Testing Infrahub")).to_be_visible()

    def test_4_view_diff_and_merge_into_main(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle, infrastructure_menu: None, date_before: datetime
    ) -> None:
        # go to branch cr1234 page
        admin_page.goto("/?branch=cr1234")
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_role("link", name="View all branches").click()
        expect(admin_page.get_by_role("heading", name="Branches")).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_1_branch_list")
        admin_page.get_by_role("link", name="cr1234").click()
        expect(admin_page.get_by_role("heading", name="cr1234")).to_be_visible()

        # trigger the diff update
        admin_page.get_by_text("Data").click()
        expect(admin_page.get_by_text("We are computing the diff")).to_be_visible()
        admin_page.get_by_role("button", name="Refresh").click()
        expect(admin_page.get_by_text("Diff updated!")).to_be_visible()

        # view branch diff
        admin_page.get_by_text("Organization ›Tenant").click()
        expect(admin_page.get_by_text("Testing Infrahub").first).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_1_branch_diff")
        expect(admin_page.get_by_text("Changes from branch cr1234")).to_be_visible()

        # merge branch cr1234 into main
        admin_page.get_by_text("Details", exact=True).click()
        merge_button = admin_page.get_by_role("button", name="Merge")
        expect(merge_button).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_1_branch_details")
        merge_button.click()
        expect(admin_page.locator("#alert-success")).to_contain_text("Branch merge requested!")
        admin_page.get_by_test_id("tasks-accordion").click()
        expect(admin_page.get_by_text("COMPLETEDMerge branch graphQL")).to_be_visible()

        # validate merged changes in main
        admin_page.get_by_test_id("branch-selector-trigger").click()
        admin_page.get_by_role("option", name="main default").click()
        expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text("main")
        admin_page.get_by_test_id("sidebar").get_by_role("button", name="Organization").click()
        admin_page.get_by_role("menuitem", name="Tenant").click()
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Changes from branch cr1234")

    def test_5_browse_historical_data(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle, date_before: datetime
    ) -> None:
        admin_page.goto("/objects/OrganizationTenant")

        # row my-first-tenant is visible at the current time
        expect(admin_page.get_by_role("link", name="my-first-tenant")).to_be_visible()

        # not visible when a date prior to its creation is selected
        admin_page.get_by_test_id("timeframe-selector").click()
        save_screenshot_for_docs(admin_page, "tutorial_2_historical")
        admin_page.get_by_role("option", name=date_before.strftime("%-I:%M %p"), exact=True).click()
        expect(admin_page.get_by_role("link", name="Duff")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Changes from branch cr1234")).not_to_be_visible()

        # visible again once the date input is reset
        admin_page.get_by_test_id("reset-timeframe-selector").click()
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Changes from branch cr1234")
        expect(admin_page.get_by_test_id("object-items")).not_to_contain_text("Testing Infrahub")
