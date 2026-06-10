"""Port of frontend/app/tests/e2e/objects/list/object-list-bulk-delete-some-rows.spec.ts.

/objects/BuiltinTag - Bulk delete some rows: select the blue and green tag rows,
delete them, and assert only red remains. Runs as Admin on a throwaway branch
cut from main, hence the data_org_registry dependency (the seeded blue/green/red
tags). The source describe is serial but has a single self-contained test, so
order is irrelevant.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import OrgRegistryHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestBulkDeleteSomeRows:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_org_registry: OrgRegistryHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("bulk-delete-some-rows")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_be_able_to_delete_objects(self, admin_page: Page, branch: str) -> None:
        # assert we have the initial values
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        expect(admin_page.get_by_role("button", name="Add Tag")).to_be_visible()
        expect(
            admin_page.locator("a").filter(has_text="blue").locator("..").get_by_test_id("identifier-checkbox-cell")
        ).to_be_visible()
        expect(
            admin_page.locator("a").filter(has_text="green").locator("..").get_by_test_id("identifier-checkbox-cell")
        ).to_be_visible()

        # proceed delete
        admin_page.locator("a").filter(has_text="blue").locator("..").get_by_test_id("identifier-checkbox-cell").click()
        admin_page.locator("a").filter(has_text="green").locator("..").get_by_test_id(
            "identifier-checkbox-cell"
        ).click()

        admin_page.get_by_test_id("object-table-toolbar").get_by_role("button", name="Delete").click()
        expect(admin_page.get_by_text("Are you sure you want to")).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Objects deleted!")).to_be_visible()

        # assert the objects were deleted
        expect(admin_page.get_by_role("link", name="red")).to_be_visible()
        expect(admin_page.get_by_role("link", name="blue")).not_to_be_visible()
        expect(admin_page.get_by_role("link", name="green")).not_to_be_visible()
