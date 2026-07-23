"""E2E coverage for personal user preferences.

Each user sets their own date format and timezone from the Preferences card on
the account Profile tab. A saved value persists across a reload; re-selecting the
currently-applied value clears the override so the field inherits again.

Runs as admin only (the bootstrap account), so no demo data is required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import select_combobox_option
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

# A preset that differs from every layer's default, so a persisted value is
# unambiguous. The option's accessible name is its date-fns pattern (the label
# the Combobox shows).
EU_DATE_FORMAT = "dd/MM/yyyy HH:mm"
TIMEZONE = "Asia/Tokyo"


class TestUserPreferences:
    @pytest.fixture(autouse=True)
    async def reset_admin_preferences(self, infrahub_client: InfrahubClient) -> AsyncGenerator[None, None]:
        """Clear the admin account's own preference row after each test.

        Preferences persist per account on the shared session instance, so an
        override left behind would leak into later tests. An explicit ``null``
        resets each field (an omitted field would be left unchanged).
        """
        yield
        await infrahub_client.execute_graphql(
            query=("mutation { InfrahubSetPreferences(scope: USER, date_format: null, timezone: null) { ok } }"),
        )

    async def test_set_personal_preferences_persist_across_reload(self, admin_page: Page) -> None:
        await admin_page.goto("/profile")
        await expect(admin_page.get_by_text("Preferences", exact=True)).to_be_visible()

        await select_combobox_option(admin_page, "Date format", EU_DATE_FORMAT)
        await select_combobox_option(admin_page, "Timezone", TIMEZONE)
        await admin_page.get_by_role("button", name="Save", exact=True).click()
        await expect(admin_page.get_by_text("Preferences updated")).to_be_visible()

        # The saved override survives a full reload (it is read back from the server).
        await admin_page.reload()
        await expect(admin_page.get_by_role("button", name="Date format", exact=True)).to_contain_text(EU_DATE_FORMAT)
        await expect(admin_page.get_by_role("button", name="Timezone", exact=True)).to_contain_text(TIMEZONE)

    async def test_reselecting_the_current_value_clears_the_override(self, admin_page: Page) -> None:
        await admin_page.goto("/profile")

        # Set an override first.
        await select_combobox_option(admin_page, "Date format", EU_DATE_FORMAT)
        await admin_page.get_by_role("button", name="Save", exact=True).click()
        await expect(admin_page.get_by_text("Preferences updated")).to_be_visible()

        # Re-selecting the currently-applied value clears the override; the field
        # falls back to the inherited value and shows its placeholder again.
        await select_combobox_option(admin_page, "Date format", EU_DATE_FORMAT)
        await admin_page.get_by_role("button", name="Save", exact=True).click()
        await expect(admin_page.get_by_text("Preferences updated")).to_be_visible()

        await admin_page.reload()
        await expect(admin_page.get_by_role("button", name="Date format", exact=True)).to_contain_text(
            "Automatic (inherited)"
        )
