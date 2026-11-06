"""E2E coverage for organisation-wide default preferences.

A user holding ``manage_global_preferences`` sets organisation defaults on the
Global preferences page. Every user without a personal override then inherits
those defaults — surfaced in the Preferences card as the "organisation default"
source.

Uses the read-only account (from the RBAC slice) as the inheriting user, so the
test declares the ``data_rbac`` dependency transitively via ``read_only_page``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import select_combobox_option
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page

# US 12-hour preset — distinct from the ISO default so an inherited value is
# unambiguous.
GLOBAL_DATE_FORMAT = "MM/dd/yyyy hh:mm a"


class TestGlobalPreferences:
    async def test_global_default_is_inherited_by_users_without_an_override(
        self, admin_page: Page, read_only_page: Page
    ) -> None:
        # An administrator sets the organisation default.
        await admin_page.goto("/global-preferences")
        await select_combobox_option(admin_page, "Date format", GLOBAL_DATE_FORMAT)
        await admin_page.get_by_role("button", name="Save", exact=True).click()
        await expect(admin_page.get_by_text("Global preferences updated")).to_be_visible()

        # A user with no personal override sees the field inherit, and the source
        # hint attributes it to the organisation default.
        await read_only_page.goto("/profile")
        await expect(read_only_page.get_by_role("button", name="Date format", exact=True)).to_contain_text(
            "Automatic (inherited)"
        )

        # Focus (not hover): React Aria opens the tooltip immediately on keyboard
        # focus, while hover goes through the warm-up delay — the deterministic
        # option for CI.
        await read_only_page.get_by_role("button", name="Where this value comes from").first.focus()
        await expect(read_only_page.get_by_text("From the organisation default")).to_be_visible()
