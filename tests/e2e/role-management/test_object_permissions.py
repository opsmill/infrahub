"""Port of frontend/app/tests/e2e/role-management/object-permissions.spec.ts.

Object permission CRUD: create (Builtin / * / view / deny for Administrator),
verify, edit decision, delete. Operates on bootstrap RBAC objects on a
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


class TestObjectPermissionsCrud:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_rbac: RbacHandle) -> AsyncGenerator[str, None]:
        # The default "object:*:*:any:allow_all" permission is created by the rbac slice.
        name = generate_random_branch_name("object-permissions-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_object_permission_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to object permissions page
        await admin_page.goto(f"/role-management/object-permissions?branch={branch}")
        await expect(get_data_table_row(admin_page, "object:*:*:any:allow_all")).to_be_visible()

        # open create form and fill fields
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Namespace").click()
        await admin_page.get_by_role("option", name="Builtin").click()
        await admin_page.get_by_label("Name", exact=True).click()
        await admin_page.get_by_role("option", name="*").click()
        await admin_page.get_by_label("Action *").click()
        await admin_page.get_by_role("option", name="View").click()
        await admin_page.get_by_label("Decision *").click()
        await admin_page.get_by_role("option", name="Deny everywhere").click()
        await admin_page.get_by_label("Roles").click()
        await admin_page.get_by_role("option", name="Administrator", exact=True).click()
        await admin_page.get_by_label("Roles").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Object permission created!")).to_be_visible()

        # verify new permission in table
        row = get_data_table_row(admin_page, "object:Builtin:*:view:deny")
        await expect(row).to_be_visible()
        await expect(row.get_by_text("view", exact=True)).to_be_visible()
        await expect(row.get_by_text("Deny everywhere")).to_be_visible()
        await expect(row.get_by_text("Administrator")).to_be_visible()

        # open edit form and verify field values, then change decision
        await admin_page.get_by_test_id("actions-cell-object:Builtin:*:view:deny").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await expect(admin_page.get_by_label("Namespace")).to_contain_text("Builtin")
        await expect(admin_page.get_by_label("Name", exact=True)).to_contain_text("*")
        await expect(admin_page.get_by_label("Action *")).to_contain_text("View")
        await expect(admin_page.get_by_label("Decision *")).to_contain_text("Deny everywhere")
        await admin_page.get_by_label("Decision *").click()
        await admin_page.get_by_role("option", name="Allow on other branches").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Object permission updated!")).to_be_visible()

        # verify updated permission in table
        row = get_data_table_row(admin_page, "object:Builtin:*:view:allow_other")
        await expect(row).to_be_visible()
        await expect(row.get_by_text("view", exact=True)).to_be_visible()
        await expect(row.get_by_text("Allow on other branches")).to_be_visible()

        # delete the permission
        await admin_page.get_by_test_id("actions-cell-object:Builtin:*:view:allow_other").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object object:Builtin:*:view:allow_other deleted")).to_be_visible()
        await expect(get_data_table_row(admin_page, "object:Builtin:*:view:allow_other")).not_to_be_visible()
