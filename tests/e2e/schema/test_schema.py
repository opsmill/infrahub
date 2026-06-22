"""Port of frontend/app/tests/e2e/schema/schema.spec.ts.

Schema visualizer: redirect from an object's Schema link, the help menu
(documentation / list-view link states), schema list filtering, the graph view,
and a NumberPool attribute. Runs anonymously; needs the base schema loaded.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestSchemaVisualizer:
    async def test_redirect_to_schema_page_via_object_help_menu(self, page: Page, schema_base: None) -> None:
        await page.goto("/objects/InfraInterface")
        await page.get_by_role("link", name="Schema").click()
        await expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        await expect(page.get_by_text("KindInfraInterface")).to_be_visible()
        await expect(page).to_have_url(re.compile(r"\/schema\?kind=InfraInterface"))

    async def test_display_help_menu_correctly(self, page: Page, schema_base: None) -> None:
        await page.goto("/schema")

        # open schema viewer
        await page.get_by_text("CoreGraphQL Query", exact=True).click()
        await expect(page.get_by_test_id("schema-viewer")).to_be_visible()

        # open help menu
        await page.get_by_test_id("schema-help-menu-trigger").click()
        await expect(page.get_by_test_id("schema-help-menu-content")).to_be_visible()

        # help menu with documentation and list view link
        await expect(page.get_by_role("menuitem", name="Documentation")).to_be_enabled()
        await expect(page.get_by_role("menuitem", name="Open list view")).to_be_enabled()

        # close menu when pressing Esc
        await page.locator("body").press("Escape")
        await expect(page.get_by_test_id("schema-help-menu-content")).not_to_be_visible()

        # help menu for a schema without documentation and no list view link
        await page.get_by_text("CoreThread - Artifact").click()
        await page.get_by_test_id("schema-help-menu-trigger").click()
        await expect(page.get_by_role("menuitem", name="Documentation")).to_be_disabled()
        await expect(page.get_by_role("menuitem", name="Open list view")).to_be_disabled()
        await page.locator("body").press("Escape")

        # help menu for a schema without documentation, but with list view link
        await page.get_by_text("BuiltinTag", exact=True).click()
        await page.get_by_test_id("schema-help-menu-trigger").click()
        await expect(page.get_by_role("menuitem", name="Documentation")).to_be_disabled()
        await expect(page.get_by_role("menuitem", name="Open list view")).to_be_enabled()

    async def test_filter_schema_list(self, page: Page, schema_base: None) -> None:
        await page.goto("/schema")
        await expect(page.get_by_role("heading", name="Core Account Node")).to_be_visible()

        await page.get_by_placeholder("Search schema").fill("tag")
        await expect(page.get_by_role("heading", name="Builtin Tag Node")).to_be_visible()
        await expect(page.get_by_role("heading", name="Core Account Node")).not_to_be_visible()

    async def test_navigate_to_schema_graph_view(self, page: Page, schema_base: None) -> None:
        await page.goto("/schema")
        await expect(page.get_by_role("heading", name="Core Account Node")).to_be_visible()
        await page.get_by_role("heading", name="Core Account Node").click()
        await page.get_by_role("link", name="View in graph").click()
        await expect(page).to_have_url(re.compile(r"\/schema\/graph\?highlight=CoreAccount"))
        await expect(page.get_by_text("Schema Overview")).to_be_visible()

    async def test_view_schema_attribute_kind_numberpool(self, page: Page, schema_base: None) -> None:
        await page.goto("/schema")
        await page.get_by_placeholder("Search schema").fill("InfraBackBoneService")
        await page.get_by_text("InfraBackbone Service").click()
        await page.get_by_role("tab", name="Attributes").click()
        await page.get_by_text("Service Identifier NumberPool").click()
        await page.get_by_text("Parameters").click()
        await save_screenshot_for_docs(page, "schema_numberpool")
