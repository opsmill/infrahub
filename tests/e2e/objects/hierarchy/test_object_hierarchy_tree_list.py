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
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import LocationsHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectHierarchyTreeLite:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_locations: LocationsHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-hierarchy-tree-lite")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_display_lite_tree_on_initial_load_and_refresh_on_node_changes(
        self, admin_page: Page, branch: str
    ) -> None:
        object_hierarchy_tree = admin_page.get_by_label("Hierarchy tree", exact=True)
        object_hierarchy_tree_lite = admin_page.get_by_label("Hierarchy tree lite")

        # navigate to a child node in the hierarchy
        admin_page.goto(f"/objects/LocationGeneric?branch={branch}")
        expect(object_hierarchy_tree).to_be_visible()
        admin_page.get_by_role("button", name="Expand North America").click()
        object_hierarchy_tree.get_by_text("United States of America").click()
        expect(admin_page.get_by_test_id("object-header").get_by_text("United States of America")).to_be_visible()

        # reload page - lite tree should appear on initial load
        admin_page.reload()
        expect(object_hierarchy_tree_lite).to_be_visible()
        expect(object_hierarchy_tree).not_to_be_visible()

        # verify lite tree shows parent, current node highlighted, and siblings
        expect(admin_page.get_by_role("button", name="Back", exact=True)).to_be_visible()
        expect(object_hierarchy_tree_lite.get_by_text("North America")).to_be_visible()
        expect(object_hierarchy_tree_lite.get_by_role("row", name="United States of America")).to_contain_class(
            "bg-neutral-100"
        )
        expect(object_hierarchy_tree_lite.get_by_text("Canada")).to_be_visible()

        admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="Country").click()
        expect(admin_page.get_by_role("link", name="Australia")).to_be_visible()

        # add a sibling node - lite tree should refresh
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Country 1")
        admin_page.get_by_role("combobox", name="Parent *").click()
        admin_page.get_by_role("option", name="North America").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Country created")).to_be_visible()
        expect(object_hierarchy_tree_lite.get_by_text("Country 1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Country 1")).to_be_visible()

        # add another sibling node - lite tree should refresh
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("country 2")
        admin_page.get_by_role("combobox", name="Parent *").click()
        admin_page.get_by_role("option", name="North America").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(object_hierarchy_tree_lite.get_by_text("country 2")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Country 2")).to_be_visible()

        # delete a sibling node - lite tree should refresh
        admin_page.get_by_test_id("actions-cell-country 2").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(object_hierarchy_tree_lite.get_by_text("Country 1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Country 1")).to_be_visible()
        expect(object_hierarchy_tree_lite.get_by_text("country 2")).not_to_be_visible()
        expect(admin_page.get_by_role("link", name="Country 2")).not_to_be_visible()

        # navigate to sibling via lite tree
        object_hierarchy_tree_lite.get_by_text("Country 1").click()
        expect(admin_page.get_by_test_id("object-header").get_by_text("Country 1")).to_be_visible()

        # click Back button - should show full tree
        admin_page.get_by_role("button", name="Back", exact=True).click()
        expect(object_hierarchy_tree).to_be_visible()
        expect(object_hierarchy_tree_lite).not_to_be_visible()

        # delete current node - should fall back to full tree
        admin_page.reload()
        expect(admin_page.get_by_test_id("object-header").get_by_text("Country 1")).to_be_visible()
        expect(object_hierarchy_tree_lite).to_be_visible()
        expect(object_hierarchy_tree).not_to_be_visible()

        admin_page.get_by_test_id("object-details-menu").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object Country 1 deleted")).to_be_visible()

        # After deleting the current node, should fall back to full tree (not show error)
        expect(object_hierarchy_tree).to_be_visible()
        expect(object_hierarchy_tree_lite).not_to_be_visible()
        expect(admin_page.get_by_role("link", name="Country 1")).not_to_be_visible()
