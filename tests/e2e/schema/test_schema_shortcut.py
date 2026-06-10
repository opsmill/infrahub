"""Port of frontend/app/tests/e2e/schema/schema-shortcut.spec.ts.

Schema shortcut modal opened from an object's attribute / relationship-one /
relationship-many labels. Uses the demo device atl1-edge1 (its detail page),
so it needs data_sites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestSchemaShortcut:
    async def test_open_schema_modal_from_attribute_label(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/objects/InfraDevice")
        await page.get_by_role("link", name="atl1-edge1").click()

        # open schema modal from attribute
        await page.get_by_test_id("object-details").get_by_role("button", name="Name").click()
        await expect(page.get_by_role("dialog")).to_be_visible()
        await expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        await expect(page.get_by_role("heading", name="Device", exact=True)).to_be_visible()
        await expect(page.get_by_role("tab", name="Attributes")).to_have_attribute("aria-selected", "true")
        await expect(page.get_by_text("Namename")).to_be_visible()

        # close modal with the close button
        await page.get_by_role("button", name="Close schema viewer").click()
        await expect(page.get_by_role("dialog")).not_to_be_visible()

    async def test_open_schema_modal_from_relationship_one_label(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/objects/InfraDevice")
        await page.get_by_role("link", name="atl1-edge1").click()

        await page.get_by_test_id("object-details").get_by_role("button", name="Site").click()
        await expect(page.get_by_role("dialog")).to_be_visible()
        await expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        await expect(page.get_by_role("tab", name="Relationships")).to_have_attribute("aria-selected", "true")
        await expect(page.get_by_text("Namesite")).to_be_visible()

        await page.keyboard.press("Escape")
        await expect(page.get_by_role("dialog")).not_to_be_visible()

    async def test_open_schema_modal_from_relationship_many_label(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/objects/InfraDevice")
        await page.get_by_role("link", name="atl1-edge1").click()

        await page.get_by_test_id("object-details").get_by_role("button", name="Tags").click()
        await expect(page.get_by_role("dialog")).to_be_visible()
        await expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        await expect(page.get_by_role("tab", name="Relationships")).to_have_attribute("aria-selected", "true")
        await expect(page.get_by_text("Nametags")).to_be_visible()

        await page.keyboard.press("Escape")
        await expect(page.get_by_role("dialog")).not_to_be_visible()
