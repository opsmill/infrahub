"""Port of frontend/app/tests/e2e/role-management/group-management.spec.ts.

Group CRUD: create, verify columns, edit, second group, bulk edit, delete, bulk
delete. Operates on bootstrap RBAC objects on a throwaway branch.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, get_data_table_row
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestGroupCrud:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI) -> Generator[str, None, None]:
        name = generate_random_branch_name("group-management-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_group_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to groups page
        admin_page.goto(f"/role-management/groups?branch={branch}")
        expect(get_data_table_row(admin_page, "Infrahub Users")).to_be_visible()

        # create a new group
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test group")
        admin_page.get_by_role("textbox", name="Label").fill("Test Group Label")
        admin_page.get_by_role("textbox", name="Description").fill("A test group")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Group created!")).to_be_visible()

        # verify group columns are displayed
        row = get_data_table_row(admin_page, "test group")
        expect(row).to_be_visible()
        expect(row.get_by_text("Test Group Label")).to_be_visible()
        expect(row.get_by_text("A test group")).to_be_visible()

        # open edit form and verify field values
        get_data_table_row(admin_page, "test group").get_by_test_id("actions-cell-test group").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        expect(admin_page.get_by_role("textbox", name="Name *")).to_have_value("test group")
        expect(admin_page.get_by_role("textbox", name="Label")).to_have_value("Test Group Label")
        expect(admin_page.get_by_role("textbox", name="Description")).to_have_value("A test group")

        # update the group description and save
        admin_page.get_by_role("textbox", name="Description").fill("updated description")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Group updated!")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group").get_by_text("updated description")).to_be_visible()

        # create a second group
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test group 2")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Group created!")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group 2")).to_be_visible()

        # bulk edit both groups
        get_data_table_row(admin_page, "test group").get_by_test_id("identifier-checkbox-cell").click()
        get_data_table_row(admin_page, "test group 2").get_by_test_id("identifier-checkbox-cell").click()
        admin_page.get_by_role("button", name="Edit").click()
        admin_page.get_by_role("textbox", name="Description").fill("bulk edited")
        admin_page.get_by_role("button", name="Save").click()
        admin_page.get_by_role("heading", name="2 / 2 objects updated").click()
        admin_page.keyboard.press("Escape")
        expect(get_data_table_row(admin_page, "test group").get_by_text("bulk edited")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group 2").get_by_text("bulk edited")).to_be_visible()

        # delete the first group
        get_data_table_row(admin_page, "test group").get_by_test_id("actions-cell-test group").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object test group deleted")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group 2")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group")).not_to_be_visible()

        # bulk delete the remaining group
        admin_page.get_by_role("button", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        expect(get_data_table_row(admin_page, "test group 2")).not_to_be_visible()
