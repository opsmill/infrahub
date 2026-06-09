"""Port of frontend/app/tests/e2e/schema/schema.spec.ts.

Schema visualizer: redirect from an object's Schema link, the help menu
(documentation / list-view link states), schema list filtering, the graph view,
and a NumberPool attribute. Runs anonymously; needs the base schema loaded.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestSchemaVisualizer:
    def test_redirect_to_schema_page_via_object_help_menu(self, page: Page, schema_base: None) -> None:
        page.goto("/objects/InfraInterface")
        page.get_by_role("link", name="Schema").click()
        expect(page.get_by_test_id("schema-viewer")).to_be_visible()
        expect(page.get_by_text("KindInfraInterface")).to_be_visible()
        expect(page).to_have_url(re.compile(r"\/schema\?kind=InfraInterface"))

    def test_display_help_menu_correctly(self, page: Page, schema_base: None) -> None:
        page.goto("/schema")

        # open schema viewer
        page.get_by_text("CoreGraphQL Query", exact=True).click()
        expect(page.get_by_test_id("schema-viewer")).to_be_visible()

        # open help menu
        page.get_by_test_id("schema-help-menu-trigger").click()
        expect(page.get_by_test_id("schema-help-menu-content")).to_be_visible()

        # help menu with documentation and list view link
        expect(page.get_by_role("menuitem", name="Documentation")).to_be_enabled()
        expect(page.get_by_role("menuitem", name="Open list view")).to_be_enabled()

        # close menu when pressing Esc
        page.locator("body").press("Escape")
        expect(page.get_by_test_id("schema-help-menu-content")).not_to_be_visible()

        # help menu for a schema without documentation and no list view link
        page.get_by_text("CoreThread - Artifact").click()
        page.get_by_test_id("schema-help-menu-trigger").click()
        expect(page.get_by_role("menuitem", name="Documentation")).to_be_disabled()
        expect(page.get_by_role("menuitem", name="Open list view")).to_be_disabled()
        page.locator("body").press("Escape")

        # help menu for a schema without documentation, but with list view link
        page.get_by_text("BuiltinTag", exact=True).click()
        page.get_by_test_id("schema-help-menu-trigger").click()
        expect(page.get_by_role("menuitem", name="Documentation")).to_be_disabled()
        expect(page.get_by_role("menuitem", name="Open list view")).to_be_enabled()

    def test_filter_schema_list(self, page: Page, schema_base: None) -> None:
        page.goto("/schema")
        expect(page.get_by_role("heading", name="Core Account Node")).to_be_visible()

        page.get_by_placeholder("Search schema").fill("tag")
        expect(page.get_by_role("heading", name="Builtin Tag Node")).to_be_visible()
        expect(page.get_by_role("heading", name="Core Account Node")).not_to_be_visible()

    def test_navigate_to_schema_graph_view(self, page: Page, schema_base: None) -> None:
        page.goto("/schema")
        expect(page.get_by_role("heading", name="Core Account Node")).to_be_visible()
        page.get_by_role("heading", name="Core Account Node").click()
        page.get_by_role("link", name="View in graph").click()
        expect(page).to_have_url(re.compile(r"\/schema\/graph\?highlight=CoreAccount"))
        expect(page.get_by_text("Schema Overview")).to_be_visible()

    def test_view_schema_attribute_kind_numberpool(self, page: Page, schema_base: None) -> None:
        page.goto("/schema")
        page.get_by_placeholder("Search schema").fill("InfraBackBoneService")
        page.get_by_text("InfraBackbone Service").click()
        page.get_by_role("tab", name="Attributes").click()
        page.get_by_text("Service Identifier NumberPool").click()
        page.get_by_text("Parameters").click()
        save_screenshot_for_docs(page, "schema_numberpool")
