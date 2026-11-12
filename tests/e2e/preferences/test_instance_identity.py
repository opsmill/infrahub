"""E2E coverage for the instance label and color that an administrator sets and every visitor views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import select_combobox_option
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

INSTANCE_LABEL = "QA"
BRANCHES_PAGE_TITLE = "Branches list"
APPLICATION_TITLE = "Infrahub"


SET_INSTANCE_IDENTITY = """
mutation ($label: String, $color: InstanceColor) {
  InfrahubSetPreferences(scope: GLOBAL, instance_label: $label, instance_color: $color) {
    ok
  }
}
"""


async def _set_instance_identity(client: InfrahubClient, *, label: str | None, color: str | None) -> None:
    await client.execute_graphql(query=SET_INSTANCE_IDENTITY, variables={"label": label, "color": color})


async def _expect_identity_on_branches_page(page: Page) -> None:
    await expect(page.get_by_test_id("instance-badge")).to_contain_text(INSTANCE_LABEL)
    await expect(page.get_by_test_id("instance-color-bar")).to_be_visible()
    await expect(page).to_have_title(f"{INSTANCE_LABEL} · {BRANCHES_PAGE_TITLE}")


class TestInstanceIdentity:
    async def test_admin_sets_the_label_and_color_and_every_user_views_them(
        self, admin_page: Page, read_only_page: Page
    ) -> None:
        await admin_page.goto("/global-preferences")
        await admin_page.get_by_label("Instance label").fill(INSTANCE_LABEL)
        await select_combobox_option(admin_page, "Instance color", "Red")
        await admin_page.get_by_role("button", name="Save instance identity").click()
        await expect(admin_page.get_by_text("Instance identity updated")).to_be_visible()

        await read_only_page.goto("/branches")
        await _expect_identity_on_branches_page(read_only_page)

        # The identity comes from the server, so it survives a reload.
        await read_only_page.reload()
        await _expect_identity_on_branches_page(read_only_page)

    async def test_anonymous_visitor_views_the_identity_on_the_login_page(
        self, infrahub_client: InfrahubClient, page: Page
    ) -> None:
        await _set_instance_identity(infrahub_client, label=INSTANCE_LABEL, color="RED")

        await page.goto("/login")
        await expect(page.get_by_test_id("instance-color-bar")).to_be_visible()
        await expect(page.get_by_test_id("instance-badge")).to_contain_text(INSTANCE_LABEL)
        await expect(page).to_have_title(f"{INSTANCE_LABEL} · {APPLICATION_TITLE}")

    async def test_clearing_the_label_keeps_the_bar(
        self, infrahub_client: InfrahubClient, read_only_page: Page
    ) -> None:
        await _set_instance_identity(infrahub_client, label=INSTANCE_LABEL, color="RED")
        await _set_instance_identity(infrahub_client, label=None, color="RED")

        await read_only_page.goto("/branches")
        await expect(read_only_page.get_by_test_id("instance-color-bar")).to_be_visible()
        await expect(read_only_page.get_by_test_id("instance-badge")).to_have_count(0)
        await expect(read_only_page).to_have_title(BRANCHES_PAGE_TITLE)

    async def test_nothing_set_shows_neither_the_badge_nor_the_bar(self, read_only_page: Page) -> None:
        await read_only_page.goto("/branches")
        await expect(read_only_page.get_by_role("link", name="main", exact=True)).to_be_visible()
        await expect(read_only_page.get_by_test_id("instance-badge")).to_have_count(0)
        await expect(read_only_page.get_by_test_id("instance-color-bar")).to_have_count(0)
        await expect(read_only_page).to_have_title(BRANCHES_PAGE_TITLE)
