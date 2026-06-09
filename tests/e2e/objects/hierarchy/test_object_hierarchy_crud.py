"""Port of frontend/app/tests/e2e/objects/hierarchy/object-hierarchy-crud.spec.ts.

CRUD operations on hierarchical Location objects (Continent/Country) shown in the
tree + list views. All work happens on a throwaway branch cut from main, which
carries the demo dataset (the hierarchical LocationGeneric model), hence the
infrastructure_data dependency.
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


class TestObjectHierarchyCrud:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-hierarchy-crud")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_perform_crud_operations_on_hierarchical_objects(self, admin_page: Page, branch: str) -> None:
        object_hierarchy_tree = admin_page.get_by_label("Hierarchy tree")

        # should display both tree view and list view for a hierarchical model
        admin_page.goto(f"/objects/LocationGeneric?branch={branch}")
        expect(object_hierarchy_tree).to_be_visible()
        expect(admin_page.get_by_test_id("object-items")).to_be_visible()

        # should create a new top level Continent node and verify it appears in the UI
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Continent Location").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Test Continent")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Continent created")).to_be_visible()
        expect(admin_page.get_by_label("Test Continent")).to_be_visible()

        # should create a child Country node under a collapsed Continent node
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Country Location").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Test Country")
        admin_page.get_by_role("combobox", name="Parent *").click()
        admin_page.get_by_role("option", name="Test Continent").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Country created")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Expand Test Continent")).to_be_visible()

        # should expand parent node to reveal newly created child node
        admin_page.get_by_role("button", name="Expand Test Continent").click()
        expect(object_hierarchy_tree.get_by_text("Test Country")).to_be_visible()

        # should update a Country node's name and verify changes in the tree UI
        admin_page.get_by_test_id("actions-cell-Test Country").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Test Country updated")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Country updated", exact=True)).to_be_visible()
        expect(object_hierarchy_tree.get_by_text("Test Country updated")).to_be_visible()

        # should create a second Country node under the same Continent parent
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Country Location").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Test country 2")
        admin_page.get_by_role("combobox", name="Parent *").click()
        admin_page.get_by_role("option", name="Test Continent").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Country created")).to_be_visible()
        expect(object_hierarchy_tree.get_by_text("Test country 2")).to_be_visible()

        # should delete a Country node and verify its removal from the tree
        admin_page.get_by_test_id("actions-cell-Test country 2").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Object Test country 2 deleted")).to_be_visible()
        expect(object_hierarchy_tree.get_by_text("Test Country updated")).to_be_visible()
        expect(object_hierarchy_tree.get_by_text("Test Country 2")).not_to_be_visible()
