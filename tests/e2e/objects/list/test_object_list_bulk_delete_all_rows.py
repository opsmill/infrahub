"""Port of frontend/app/tests/e2e/objects/list/object-list-bulk-delete-all-rows.spec.ts.

/objects/BuiltinTag - Bulk delete all rows: select every tag row and delete
them all at once. Runs as Admin on a throwaway branch cut from main, which
carries the demo tags (blue/green/red), hence the infrastructure_data dependency.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestBulkDeleteAllRows:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("bulk-delete-all-rows")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_delete_all_rows(self, admin_page: Page, branch: str) -> None:
        # assert we have the initial values
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        expect(admin_page.get_by_role("link", name="green")).to_be_visible()
        expect(admin_page.get_by_test_id("identifier-checkbox-cell")).to_have_count(3)

        # select all rows
        admin_page.get_by_test_id("select-all-rows").click()
        expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).to_be_checked()
        expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()

        # delete all rows
        admin_page.get_by_test_id("object-table-toolbar").get_by_role("button", name="Delete").click()
        expect(admin_page.get_by_text("Are you sure you want to")).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()
        expect(admin_page.get_by_text("No Tag found")).to_be_visible()
