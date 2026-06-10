"""Port of frontend/app/tests/e2e/objects/object-details-delete.spec.ts.

Delete an object from its detail view and confirm the user stays on the same
branch afterwards. Operates on the seeded `blue` tag (the data_org_registry
dependency) on a throwaway branch; the branch keeps the literal name
`object-details-delete` because the test asserts the branch selector contains
that name.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import OrgRegistryHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectDetailsDelete:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_org_registry: OrgRegistryHandle,
    ) -> Generator[str, None, None]:
        name = "object-details-delete"
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_delete_an_object_and_redirects_to_list_view(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text("object-details-delete")

        # go to blue tag details
        admin_page.get_by_role("link", name="blue").click()

        # delete blue tag
        admin_page.get_by_test_id("object-details-menu").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            'Are you sure you want to remove the Tag"blue"?'
        )
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object blue deleted")).to_be_visible()
        expect(admin_page.get_by_role("link", name="blue")).to_be_hidden()

        # user is still on the same branch after delete
        expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text("object-details-delete")
