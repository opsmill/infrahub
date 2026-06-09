"""Port of frontend/app/tests/e2e/schema/schema-shortcut.spec.ts.

Schema shortcut modal opened from an object's attribute / relationship-one /
relationship-many labels. Uses the demo device atl1-edge1, so it needs the
demo data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestSchemaShortcut:
    def test_open_schema_modal_from_attribute_label(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/objects/InfraDevice")
        page.get_by_role("link", name="atl1-edge1").click()

        # open schema modal from attribute
        page.get_by_test_id("object-details").get_by_role("button", name="Name").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        expect(page.get_by_role("heading", name="Device", exact=True)).to_be_visible()
        expect(page.get_by_role("tab", name="Attributes")).to_have_attribute("aria-selected", "true")
        expect(page.get_by_text("Namename")).to_be_visible()

        # close modal with the close button
        page.get_by_role("button", name="Close schema viewer").click()
        expect(page.get_by_role("dialog")).not_to_be_visible()

    def test_open_schema_modal_from_relationship_one_label(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/objects/InfraDevice")
        page.get_by_role("link", name="atl1-edge1").click()

        page.get_by_test_id("object-details").get_by_role("button", name="Site").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        expect(page.get_by_role("tab", name="Relationships")).to_have_attribute("aria-selected", "true")
        expect(page.get_by_text("Namesite")).to_be_visible()

        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).not_to_be_visible()

    def test_open_schema_modal_from_relationship_many_label(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/objects/InfraDevice")
        page.get_by_role("link", name="atl1-edge1").click()

        page.get_by_test_id("object-details").get_by_role("button", name="Tags").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        expect(page.get_by_role("tab", name="Relationships")).to_have_attribute("aria-selected", "true")
        expect(page.get_by_text("Nametags")).to_be_visible()

        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).not_to_be_visible()
