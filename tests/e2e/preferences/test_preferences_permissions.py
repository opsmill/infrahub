"""E2E coverage for the manage_global_preferences permission gate (IFC-2722).

The Global preferences page is gated by the ``manage_global_preferences`` global
permission. An administrator (super admin, who holds it implicitly) sees the
account-menu entry and the editor; a user without the permission never sees the
menu entry, and a direct visit to the page is refused.

Uses the read-only account (from the RBAC slice) as the unprivileged user, so the
test declares the ``data_rbac`` dependency transitively via ``read_only_page``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestPreferencesPermissions:
    async def test_admin_sees_the_global_preferences_menu_entry_and_editor(self, admin_page: Page) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("authenticated-menu-trigger").click()
        await expect(admin_page.get_by_role("menuitem", name="Global preferences")).to_be_visible()

        await admin_page.get_by_role("menuitem", name="Global preferences").click()
        await expect(admin_page).to_have_url(re.compile(r"/global-preferences$"))
        await expect(admin_page.get_by_role("button", name="Save", exact=True)).to_be_visible()

    async def test_non_admin_cannot_see_or_open_global_preferences(self, read_only_page: Page) -> None:
        await read_only_page.goto("/")
        # The account menu opens, but the gated entry is absent.
        await read_only_page.get_by_test_id("authenticated-menu-trigger").click()
        await expect(read_only_page.get_by_role("menuitem", name="Account settings")).to_be_visible()
        await expect(read_only_page.get_by_role("menuitem", name="Global preferences")).to_have_count(0)
        await read_only_page.keyboard.press("Escape")

        # A direct visit to the gated page is refused.
        await read_only_page.goto("/global-preferences")
        await expect(read_only_page.get_by_text("You don't have permission to edit global preferences")).to_be_visible()
