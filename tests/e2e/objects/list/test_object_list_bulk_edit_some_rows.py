"""Port of frontend/app/tests/e2e/objects/list/object-list-bulk-edit-some-rows.spec.ts.

/objects/:objectKind - Bulk edit some rows: select three InfraDevice rows and
apply a single set of changes (site, description, type, status, role, loopback
pool) to all of them at once. Runs as Admin on a throwaway branch cut from main,
which carries the demo devices (atl1-*), site den1, statuses/roles, and the
Loopbacks pool, hence the infrastructure_data dependency.
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


class TestBulkEditSomeRows:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("bulk-edit-some-rows")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_be_able_to_update_multiple_objects_at_once(self, admin_page: Page, branch: str) -> None:
        # navigate to objects page and select items
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        admin_page.get_by_test_id("identifier-checkbox-cell").nth(0).click()
        admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        admin_page.get_by_test_id("identifier-checkbox-cell").nth(2).click()
        admin_page.get_by_test_id("object-table-toolbar").get_by_role("button", name="Edit").click()

        # verify bulk edit panel is displayed correctly
        expect(admin_page.get_by_role("heading", name="objects selected for editing")).to_be_visible()
        expect(admin_page.get_by_text("atl1-core1Waiting for changes")).to_be_visible()
        expect(admin_page.get_by_text("atl1-core2Waiting for changes")).to_be_visible()
        expect(admin_page.get_by_text("atl1-edge1Waiting for changes")).to_be_visible()
        expect(admin_page.get_by_role("heading", name="Set bulk changes")).to_be_visible()
        expect(admin_page.get_by_label("Description")).to_be_visible()
        expect(admin_page.get_by_label("Name")).to_be_hidden()
        expect(admin_page.get_by_label("Member of groups")).to_be_hidden()
        expect(admin_page.get_by_label("Edit").get_by_text("Description")).to_be_visible()

        # make bulk changes
        admin_page.get_by_label("Site").click()
        admin_page.get_by_role("option", name="den1").click()
        admin_page.get_by_label("Description").fill("test desc")
        admin_page.get_by_label("Type").fill("test type")
        admin_page.get_by_label("Status").click()
        admin_page.get_by_role("option", name="Drained Temporarily taken out").click()
        admin_page.get_by_label("Role").click()
        admin_page.get_by_role("option", name="Leaf Switch Top of Rack part").click()
        admin_page.get_by_test_id("select-open-pool-option-button").click()
        admin_page.get_by_role("option", name="Loopbacks pool").click()
        admin_page.get_by_role("button", name="Save").click()

        # verify changes were applied successfully
        expect(admin_page.get_by_text("atl1-core1success")).to_be_visible()
        expect(admin_page.get_by_text("atl1-core2success")).to_be_visible()
        expect(admin_page.get_by_text("atl1-edge1success")).to_be_visible()
        expect(admin_page.get_by_text("Drained").nth(0)).to_be_visible()
        expect(admin_page.get_by_text("Drained").nth(1)).to_be_visible()
        expect(admin_page.get_by_text("Drained").nth(2)).to_be_visible()
