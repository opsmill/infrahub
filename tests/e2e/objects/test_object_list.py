"""Port of frontend/app/tests/e2e/objects/list/object-list.spec.ts.

/objects/:objectKind list view: unauthenticated vs admin behaviour, generic
"kind" column, relationship navigation, open-in-new-tab, and a full
create/edit/delete cycle on BuiltinTag. All work happens on a throwaway branch
created via the API; the branch is cut from main, hence the data_topology
dependency: the arista_devices Members tab content is populated by the topology
stage (tags blue/green and the Juniper-platform device come transitively).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import TopologyHandle
    from helpers import BranchAPI
    from playwright.async_api import BrowserContext, Page


class TestObjectList:
    @pytest.fixture
    async def branch_name(
        self,
        branch_api: BranchAPI,
        data_topology: TopologyHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-list")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    # --- when not logged in --------------------------------------------------
    async def test_cannot_create_a_new_object(self, page: Page, branch_name: str) -> None:
        await page.goto(f"/objects/BuiltinTag?branch={branch_name}")

        await expect(page.get_by_role("heading", name="Tag")).to_be_visible()
        await expect(
            page.get_by_text("Standard Tag object to attach to other objects to provide some context.")
        ).to_be_visible()
        await expect(page.get_by_test_id("create-object-button")).to_be_disabled()
        await page.get_by_test_id("actions-cell-blue").click()
        await expect(page.get_by_role("menuitem", name="Delete")).to_be_disabled()

    async def test_cannot_select_rows(self, page: Page, branch_name: str) -> None:
        await page.goto(f"/objects/BuiltinTag?branch={branch_name}")
        await expect(page.get_by_role("link", name="blue")).to_be_visible()
        await expect(page.get_by_test_id("select-all-rows")).not_to_be_visible()
        # The row checkbox is auth-gated inside identifier-cell (the cell itself still renders
        # the object link), so assert the checkbox role is absent rather than the cell.
        await expect(page.get_by_test_id("identifier-cell").get_by_role("checkbox")).not_to_be_visible()

    async def test_open_object_details_in_a_new_tab(
        self, page: Page, context: BrowserContext, branch_name: str
    ) -> None:
        await page.goto(f"/objects/BuiltinTag?branch={branch_name}")

        object_details_link = page.get_by_role("link", name="blue")
        link_href = await object_details_link.get_attribute("href")
        assert link_href is not None
        async with context.expect_page() as new_tab_info:
            await object_details_link.click(button="middle")

        new_tab = await new_tab_info.value
        await new_tab.wait_for_url(lambda url: link_href in url)
        assert link_href in new_tab.url

    # --- when logged in as Admin --------------------------------------------
    async def test_kind_column_displayed_for_generic(self, admin_page: Page, branch_name: str) -> None:
        await admin_page.goto(f"/objects/CoreGroup?branch={branch_name}")
        await expect(admin_page.get_by_test_id("kind-header-cell")).to_be_visible()

    async def test_default_column_when_relationship_has_no_attributes(self, admin_page: Page, branch_name: str) -> None:
        await admin_page.goto(f"/objects/CoreStandardGroup?branch={branch_name}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name="arista_devices").click()
        await admin_page.get_by_text("Members").click()
        await expect(admin_page.get_by_text("Node", exact=True)).to_be_visible()
        await expect(admin_page.get_by_test_id("kind-header-cell")).to_be_visible()

    async def test_clicking_relationship_value_redirects_to_details(self, admin_page: Page, branch_name: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch_name}")
        await admin_page.get_by_role("link", name="Juniper JunOS").first.click()
        await expect(admin_page.get_by_text("NameJuniper JunOS", exact=True)).to_be_visible()
        assert "/objects/InfraPlatform/" in admin_page.url

    async def test_manage_objects(self, admin_page: Page, branch_name: str) -> None:
        await admin_page.goto(f"/objects/BuiltinTag?branch={branch_name}")
        await expect(admin_page.get_by_role("heading", name="Tag")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="green")).to_be_visible()
        await expect(admin_page.get_by_test_id("create-object-button")).to_be_enabled()

        # create a new item from the list
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Name *").fill("crud")
        await admin_page.get_by_label("Description").fill("initial description")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_role("link", name="crud")).to_be_visible()
        await expect(admin_page.get_by_text("initial description")).to_be_visible()

        # edit the item
        await admin_page.get_by_test_id("actions-cell-crud").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_label("Description").fill("description updated")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Tag updated")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="crud")).to_be_visible()
        await expect(admin_page.get_by_text("description updated")).to_be_visible()

        # delete the item
        await admin_page.get_by_test_id("actions-cell-crud").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_be_visible()
        await expect(admin_page.get_by_text("Are you sure you want to remove crud")).to_be_visible()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object crud deleted")).to_be_visible()
