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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import RbacHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectPermissionsCrud:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI, data_rbac: RbacHandle) -> Generator[str, None, None]:
        # The default "object:*:*:any:allow_all" permission is created by the rbac slice.
        name = generate_random_branch_name("object-permissions-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_object_permission_crud(self, admin_page: Page, branch: str) -> None:
        # navigate to object permissions page
        admin_page.goto(f"/role-management/object-permissions?branch={branch}")
        expect(get_data_table_row(admin_page, "object:*:*:any:allow_all")).to_be_visible()

        # open create form and fill fields
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Namespace").click()
        admin_page.get_by_role("option", name="Builtin").click()
        admin_page.get_by_label("Name", exact=True).click()
        admin_page.get_by_role("option", name="*").click()
        admin_page.get_by_label("Action *").click()
        admin_page.get_by_role("option", name="View").click()
        admin_page.get_by_label("Decision *").click()
        admin_page.get_by_role("option", name="Deny everywhere").click()
        admin_page.get_by_label("Roles").click()
        admin_page.get_by_role("option", name="Administrator", exact=True).click()
        admin_page.get_by_label("Roles").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Object permission created!")).to_be_visible()

        # verify new permission in table
        row = get_data_table_row(admin_page, "object:Builtin:*:view:deny")
        expect(row).to_be_visible()
        expect(row.get_by_text("view", exact=True)).to_be_visible()
        expect(row.get_by_text("Deny everywhere")).to_be_visible()
        expect(row.get_by_text("Administrator")).to_be_visible()

        # open edit form and verify field values, then change decision
        admin_page.get_by_test_id("actions-cell-object:Builtin:*:view:deny").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        expect(admin_page.get_by_label("Namespace")).to_contain_text("Builtin")
        expect(admin_page.get_by_label("Name", exact=True)).to_contain_text("*")
        expect(admin_page.get_by_label("Action *")).to_contain_text("View")
        expect(admin_page.get_by_label("Decision *")).to_contain_text("Deny everywhere")
        admin_page.get_by_label("Decision *").click()
        admin_page.get_by_role("option", name="Allow on other branches").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Object permission updated!")).to_be_visible()

        # verify updated permission in table
        row = get_data_table_row(admin_page, "object:Builtin:*:view:allow_other")
        expect(row).to_be_visible()
        expect(row.get_by_text("view", exact=True)).to_be_visible()
        expect(row.get_by_text("Allow on other branches")).to_be_visible()

        # delete the permission
        admin_page.get_by_test_id("actions-cell-object:Builtin:*:view:allow_other").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object object:Builtin:*:view:allow_other deleted")).to_be_visible()
        expect(get_data_table_row(admin_page, "object:Builtin:*:view:allow_other")).not_to_be_visible()
