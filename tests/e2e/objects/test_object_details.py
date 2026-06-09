"""Port of frontend/app/tests/e2e/objects/object-details.spec.ts.

/objects/:objectKind/:objectId detail view: unauthenticated cannot edit, admin
can edit, relationship rendering, the two-step select, and the node metadata
popover. All work happens on a throwaway branch cut from main, which carries the
demo dataset (InfraBGPSession 203.111.0.2/29, InfraDevice atl1-edge1), hence the
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


class TestObjectDetails:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-details")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    # --- when not logged in --------------------------------------------------
    def test_should_not_be_able_to_edit_object(self, page: Page, branch: str) -> None:
        page.goto(f"/objects/InfraBGPSession?branch={branch}")
        page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        expect(page.get_by_test_id("edit-button")).to_be_disabled()

        page.get_by_test_id("object-details-menu").click()
        expect(page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        page.keyboard.press("Escape")

    # --- when logged in as Admin --------------------------------------------
    def test_should_be_able_to_edit_object(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraBGPSession?branch={branch}")

        admin_page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        expect(admin_page.get_by_test_id("edit-button")).to_be_enabled()

        admin_page.get_by_test_id("object-details-menu").click()
        expect(admin_page.get_by_role("menuitem", name="Groups")).not_to_have_attribute("aria-disabled", "true")
        admin_page.keyboard.press("Escape")

    def test_should_display_relationships_correctly(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraBGPSession?branch={branch}")

        admin_page.get_by_role("link", name="203.111.0.2/29, atl1-edge1").click()

        # Attribute
        expect(admin_page.get_by_text("Type", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Description", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Import Policies", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Export Policies", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Status", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Role", exact=True)).to_be_visible()

        # Relationships Attributes
        expect(admin_page.get_by_text("Local As", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Remote As", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Local Ip", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Remote Ip", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Peer Group", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Peer Session", exact=True)).to_be_visible()

        # Relationships Generics
        expect(admin_page.get_by_test_id("object-details").get_by_text("Device")).to_be_visible()

    def test_should_display_the_select_2_steps_correctly(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        admin_page.get_by_role("link", name="atl1-edge1").click()
        admin_page.get_by_text("Interfaces15").click()
        admin_page.get_by_role("link", name="Ethernet4").first.click()
        admin_page.get_by_test_id("edit-button").click()

        kind_selector = admin_page.get_by_label("Kind").get_by_test_id("select-value")
        expect(kind_selector).to_contain_text("Circuit Endpoint")

        node_selector = admin_page.get_by_label("Circuit Endpoint").get_by_test_id("select-value")
        expect(node_selector).not_to_be_empty()  # ID is in the input but it's dynamic

    def test_should_display_node_metadata_popover(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        admin_page.get_by_role("link", name="atl1-edge1").click()

        admin_page.get_by_role("button", name="View node metadata").click()

        expect(admin_page.get_by_text("Created at")).to_be_visible()
        expect(admin_page.get_by_text("Created by")).to_be_visible()
        expect(admin_page.get_by_text("Updated at")).to_be_visible()
        expect(admin_page.get_by_text("Updated by")).to_be_visible()
