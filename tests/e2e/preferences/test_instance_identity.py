"""E2E coverage for the instance label and color global settings.

An administrator names and colors the instance on the Global preferences page.
Every visitor, including a user without any permission and an anonymous visitor
on the login page, then views the label badge in the header, the color bar at the
top of the page and the label in the browser tab title.

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

INSTANCE_LABEL = "QA"
INSTANCE_LABEL_MAX_LENGTH = 32
BRANCHES_PAGE_TITLE = "Branches list"
APPLICATION_TITLE = "Infrahub"


async def _set_instance_identity(client: InfrahubClient, *, label: str | None, color: str | None) -> None:
    label_argument = "null" if label is None else f'"{label}"'
    color_argument = "null" if color is None else color
    await client.execute_graphql(
        query=(
            "mutation { InfrahubSetPreferences(scope: GLOBAL, "
            f"instance_label: {label_argument}, instance_color: {color_argument}) {{ ok }} }}"
        ),
    )


async def _stored_instance_identity(page: Page) -> dict[str, str | None]:
    response = await page.request.get("/api/config")
    return (await response.json())["instance"]


class TestInstanceIdentity:
    @pytest.fixture(autouse=True)
    async def reset_instance_identity(self, infrahub_client: InfrahubClient) -> AsyncGenerator[None, None]:
        """Clear the instance label and color after the test.

        The global row is shared by every account on the session instance, so it
        must be reset or later tests view a stale badge and bar.
        """
        yield
        await _set_instance_identity(infrahub_client, label=None, color=None)

    async def test_admin_sets_the_label_and_color_and_every_user_views_them(
        self, admin_page: Page, read_only_page: Page
    ) -> None:
        # An administrator names and colors the instance.
        await admin_page.goto("/global-preferences")
        await admin_page.get_by_label("Instance label").fill(INSTANCE_LABEL)
        await select_combobox_option(admin_page, "Instance color", "Red")
        await admin_page.get_by_role("button", name="Save instance identity").click()
        await expect(admin_page.get_by_text("Instance identity updated")).to_be_visible()

        # A user without any permission views the badge, the bar and the tab title.
        await read_only_page.goto("/branches")
        await expect(read_only_page.get_by_test_id("instance-badge")).to_contain_text(INSTANCE_LABEL)
        await expect(read_only_page.get_by_test_id("instance-color-bar")).to_be_visible()
        await expect(read_only_page).to_have_title(f"{INSTANCE_LABEL} · {BRANCHES_PAGE_TITLE}")

        # The identity comes from the server, so it survives a reload.
        await read_only_page.reload()
        await expect(read_only_page.get_by_test_id("instance-badge")).to_contain_text(INSTANCE_LABEL)
        await expect(read_only_page.get_by_test_id("instance-color-bar")).to_be_visible()
        await expect(read_only_page).to_have_title(f"{INSTANCE_LABEL} · {BRANCHES_PAGE_TITLE}")

    async def test_label_over_the_limit_is_refused_and_nothing_is_stored(self, admin_page: Page) -> None:
        await admin_page.goto("/global-preferences")
        await admin_page.get_by_label("Instance label").fill("x" * (INSTANCE_LABEL_MAX_LENGTH + 1))

        await expect(
            admin_page.get_by_text(f"cannot be longer than {INSTANCE_LABEL_MAX_LENGTH} characters")
        ).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Save instance identity")).to_be_disabled()

        stored = await _stored_instance_identity(admin_page)
        assert stored["label"] is None

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
