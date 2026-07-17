"""E2E coverage for organisation-wide default preferences (IFC-2720 / IFC-2722).

A user holding ``manage_global_preferences`` sets organisation defaults on the
Global preferences tab. Every user without a personal override then inherits
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
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

# US 12-hour preset — distinct from the ISO default so an inherited value is
# unambiguous.
GLOBAL_DATE_FORMAT = "MM/dd/yyyy hh:mm a"


class TestGlobalPreferences:
    @pytest.fixture(autouse=True)
    async def reset_global_preferences(self, infrahub_client: InfrahubClient) -> AsyncGenerator[None, None]:
        """Clear the organisation-wide defaults after the test.

        The global row is shared by every account on the session instance, so it
        must be reset or later tests inherit a stale default.
        """
        yield
        await infrahub_client.execute_graphql(
            query=("mutation { InfrahubSetPreferences(scope: GLOBAL, date_format: null, timezone: null) { ok } }"),
        )

    async def test_global_default_is_inherited_by_users_without_an_override(
        self, admin_page: Page, read_only_page: Page
    ) -> None:
        # An administrator sets the organisation default.
        await admin_page.goto("/profile/global-preferences")
        await select_combobox_option(admin_page, "Date format", GLOBAL_DATE_FORMAT)
        await admin_page.get_by_role("button", name="Save", exact=True).click()
        await expect(admin_page.get_by_text("Global preferences updated")).to_be_visible()

        # A user with no personal override sees the field inherit, and the source
        # hint attributes it to the organisation default.
        await read_only_page.goto("/profile")
        await expect(read_only_page.get_by_role("button", name="Date format", exact=True)).to_contain_text(
            "Automatic (inherited)"
        )

        await read_only_page.get_by_role("button", name="Where this value comes from").first.hover()
        await expect(read_only_page.get_by_text("From the organisation default")).to_be_visible()
