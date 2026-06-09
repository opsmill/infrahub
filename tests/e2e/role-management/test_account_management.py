"""Port of frontend/app/tests/e2e/role-management/account-management.spec.ts.

Account CRUD: create, edit, second account, bulk edit, bulk add/remove to a
group, delete, bulk delete. Operates on the bootstrap RBAC objects (admin
account, "Infrahub Users" group) on its own throwaway branch.
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


class TestAccountCrud:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI) -> Generator[str, None, None]:
        name = generate_random_branch_name("account-management-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_account_crud_and_group_management(self, admin_page: Page, branch: str) -> None:
        # navigate to role management page
        admin_page.goto(f"/role-management?branch={branch}")
        expect(admin_page.get_by_role("link", name="Admin", exact=True)).to_be_visible()

        # create a new account
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("account test")
        admin_page.get_by_role("textbox", name="Password *").fill("123")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Account created!")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Account Test")).to_be_visible()

        # open edit form and verify field values
        get_data_table_row(admin_page, "Account Test").get_by_test_id("actions-cell-Account Test").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        expect(admin_page.get_by_role("textbox", name="Name *")).to_have_value("account test")
        expect(admin_page.get_by_role("textbox", name="Description")).to_have_value("")

        # update the account description and save
        admin_page.get_by_role("textbox", name="Description").fill("test edit")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Account updated!")).to_be_visible()
        expect(get_data_table_row(admin_page, "Account Test").get_by_text("test edit")).to_be_visible()

        # create a second account
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Account test 2")
        admin_page.get_by_role("textbox", name="Password *").fill("123")
        admin_page.get_by_role("button", name="Save").click()
        expect(get_data_table_row(admin_page, "Account Test 2")).to_be_visible()

        # bulk edit both accounts
        get_data_table_row(admin_page, "Account Test").get_by_test_id("identifier-checkbox-cell").click()
        get_data_table_row(admin_page, "Account Test 2").get_by_test_id("identifier-checkbox-cell").click()
        admin_page.get_by_role("button", name="Edit").click()
        admin_page.get_by_role("textbox", name="Description").fill("test bulk edit")
        admin_page.get_by_role("button", name="Save").click()
        admin_page.get_by_role("heading", name="2 / 2 objects updated").click()
        admin_page.keyboard.press("Escape")
        expect(get_data_table_row(admin_page, "Account Test").get_by_text("test bulk edit")).to_be_visible()
        expect(get_data_table_row(admin_page, "Account Test 2").get_by_text("test bulk edit")).to_be_visible()

        # bulk add accounts to a group
        admin_page.get_by_role("button", name="Add to groups").click()
        admin_page.get_by_role("option", name="Infrahub Users").click()
        admin_page.get_by_role("button", name="Validate").click()
        expect(admin_page.get_by_role("heading", name="1 / 1 group updated successfully")).to_be_visible()
        admin_page.get_by_role("button", name="Close").click()
        expect(
            get_data_table_row(admin_page, "Account Test").get_by_role("link", name="Infrahub Users")
        ).to_be_visible()
        expect(
            get_data_table_row(admin_page, "Account Test 2").get_by_role("link", name="Infrahub Users")
        ).to_be_visible()

        # bulk remove accounts from a group
        admin_page.get_by_role("button", name="Remove from groups").click()
        admin_page.get_by_role("option", name="Infrahub Users").click()
        admin_page.get_by_role("button", name="Validate").click()
        expect(admin_page.get_by_role("heading", name="1 / 1 group updated successfully")).to_be_visible()
        admin_page.get_by_role("button", name="Close").click()
        expect(
            get_data_table_row(admin_page, "Account Test").get_by_role("link", name="Infrahub Users")
        ).not_to_be_visible()
        expect(
            get_data_table_row(admin_page, "Account Test 2").get_by_role("link", name="Infrahub Users")
        ).not_to_be_visible()

        # delete the first account
        get_data_table_row(admin_page, "Account Test").get_by_test_id("actions-cell-Account Test").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object Account Test deleted")).to_be_visible()
        expect(get_data_table_row(admin_page, "Account Test 2")).to_be_visible()
        expect(get_data_table_row(admin_page, "Account Test")).not_to_be_visible()

        # bulk delete the remaining account
        admin_page.get_by_role("button", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        expect(get_data_table_row(admin_page, "Account Test 2")).not_to_be_visible()
