"""Port of frontend/app/tests/e2e/objects/object-relationships.spec.ts.

/objects/:objectKind/:objectId relationship tab (a serial flow):
read-only enforcement when unauthenticated, then as Admin dissociate / add /
edit relationships, traverse hierarchical cardinality-many children, allocate a
relationship from a pool, and confirm a relationship value links to its details
page.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
relies on prior tests' side effects (the Cisco IOS platform's device count goes
10 -> 9 -> 10). Every test depends on the SAME `branch` fixture and the chain
relies on pytest's default definition-order collection (see the README's
serial-specs gotcha). The suite runs single-process. The first and
last tests run unauthenticated (default `page`); the middle tests run as Admin
(`admin_page`).
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
    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestObjectRelationships:
    @pytest.fixture(scope="class")
    def branch(
        self,
        infrahub_client: InfrahubClientSync,
        data_sites: SitesHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-relationships")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    # --- when not logged in --------------------------------------------------
    def test_should_not_be_able_to_edit_relationship(self, page: Page, branch: str) -> None:
        # Navigate to relationship tab of an object
        page.goto(f"/objects/InfraPlatform?branch={branch}")
        page.get_by_role("link", name="Cisco IOS", exact=True).click()

        # all buttons are disabled
        expect(page.get_by_test_id("edit-button")).to_be_disabled()

        page.get_by_test_id("object-details-menu").click()
        expect(page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        expect(page.get_by_role("menuitem", name="Delete")).to_have_attribute("aria-disabled", "true")
        page.keyboard.press("Escape")

        page.get_by_role("link", name="Devices 10").click()
        expect(page.get_by_test_id("open-relationship-form-button")).to_be_disabled()

    # --- when logged in as Admin --------------------------------------------
    def test_should_delete_the_relationship(self, admin_page: Page, branch: str) -> None:
        # Navigate to relationship tab of an object
        admin_page.goto(f"/objects/InfraPlatform?branch={branch}")
        admin_page.get_by_role("link", name="Cisco IOS", exact=True).click()
        admin_page.get_by_role("link", name="Devices 10").click()

        # Delete the relationship
        admin_page.get_by_test_id("actions-cell-atl1-leaf1").click()
        admin_page.get_by_role("menuitem", name="Dissociate").click()
        expect(
            admin_page.get_by_text(
                "Are you sure you want to dissociate atl1-leaf1 ?"
                "- This action will only remove the association."
                "- The object itself will not be deleted."
            )
        ).to_be_visible()
        admin_page.get_by_test_id("modal-delete-confirm").click()

        # Verify deletion of relationship
        expect(admin_page.get_by_text("Association with atl1-leaf1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-leaf1")).to_be_hidden()
        expect(admin_page.get_by_role("link", name="Devices 9")).to_be_visible()

    def test_should_add_a_new_relationship(self, admin_page: Page, branch: str) -> None:
        # Navigate to relationship tab of an object
        admin_page.goto(f"/objects/InfraPlatform?branch={branch}")
        admin_page.get_by_role("link", name="Cisco IOS", exact=True).click()
        admin_page.get_by_role("link", name="Devices 9").click()
        expect(admin_page.get_by_role("link", name="atl1-leaf2")).to_be_visible()

        # Add a new relationship
        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_test_id("side-panel-container").get_by_label("Devices").click()
        admin_page.get_by_role("option", name="atl1-leaf1").click()
        admin_page.get_by_role("button", name="Save").click()

        # Verify new relationship addition
        expect(admin_page.get_by_text("Association with InfraDevice added")).to_be_visible()
        expect(admin_page.get_by_role("link", name="Devices 10")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-leaf1")).to_be_visible()

    def test_should_edit_a_relationship(self, admin_page: Page, branch: str) -> None:
        # Navigate to relationship tab of an object
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        admin_page.get_by_role("link", name="atl1-core1").click()
        admin_page.get_by_text("Interfaces6").click()

        # Edit a relationship
        admin_page.get_by_role("link", name="Loopback0", exact=True).click()
        expect(admin_page.get_by_text("NameLoopback0")).to_be_visible()

        admin_page.get_by_test_id("edit-button").click()
        expect(admin_page.get_by_text("Device *")).to_be_visible()
        admin_page.get_by_role("textbox", name="Name *").fill("Loopback0-update")
        admin_page.get_by_role("button", name="Save").click()

        # Verify relationship update
        expect(admin_page.get_by_text("InterfaceL3 updated")).to_be_visible()
        expect(admin_page.get_by_text("NameLoopback0-update")).to_be_visible()

    def test_should_access_relationships_of_cardinality_many_with_hierarchical_children(
        self, admin_page: Page, branch: str
    ) -> None:
        # Navigates to North America and checks the children
        admin_page.goto(f"/objects/LocationContinent?branch={branch}")
        admin_page.get_by_role("link", name="North America").first.click()
        admin_page.get_by_text("Children2").click()
        expect(admin_page.get_by_role("link", name="Canada")).to_be_visible()
        expect(admin_page.get_by_role("link", name="United States of America")).to_be_visible()

        # Navigates to the USA and checks the children
        admin_page.get_by_role("link", name="United States of America").click()
        admin_page.get_by_text("Children5").click()
        expect(admin_page.get_by_role("link", name="atl1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1")).to_be_visible()
        expect(admin_page.get_by_text("Bailey Li")).to_be_visible()
        expect(admin_page.get_by_text("Francesca Wilcox")).to_be_visible()

    def test_should_access_to_the_pool_selector_on_relationships_add(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraInterfaceL3?branch={branch}")
        admin_page.get_by_test_id("identifier-cell").get_by_role("link", name="Ethernet1", exact=True).nth(2).click()
        admin_page.get_by_text("Ip Addresses0").click()
        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_test_id("select-open-pool-option-button").click()
        admin_page.get_by_role("option", name="Loopbacks pool").click()
        expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("Loopbacks pool")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Association with IpamIPAddress added")).to_be_visible()

    def test_clicking_on_a_relationship_value_redirects_to_its_details_page(self, page: Page, branch: str) -> None:
        # Navigate to relationship tab of an object
        page.goto(f"/objects/InfraPlatform?branch={branch}")
        page.get_by_role("link", name="Cisco IOS", exact=True).click()
        page.get_by_role("link", name="Devices 10").click()

        page.get_by_role("link", name="atl1", exact=True).first.click()
        expect(page.get_by_test_id("object-details").get_by_text("Nameatl1")).to_be_visible()
        assert "/objects/LocationSite/" in page.url
