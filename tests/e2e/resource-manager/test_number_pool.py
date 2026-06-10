"""Port of frontend/app/tests/e2e/resource-manager/number-pool.spec.ts.

Serial: create a number pool for a generic schema and for a node schema, verify
its details, confirm the update form omits the node/attribute selects, open the
number-pool attribute-kind page, then create an InterfaceL3 that allocates from
the pool and verify the pool assignment.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the number pools it creates on that branch. Every test depends on the SAME
fixtures (admin_page + number_pool_branch) and the chain relies on pytest's
default definition-order collection (see the README's serial-specs gotcha).
Depends on data_sites (the atl1-core1 device); the InterfaceL3 schema and the
InfraService number pool come from the schema, not the data.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestNumberPool:
    @pytest.fixture(scope="class")
    def number_pool_branch(
        self, infrahub_client: InfrahubClientSync, data_sites: SitesHandle
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("number-pool")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_create_number_pool_for_generic_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Number Pool Core").click()
        expect(admin_page.get_by_text("Name *")).to_be_visible()
        admin_page.get_by_label("Name *").fill("number pool test for generic")
        admin_page.get_by_label("Node *").click()
        expect(admin_page.get_by_role("option", name="Interface Infra", exact=True)).to_be_visible()
        expect(admin_page.get_by_role("option", name="Artifact Check Core", exact=True)).to_be_visible()
        admin_page.get_by_role("option", name="Interface Infra", exact=True).click()
        admin_page.get_by_text("Number Attribute *").click()
        admin_page.get_by_role("option", name="Speed").click()
        admin_page.get_by_label("Start range *").fill("1")
        admin_page.get_by_label("End range *").fill("10")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    def test_create_number_pool_for_node_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Number Pool Core").click()
        admin_page.get_by_label("Name *").fill("number pool test for node")
        admin_page.get_by_label("Node *").click()
        admin_page.get_by_role("option", name="Interface L3 Infra", exact=True).click()
        admin_page.get_by_text("Number Attribute *").click()
        admin_page.get_by_role("option", name="Speed").click()
        admin_page.get_by_label("Start range *").fill("11")
        admin_page.get_by_label("End range *").fill("20")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    def test_displays_correct_details_for_created_number_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        admin_page.get_by_test_id("object-items").get_by_role("link", name="number pool test for generic").click()
        admin_page.get_by_role("cell", name="number pool test for generic").first.click()
        expect(admin_page.get_by_role("cell", name="speed")).to_be_visible()
        expect(admin_page.get_by_role("cell", name="1", exact=True)).to_be_visible()
        expect(admin_page.get_by_role("cell", name="10", exact=True)).to_be_visible()

    def test_update_form_should_not_include_node_and_attribute_selects(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        admin_page.get_by_test_id("object-items").get_by_role("link", name="number pool test for generic").click()
        expect(admin_page.get_by_role("cell", name="number pool test for generic").first).to_be_visible()
        expect(admin_page.get_by_text("Node *")).not_to_be_visible()
        expect(admin_page.get_by_text("Attribute *")).not_to_be_visible()

    def test_number_pool_attribute_kind_resource_manager(self, admin_page: Page, number_pool_branch: str) -> None:
        admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        expect(admin_page.get_by_role("link", name="InfraService.")).to_be_visible()
        admin_page.get_by_role("link", name="InfraService.").click()
        admin_page.get_by_role("link", name="View", exact=True).click()
        save_screenshot_for_docs(admin_page, "numberpool_attribute_kind_resource_manager")

    def test_create_node_using_number_pool_and_verify_pool_assignment(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        # Navigate to interface creation page
        admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        admin_page.get_by_test_id("create-object-button").click()

        # Fill in interface details
        admin_page.get_by_role("combobox", name="Device *").click()
        admin_page.get_by_role("option", name="atl1-core1").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test interface with pool")

        # Select number pool
        admin_page.get_by_test_id("number-pool-button").click()
        expect(admin_page.get_by_role("option", name="number pool test for generic")).to_be_visible()
        expect(admin_page.get_by_role("option", name="number pool test for node")).to_be_visible()
        admin_page.get_by_role("option", name="number pool test for generic").click()
        expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()

        # Save interface
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("InterfaceL3 created")).to_be_visible()

        # Verify pool assignment
        admin_page.get_by_role("searchbox", name="Search").fill("interface with pool")
        admin_page.get_by_role("link", name="test interface with pool").click()
        admin_page.get_by_text("Speed1").get_by_test_id("view-metadata-button").click()
        expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="number pool test for generic")
        ).to_be_visible()
