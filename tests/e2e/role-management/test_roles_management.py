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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import RbacHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestRolesCrud:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI, data_rbac: RbacHandle) -> Generator[str, None, None]:
        # The "Administrator" role is created by the rbac slice, not bootstrap.
        name = generate_random_branch_name("role-crud-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_roles_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to roles page
        admin_page.goto(f"/role-management/roles?branch={branch}")
        expect(admin_page.get_by_role("link", name="Administrator", exact=True)).to_be_visible()

        # create a new role (with a group and a permission)
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test role")
        admin_page.get_by_label("Groups").click()
        admin_page.get_by_test_id("side-panel-container").get_by_text("Infrahub Users").click()
        admin_page.get_by_label("Groups").click()
        admin_page.get_by_test_id("side-panel-container").get_by_label("Permissions").click()
        admin_page.get_by_test_id("side-panel-container").get_by_role(
            "option", name="global:super_admin:allow_all"
        ).click()
        admin_page.get_by_test_id("side-panel-container").get_by_label("Permissions").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Role created!")).to_be_visible()

        # verify role columns are displayed
        row = get_data_table_row(admin_page, "test role")
        expect(row.get_by_role("link", name="Infrahub Users")).to_be_visible()
        expect(row.get_by_text("global:super_admin:allow_all")).to_be_visible()

        # open edit form and verify field values
        admin_page.get_by_test_id("actions-cell-test role").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        expect(admin_page.get_by_role("textbox", name="Name *")).to_have_value("test role")
        expect(admin_page.get_by_label("Groups").locator("..")).to_contain_text("Infrahub Users")
        expect(admin_page.get_by_label("Permissions").locator("..")).to_contain_text("global:super_admin:allow_all")

        # update the role name and save
        admin_page.get_by_role("textbox", name="Name *").fill("test role updated")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Role updated!")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test role updated")).to_be_visible()

        # create a second role
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test role 2")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Role created!")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()

        # bulk edit both roles
        admin_page.get_by_role("link", name="test role updated").locator("..").get_by_test_id(
            "identifier-checkbox-cell"
        ).click()
        admin_page.get_by_role("link", name="test role 2").locator("..").get_by_test_id(
            "identifier-checkbox-cell"
        ).click()
        admin_page.get_by_role("button", name="Edit").click()
        admin_page.get_by_role("button", name="Add Permissions").click()
        admin_page.get_by_role("option", name="global:super_admin:allow_all").click()
        admin_page.get_by_role("button", name="Add Permissions").click()
        admin_page.get_by_role("button", name="Save").click()
        admin_page.get_by_role("heading", name="2 / 2 objects updated").click()
        admin_page.keyboard.press("Escape")

        # verify bulk edit applied permissions
        row1 = get_data_table_row(admin_page, "test role updated")
        row2 = get_data_table_row(admin_page, "test role 2")
        expect(row1.get_by_text("global:super_admin:allow_all")).to_be_visible()
        expect(row2.get_by_text("global:super_admin:allow_all")).to_be_visible()

        # delete the first role
        admin_page.get_by_test_id("actions-cell-test role updated").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object test role updated deleted")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test role updated")).not_to_be_visible()

        # bulk delete the remaining role
        expect(admin_page.get_by_role("link", name="test role 2")).to_be_visible()
        admin_page.get_by_role("button", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test role 2")).not_to_be_visible()
