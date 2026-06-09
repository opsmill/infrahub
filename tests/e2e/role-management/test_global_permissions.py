"""Port of frontend/app/tests/e2e/role-management/global-permissions.spec.ts.

Global permission CRUD: create (Deny for Anonymous User), verify, edit decision
to Allow, delete. Operates on bootstrap RBAC objects on a throwaway branch.
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


class TestGlobalPermissionsCrud:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI) -> Generator[str, None, None]:
        name = generate_random_branch_name("global-permissions-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_create_a_new_global_permission(self, admin_page: Page, branch: str) -> None:
        # navigate to global permissions page
        admin_page.goto(f"/role-management/global-permissions?branch={branch}")
        expect(get_data_table_row(admin_page, "global:super_admin:allow_all")).to_be_visible()

        # open create form and fill fields
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Action *").click()
        admin_page.get_by_role("option", name="Update Object Hfid Display").click()
        admin_page.get_by_label("Decision").click()
        admin_page.get_by_role("option", name="Deny").click()
        admin_page.get_by_label("Roles").click()
        admin_page.get_by_role("option", name="Anonymous User").click()
        admin_page.get_by_label("Roles").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Global permission created!")).to_be_visible()

        # verify new permission in table
        row = get_data_table_row(admin_page, "global:update_object_hfid_display_label:deny")
        expect(row.get_by_text("Update Object Hfid Display")).to_be_visible()
        expect(row.get_by_text("Deny", exact=True)).to_be_visible()
        expect(row.get_by_text("Anonymous User")).to_be_visible()

        # open edit form and verify field values
        admin_page.get_by_test_id("actions-cell-global:update_object_hfid_display_label:deny").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        expect(admin_page.get_by_label("Action *")).to_contain_text("Update Object Hfid Display")
        expect(admin_page.get_by_label("Decision")).to_contain_text("Deny")
        expect(admin_page.get_by_label("Roles").locator("..")).to_contain_text("Anonymous User")

        # change decision to Allow and save
        admin_page.get_by_label("Decision").click()
        admin_page.get_by_role("option", name="Allow").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Global permission updated!")).to_be_visible()

        # verify updated permission in table
        row = get_data_table_row(admin_page, "global:update_object_hfid_display_label:allow_all")
        expect(row.get_by_text("Update Object Hfid Display")).to_be_visible()
        expect(row.get_by_text("Allow", exact=True)).to_be_visible()
        expect(row.get_by_text("Anonymous User")).to_be_visible()

        # delete the permission
        admin_page.get_by_test_id("actions-cell-global:update_object_hfid_display_label:allow_all").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(
            admin_page.get_by_text("Object global:update_object_hfid_display_label:allow_all deleted")
        ).to_be_visible()
        expect(get_data_table_row(admin_page, "global:update_object_hfid_display_label:allow_all")).not_to_be_visible()
