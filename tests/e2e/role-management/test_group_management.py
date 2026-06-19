"""Port of frontend/app/tests/e2e/role-management/group-management.spec.ts.

Group CRUD: create, verify columns, edit, second group, bulk edit, delete, bulk
delete. Operates on bootstrap RBAC objects on a throwaway branch.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, get_data_table_row
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from playwright.async_api import Page


class TestGroupCrud:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("group-management-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_group_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to groups page
        await admin_page.goto(f"/role-management/groups?branch={branch}")
        await expect(get_data_table_row(admin_page, "Infrahub Users")).to_be_visible()

        # create a new group
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test group")
        await admin_page.get_by_role("textbox", name="Label").fill("Test Group Label")
        await admin_page.get_by_role("textbox", name="Description").fill("A test group")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Group created!")).to_be_visible()

        # verify group columns are displayed
        row = get_data_table_row(admin_page, "test group")
        await expect(row).to_be_visible()
        await expect(row.get_by_text("Test Group Label")).to_be_visible()
        await expect(row.get_by_text("A test group")).to_be_visible()

        # open edit form and verify field values
        await get_data_table_row(admin_page, "test group").get_by_test_id("actions-cell-test group").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await expect(admin_page.get_by_role("textbox", name="Name *")).to_have_value("test group")
        await expect(admin_page.get_by_role("textbox", name="Label")).to_have_value("Test Group Label")
        await expect(admin_page.get_by_role("textbox", name="Description")).to_have_value("A test group")

        # update the group description and save
        await admin_page.get_by_role("textbox", name="Description").fill("updated description")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Group updated!")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group").get_by_text("updated description")).to_be_visible()

        # create a second group
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test group 2")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Group created!")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group 2")).to_be_visible()

        # bulk edit both groups
        await get_data_table_row(admin_page, "test group").get_by_test_id("identifier-checkbox-cell").click()
        await get_data_table_row(admin_page, "test group 2").get_by_test_id("identifier-checkbox-cell").click()
        await admin_page.get_by_role("button", name="Edit").click()
        await admin_page.get_by_role("textbox", name="Description").fill("bulk edited")
        await admin_page.get_by_role("button", name="Save").click()
        await admin_page.get_by_role("heading", name="2 / 2 objects updated").click()
        await admin_page.keyboard.press("Escape")
        await expect(get_data_table_row(admin_page, "test group").get_by_text("bulk edited")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group 2").get_by_text("bulk edited")).to_be_visible()

        # delete the first group
        await get_data_table_row(admin_page, "test group").get_by_test_id("actions-cell-test group").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object test group deleted")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group 2")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group")).not_to_be_visible()

        # bulk delete the remaining group
        await admin_page.get_by_role("button", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        await expect(get_data_table_row(admin_page, "test group 2")).not_to_be_visible()
