"""Port of frontend/app/tests/e2e/objects/hierarchy/object-hierarchy-crud.spec.ts.

CRUD operations on hierarchical Location objects (Continent/Country) shown in the
tree + list views. All work happens on a throwaway branch cut from main. The test
creates its own continents/countries, so it needs only the location hierarchy
pages, hence the data_locations dependency.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import LocationsHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectHierarchyCrud:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_locations: LocationsHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-hierarchy-crud")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_perform_crud_operations_on_hierarchical_objects(self, admin_page: Page, branch: str) -> None:
        object_hierarchy_tree = admin_page.get_by_label("Hierarchy tree")

        # should display both tree view and list view for a hierarchical model
        await admin_page.goto(f"/objects/LocationGeneric?branch={branch}")
        await expect(object_hierarchy_tree).to_be_visible()
        await expect(admin_page.get_by_test_id("object-items")).to_be_visible()

        # should create a new top level Continent node and verify it appears in the UI
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Continent Location").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Test Continent")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Continent created")).to_be_visible()
        await expect(admin_page.get_by_label("Test Continent")).to_be_visible()

        # should create a child Country node under a collapsed Continent node
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Country Location").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Test Country")
        await admin_page.get_by_role("combobox", name="Parent *").click()
        await admin_page.get_by_role("option", name="Test Continent").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Country created")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Expand Test Continent")).to_be_visible()

        # should expand parent node to reveal newly created child node
        await admin_page.get_by_role("button", name="Expand Test Continent").click()
        await expect(object_hierarchy_tree.get_by_text("Test Country")).to_be_visible()

        # should update a Country node's name and verify changes in the tree UI
        await admin_page.get_by_test_id("actions-cell-Test Country").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Test Country updated")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Country updated", exact=True)).to_be_visible()
        await expect(object_hierarchy_tree.get_by_text("Test Country updated")).to_be_visible()

        # should create a second Country node under the same Continent parent
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Country Location").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Test country 2")
        await admin_page.get_by_role("combobox", name="Parent *").click()
        await admin_page.get_by_role("option", name="Test Continent").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Country created")).to_be_visible()
        await expect(object_hierarchy_tree.get_by_text("Test country 2")).to_be_visible()

        # should delete a Country node and verify its removal from the tree
        await admin_page.get_by_test_id("actions-cell-Test country 2").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object Test country 2 deleted")).to_be_visible()
        await expect(object_hierarchy_tree.get_by_text("Test Country updated")).to_be_visible()
        await expect(object_hierarchy_tree.get_by_text("Test Country 2")).not_to_be_visible()
