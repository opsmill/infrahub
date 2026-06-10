"""Port of frontend/app/tests/e2e/objects/hierarchy/object-hierarchy-tree-list.spec.ts.

Focused "lite" tree view: it appears on initial load for a child node, refreshes
on sibling add/delete, supports navigation, and falls back to the full tree on
Back or when the current node is deleted. Relies on the demo hierarchy (North
America, United States of America, Canada, Australia in the country list) on a
throwaway branch cut from main, hence the data_locations dependency.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import LocationsHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectHierarchyTreeLite:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_locations: LocationsHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-hierarchy-tree-lite")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_display_lite_tree_on_initial_load_and_refresh_on_node_changes(
        self, admin_page: Page, branch: str
    ) -> None:
        object_hierarchy_tree = admin_page.get_by_label("Hierarchy tree", exact=True)
        object_hierarchy_tree_lite = admin_page.get_by_label("Hierarchy tree lite")

        # navigate to a child node in the hierarchy
        await admin_page.goto(f"/objects/LocationGeneric?branch={branch}")
        await expect(object_hierarchy_tree).to_be_visible()
        await admin_page.get_by_role("button", name="Expand North America").click()
        await object_hierarchy_tree.get_by_text("United States of America").click()
        await expect(admin_page.get_by_test_id("object-header").get_by_text("United States of America")).to_be_visible()

        # reload page - lite tree should appear on initial load
        await admin_page.reload()
        await expect(object_hierarchy_tree_lite).to_be_visible()
        await expect(object_hierarchy_tree).not_to_be_visible()

        # verify lite tree shows parent, current node highlighted, and siblings
        await expect(admin_page.get_by_role("button", name="Back", exact=True)).to_be_visible()
        await expect(object_hierarchy_tree_lite.get_by_text("North America")).to_be_visible()
        await expect(object_hierarchy_tree_lite.get_by_role("row", name="United States of America")).to_contain_class(
            "bg-neutral-100"
        )
        await expect(object_hierarchy_tree_lite.get_by_text("Canada")).to_be_visible()

        await admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="Country").click()
        await expect(admin_page.get_by_role("link", name="Australia")).to_be_visible()

        # add a sibling node - lite tree should refresh
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Country 1")
        await admin_page.get_by_role("combobox", name="Parent *").click()
        await admin_page.get_by_role("option", name="North America").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Country created")).to_be_visible()
        await expect(object_hierarchy_tree_lite.get_by_text("Country 1")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Country 1")).to_be_visible()

        # add another sibling node - lite tree should refresh
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("country 2")
        await admin_page.get_by_role("combobox", name="Parent *").click()
        await admin_page.get_by_role("option", name="North America").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(object_hierarchy_tree_lite.get_by_text("country 2")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Country 2")).to_be_visible()

        # delete a sibling node - lite tree should refresh
        await admin_page.get_by_test_id("actions-cell-country 2").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(object_hierarchy_tree_lite.get_by_text("Country 1")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Country 1")).to_be_visible()
        await expect(object_hierarchy_tree_lite.get_by_text("country 2")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="Country 2")).not_to_be_visible()

        # navigate to sibling via lite tree
        await object_hierarchy_tree_lite.get_by_text("Country 1").click()
        await expect(admin_page.get_by_test_id("object-header").get_by_text("Country 1")).to_be_visible()

        # click Back button - should show full tree
        await admin_page.get_by_role("button", name="Back", exact=True).click()
        await expect(object_hierarchy_tree).to_be_visible()
        await expect(object_hierarchy_tree_lite).not_to_be_visible()

        # delete current node - should fall back to full tree
        await admin_page.reload()
        await expect(admin_page.get_by_test_id("object-header").get_by_text("Country 1")).to_be_visible()
        await expect(object_hierarchy_tree_lite).to_be_visible()
        await expect(object_hierarchy_tree).not_to_be_visible()

        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object Country 1 deleted")).to_be_visible()

        # After deleting the current node, should fall back to full tree (not show error)
        await expect(object_hierarchy_tree).to_be_visible()
        await expect(object_hierarchy_tree_lite).not_to_be_visible()
        # The tree refetch triggered by the delete can hit a load-balanced replica
        # that has not seen the write yet and cache the stale answer (the legacy
        # suite ran against a single server and never had this window), so allow
        # bounded reloads until the deleted node is gone from the tree. Rows
        # render asynchronously after the tree container appears: anchor on a
        # row that always exists before concluding absence, otherwise a check
        # against a half-rendered tree exits the loop while the stale answer is
        # still on its way in.
        deadline = Deadline("the deleted Country 1 to disappear from the tree")
        while True:
            await expect(object_hierarchy_tree).to_be_visible()
            await expect(object_hierarchy_tree.get_by_text("North America")).to_be_visible()
            try:
                await expect(admin_page.get_by_role("link", name="Country 1")).not_to_be_visible(timeout=3_000)
                break
            except AssertionError:
                await deadline.tick()
                await admin_page.reload()
