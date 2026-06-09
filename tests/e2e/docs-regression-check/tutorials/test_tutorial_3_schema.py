"""Port of tutorials/tutorial-3_schema.spec.ts.

Visualize the active schema via Object Management > Schemas (the core
`Artifact Check` kind is shown).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestTutorial3Schema:
    def test_visualize_the_active_schema(self, admin_page: Page, schema_base: None) -> None:
        admin_page.goto("/")
        admin_page.get_by_role("button", name="Object Management").click()
        admin_page.get_by_role("menuitem", name="Schemas").click()
        expect(admin_page.get_by_text("Artifact Check")).to_be_visible()
        save_screenshot_for_docs(admin_page, "tutorial_3_schema")
