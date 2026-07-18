"""Port of frontend/app/tests/e2e/role-management/global-permissions.spec.ts.

Global permission CRUD: create (Deny for Anonymous User), verify, edit decision
to Allow, delete. Operates on bootstrap RBAC objects on a throwaway branch.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, get_data_table_row
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from playwright.async_api import Page


class TestGlobalPermissionsCrud:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("global-permissions-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_create_a_new_global_permission(self, admin_page: Page, branch: str) -> None:
        # navigate to global permissions page
        await admin_page.goto(f"/role-management/global-permissions?branch={branch}")
        await expect(get_data_table_row(admin_page, "global:super_admin:allow_all")).to_be_visible()

        # open create form and fill fields
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Action *").click()
        await admin_page.get_by_role("option", name="Update Object Hfid Display").click()
        await admin_page.get_by_label("Decision").click()
        await admin_page.get_by_role("option", name="Deny").click()
        await admin_page.get_by_label("Roles").click()
        await admin_page.get_by_role("option", name="Anonymous User").click()
        await admin_page.get_by_label("Roles").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Global permission created!")).to_be_visible()

        # verify new permission in table
        row = get_data_table_row(admin_page, "global:update_object_hfid_display_label:deny")
        await expect(row.get_by_text("Update Object Hfid Display")).to_be_visible()
        await expect(row.get_by_text("Deny", exact=True)).to_be_visible()
        await expect(row.get_by_text("Anonymous User")).to_be_visible()

        # open edit form and verify field values
        await admin_page.get_by_test_id("actions-cell-global:update_object_hfid_display_label:deny").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await expect(admin_page.get_by_label("Action *")).to_contain_text("Update Object Hfid Display")
        await expect(admin_page.get_by_label("Decision")).to_contain_text("Deny")
        await expect(admin_page.get_by_label("Roles").locator("..")).to_contain_text("Anonymous User")

        # change decision to Allow and save
        await admin_page.get_by_label("Decision").click()
        await admin_page.get_by_role("option", name="Allow").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Global permission updated!")).to_be_visible()

        # verify updated permission in table
        row = get_data_table_row(admin_page, "global:update_object_hfid_display_label:allow_all")
        await expect(row.get_by_text("Update Object Hfid Display")).to_be_visible()
        await expect(row.get_by_text("Allow", exact=True)).to_be_visible()
        await expect(row.get_by_text("Anonymous User")).to_be_visible()

        # delete the permission
        await admin_page.get_by_test_id("actions-cell-global:update_object_hfid_display_label:allow_all").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(
            admin_page.get_by_text("Object global:update_object_hfid_display_label:allow_all deleted")
        ).to_be_visible()
        await expect(
            get_data_table_row(admin_page, "global:update_object_hfid_display_label:allow_all")
        ).not_to_be_visible()
