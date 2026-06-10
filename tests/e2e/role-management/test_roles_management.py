"""Port of frontend/app/tests/e2e/role-management/roles-management.spec.ts.

Role CRUD: create (with a group + permission), edit, second role, bulk edit
permissions, delete, bulk delete. Operates on bootstrap RBAC objects on a
throwaway branch.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, get_data_table_row
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import RbacHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestRolesCrud:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_rbac: RbacHandle) -> AsyncGenerator[str, None]:
        # The "Administrator" role is created by the rbac slice, not bootstrap.
        name = generate_random_branch_name("role-crud-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_roles_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to roles page
        await admin_page.goto(f"/role-management/roles?branch={branch}")
        await expect(admin_page.get_by_role("link", name="Administrator", exact=True)).to_be_visible()

        # create a new role (with a group and a permission)
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test role")
        await admin_page.get_by_label("Groups").click()
        await admin_page.get_by_test_id("side-panel-container").get_by_text("Infrahub Users").click()
        await admin_page.get_by_label("Groups").click()
        await admin_page.get_by_test_id("side-panel-container").get_by_label("Permissions").click()
        await (
            admin_page.get_by_test_id("side-panel-container")
            .get_by_role("option", name="global:super_admin:allow_all")
            .click()
        )
        await admin_page.get_by_test_id("side-panel-container").get_by_label("Permissions").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Role created!")).to_be_visible()

        # verify role columns are displayed
        row = get_data_table_row(admin_page, "test role")
        await expect(row.get_by_role("link", name="Infrahub Users")).to_be_visible()
        await expect(row.get_by_text("global:super_admin:allow_all")).to_be_visible()

        # open edit form and verify field values
        await admin_page.get_by_test_id("actions-cell-test role").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await expect(admin_page.get_by_role("textbox", name="Name *")).to_have_value("test role")
        await expect(admin_page.get_by_label("Groups").locator("..")).to_contain_text("Infrahub Users")
        await expect(admin_page.get_by_label("Permissions").locator("..")).to_contain_text(
            "global:super_admin:allow_all"
        )

        # update the role name and save
        await admin_page.get_by_role("textbox", name="Name *").fill("test role updated")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Role updated!")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test role updated")).to_be_visible()

        # create a second role
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test role 2")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Role created!")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()

        # bulk edit both roles
        await (
            admin_page.get_by_role("link", name="test role updated")
            .locator("..")
            .get_by_test_id("identifier-checkbox-cell")
            .click()
        )
        await (
            admin_page.get_by_role("link", name="test role 2")
            .locator("..")
            .get_by_test_id("identifier-checkbox-cell")
            .click()
        )
        await admin_page.get_by_role("button", name="Edit").click()
        await admin_page.get_by_role("button", name="Add Permissions").click()
        await admin_page.get_by_role("option", name="global:super_admin:allow_all").click()
        await admin_page.get_by_role("button", name="Add Permissions").click()
        await admin_page.get_by_role("button", name="Save").click()
        await admin_page.get_by_role("heading", name="2 / 2 objects updated").click()
        await admin_page.keyboard.press("Escape")

        # verify bulk edit applied permissions
        row1 = get_data_table_row(admin_page, "test role updated")
        row2 = get_data_table_row(admin_page, "test role 2")
        await expect(row1.get_by_text("global:super_admin:allow_all")).to_be_visible()
        await expect(row2.get_by_text("global:super_admin:allow_all")).to_be_visible()

        # delete the first role
        await admin_page.get_by_test_id("actions-cell-test role updated").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object test role updated deleted")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test role updated")).not_to_be_visible()

        # bulk delete the remaining role
        await expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()
        await admin_page.get_by_role("button", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test role 2")).not_to_be_visible()
