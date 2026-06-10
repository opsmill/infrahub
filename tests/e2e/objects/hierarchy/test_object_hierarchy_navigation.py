"""Port of frontend/app/tests/e2e/objects/hierarchy/object-hierarchy-navigation.spec.ts.

Navigation in the hierarchical Location tree: expanding nodes via the chevron
without redirecting, navigating via the tree without re-expanding, and keeping
the tree state stable when navigating from the right panel. Relies on the demo
hierarchy (North America, United States of America, Canada) on a throwaway
branch cut from main, hence the data_sites dependency (the asserted USA
"Children5" are the five sites).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectHierarchyNavigation:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-hierarchy-navigation")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_display_correctly(self, admin_page: Page, branch: str) -> None:
        object_hierarchy_tree = admin_page.get_by_label("Hierarchy tree")

        # view tree and list for a hierarchical model
        admin_page.goto(f"/objects/LocationGeneric?branch={branch}")
        expect(object_hierarchy_tree).to_be_visible()
        expect(admin_page.get_by_test_id("object-items")).to_be_visible()

        # display every node type when model is a generic
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Continent")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Country")

        # clicking on a tree chevron should open tree but not redirect page
        admin_page.get_by_role("button", name="Expand North America").click()
        expect(object_hierarchy_tree.get_by_text("Canada")).to_be_visible()
        expect(object_hierarchy_tree.get_by_text("United States of America")).to_be_visible()
        expect(admin_page.get_by_test_id("object-items")).to_be_visible()

        # navigate using tree should not expand tree
        object_hierarchy_tree.get_by_text("United States of America").click()
        expect(admin_page.get_by_text("NameUnited States of America")).to_be_visible()
        expect(admin_page.get_by_text("Children5")).to_be_visible()
        expect(object_hierarchy_tree.get_by_role("row", name="United States of America")).to_contain_class(
            "bg-neutral-100"
        )
        expect(object_hierarchy_tree.get_by_role("button", name="Expand United States of")).to_be_visible()

        # navigate on right panel should not change the tree
        object_hierarchy_tree.get_by_text("North America").click()
        expect(admin_page.get_by_text("NameNorth America")).to_be_visible()
        expect(object_hierarchy_tree.get_by_role("button", name="Collapse North America")).to_be_visible()
        expect(object_hierarchy_tree.get_by_role("button", name="Expand United States of")).to_be_visible()
        expect(object_hierarchy_tree.get_by_role("row", name="North America")).to_contain_class("bg-neutral-100")
