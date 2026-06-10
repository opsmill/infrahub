"""Port of frontend/app/tests/e2e/objects/hierarchy/relationship-hierarchical-input.spec.ts.

Selecting a Site through the Explore tab of a hierarchical relationship input on
the InfraDevice creation form: drilling North America -> United States of America
-> atl1. Relies on the demo hierarchy and the atl1 site on a throwaway branch cut
from main, hence the data_sites dependency (the atl1 site option and the Explore
drill-down to atl1).
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


class TestRelationshipHierarchicalInput:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("relationship-hierarchical-input")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_select_a_site_using_the_explore_tab_of_relationship_input(
        self, admin_page: Page, branch: str
    ) -> None:
        # navigate to InfraDevice creation page
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("button", name="Start from scratch").click()

        # open site selection and verify All tab
        admin_page.get_by_label("Site").click()
        expect(admin_page.get_by_role("tab", name="All")).to_be_visible()
        expect(admin_page.get_by_role("option", name="atl1")).to_be_visible()

        # navigate through hierarchy in Explore tab
        admin_page.get_by_role("tab", name="Explore").click()
        admin_page.get_by_role("option", name="North America Continent").click()
        admin_page.get_by_role("option", name="United States of America").click()
        admin_page.get_by_role("option", name="atl1 Site").click()

        # verify selected site
        expect(admin_page.get_by_label("Site")).to_contain_text("atl1")
