"""Port of frontend/app/tests/e2e/theme.spec.ts.

Covers the dark-theme rollout behavior: a fresh visitor follows the desktop
color scheme when the deployment enables the flag, an explicit choice applies
instantly and survives a reload without flashing (the pre-paint script), and a
deployment with the flag off renders light regardless of desktop preference
while retaining any stored choice.

Every test is a fresh anonymous visitor (the plain ``page`` fixture, no storage
state): the coldest cache the pre-paint script can meet and the least
privileged surface the switch must still be reachable on. The tests need a
built frontend, which is what the docker stack serves — a Vite dev server
overrides the default to dark so that whoever is working on the theme has it on
screen, and pointing INFRAHUB_ADDRESS at one would fail the two
desktop-following tests for that reason alone.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page, Route


async def _set_dark_theme_flag(page: Page, enabled: bool) -> None:
    async def handler(route: Route) -> None:
        response = await route.fetch()
        body = await response.json()
        experimental = {**body.get("experimental_features", {}), "dark_theme": enabled}
        await route.fulfill(json={**body, "experimental_features": experimental})

    await page.route("*/**/api/config", handler)


async def _html_theme(page: Page) -> str:
    """Sample the document theme once — no retry, for the earliest-observable checks."""
    return await page.evaluate('() => (document.documentElement.classList.contains("dark") ? "dark" : "light")')


# The dark class lands in a layout effect, so it is applied in the same commit the markup arrives
# in, but a visibility wait can still return between the two. Assert through the auto-retrying
# locator matchers everywhere except the earliest-observable checks, which must sample once
# (via _html_theme) to mean anything.
def _html(page: Page) -> Locator:
    return page.locator("html")


async def _open_account_menu(page: Page) -> None:
    await page.get_by_test_id("unauthenticated-menu-trigger").click()


class TestTheme:
    async def test_fresh_visitor_on_dark_desktop_lands_dark_when_deployment_enables_it(self, page: Page) -> None:
        await _set_dark_theme_flag(page, enabled=True)
        await page.emulate_media(color_scheme="dark")

        await page.goto("/")
        await expect(page.get_by_test_id("sidebar")).to_be_visible()

        await expect(_html(page)).to_contain_class("dark")

        await _open_account_menu(page)
        # Offers the way back out, untagged — only the step *into* the pre-release theme is tagged.
        switch_item = page.get_by_role("menuitem", name="Light theme")
        await expect(switch_item).to_be_visible()
        await expect(switch_item).not_to_contain_text("alpha")

    async def test_fresh_visitor_on_light_desktop_stays_light_and_is_offered_the_way_in(self, page: Page) -> None:
        await _set_dark_theme_flag(page, enabled=True)
        await page.emulate_media(color_scheme="light")

        await page.goto("/")
        await expect(page.get_by_test_id("sidebar")).to_be_visible()

        await expect(_html(page)).not_to_contain_class("dark")

        await _open_account_menu(page)
        await expect(page.get_by_role("menuitem", name="Dark theme")).to_contain_text("alpha")

    async def test_switching_to_light_applies_instantly_and_survives_a_reload_without_flashing(
        self, page: Page
    ) -> None:
        await _set_dark_theme_flag(page, enabled=True)
        await page.emulate_media(color_scheme="dark")

        await page.goto("/")
        await expect(page.get_by_test_id("sidebar")).to_be_visible()

        await _open_account_menu(page)
        await page.get_by_role("menuitem", name="Light theme").click()
        await expect(_html(page)).not_to_contain_class("dark")

        # The pre-paint script must deliver the choice before the app boots, so the document is
        # already light at the earliest observable moment of the next load — on a desktop still
        # asking for dark, which is what makes this a test of the choice rather than of the
        # default. Sampled once on purpose: retrying here would also accept the class arriving
        # later from React, which is the very regression this asserts against.
        await page.goto("/", wait_until="domcontentloaded")
        assert await _html_theme(page) == "light"

        await expect(page.get_by_test_id("sidebar")).to_be_visible()
        await expect(_html(page)).not_to_contain_class("dark")

        await _open_account_menu(page)
        await expect(page.get_by_role("menuitem", name="Dark theme")).to_contain_text("alpha")

    async def test_deployment_with_the_theme_off_renders_light_and_offers_no_switch(self, page: Page) -> None:
        await _set_dark_theme_flag(page, enabled=False)
        # On a desktop asking for dark: the operating system expresses a preference, not a
        # permission, and must not reach past an operator who turned the theme off.
        await page.emulate_media(color_scheme="dark")

        # GIVEN a user who chose dark while the feature was on, after one visit has re-mirrored
        # the resolved theme (the first load after the flag flips may still paint one stale dark
        # frame; the mirror is what heals it)
        await page.goto("/")
        await page.evaluate(
            """() => {
                localStorage.setItem("infrahub.theme.choice", "dark");
                localStorage.setItem("infrahub.theme.resolved", "light");
            }"""
        )

        await page.goto("/", wait_until="domcontentloaded")
        assert await _html_theme(page) == "light"

        await expect(page.get_by_test_id("sidebar")).to_be_visible()
        await expect(_html(page)).not_to_contain_class("dark")

        await _open_account_menu(page)
        await expect(page.get_by_role("menuitem", name="About Infrahub")).to_be_visible()
        await expect(page.get_by_role("menuitem", name=re.compile(r"theme", re.IGNORECASE))).to_have_count(0)

        # AND the stored choice is retained, never deleted: re-enabling the flag must restore it.
        assert await page.evaluate('() => localStorage.getItem("infrahub.theme.choice")') == "dark"
