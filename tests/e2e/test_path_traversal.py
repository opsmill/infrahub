"""Port of frontend/app/tests/e2e/path-traversal.spec.ts.

The Path Traversal page: heading, mode toggle (Path / Dependencies), empty
state, panel collapse/expand, advanced options, URL-driven auto-run, source
validation, and UUID-paste resolution in the source picker. The TypeScript
spec is skipped while the feature page stabilizes; this port is kept skipped
for parity so it is ready to enable alongside the TS suite.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = [
    pytest.mark.shard_sites_a,
    pytest.mark.skip(reason="Path Traversal page is not stable yet (mirrors the skipped TS spec)"),
]

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page

DEVICE_LINK_NAME = re.compile(r"-edge|-leaf|-spine|-core", re.IGNORECASE)


class TestPathTraversal:
    async def test_load_page_with_heading(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await expect(admin_page.get_by_text("Path Traversal")).to_be_visible()

    async def test_mode_toggle_path_and_dependencies(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await expect(admin_page.get_by_role("button", name="Path", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Dependencies", exact=True)).to_be_visible()

    async def test_empty_state_message(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await expect(admin_page.get_by_text('Select two objects and click "Find Paths"')).to_be_visible()

    async def test_switch_to_dependencies_mode(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await admin_page.get_by_role("button", name="Dependencies", exact=True).click()
        await expect(admin_page.get_by_role("heading", name="Dependencies")).to_be_visible()
        await expect(
            admin_page.get_by_text('Select a source object, target kinds, and click "Find Dependencies"')
        ).to_be_visible()

    async def test_collapse_and_expand_left_panel(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await expect(admin_page.get_by_text("Path Traversal")).to_be_visible()

        # collapse the panel
        await admin_page.get_by_role("button", name="Collapse panel").click()
        await expect(admin_page.get_by_text("Path Traversal")).not_to_be_visible()

        # expand the panel
        await admin_page.get_by_role("button", name="Expand panel").click()
        await expect(admin_page.get_by_text("Path Traversal")).to_be_visible()

    async def test_toggle_advanced_options_section(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        advanced_toggle = admin_page.get_by_text("Advanced options")
        if await advanced_toggle.is_visible():
            await advanced_toggle.click()

    async def test_auto_runs_query_with_source_and_destination_in_url(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        # Pull two real seeded device ids from the demo dataset by listing
        # InfraDevice and reading the first two row links. The exact device
        # names depend on the dataset; we just need any two valid ids.
        await admin_page.goto("/objects/InfraDevice")

        device_links = admin_page.get_by_role("link", name=DEVICE_LINK_NAME)
        await expect(device_links.first).to_be_visible(timeout=10_000)

        source_href = await device_links.nth(0).get_attribute("href")
        dest_href = await device_links.nth(1).get_attribute("href")

        # Hrefs look like /objects/InfraDevice/<uuid>
        source_id = (source_href or "").split("/")[-1]
        destination_id = (dest_href or "").split("/")[-1]

        if not source_id or not destination_id:
            pytest.skip("Demo dataset has < 2 InfraDevice objects")

        await admin_page.goto(
            f"/path-traversal?mode=path&source={source_id}&destination={destination_id}&depth=5&maxPaths=10"
        )

        # The query should fire automatically — wait for either a "paths found"
        # header or the "No paths found" empty state.
        await expect(admin_page.get_by_text(re.compile(r"path[s]? found|No paths found", re.IGNORECASE))).to_be_visible(
            timeout=10_000
        )

    async def test_validation_message_when_submitting_without_source(self, admin_page: Page) -> None:
        await admin_page.goto("/path-traversal")
        await admin_page.get_by_role("button", name="Find Paths").click()

        await expect(admin_page.get_by_text("Source is required")).to_be_visible()
        # The query should not have fired — the right side stays in the empty state.
        await expect(admin_page.get_by_text('Select two objects and click "Find Paths"')).to_be_visible()

    async def test_uuid_paste_resolves_to_single_match(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # Get a known device id from the demo dataset.
        await admin_page.goto("/objects/InfraDevice")
        first_link = admin_page.get_by_role("link", name=DEVICE_LINK_NAME).first
        await expect(first_link).to_be_visible(timeout=10_000)
        href = await first_link.get_attribute("href")
        known_id = (href or "").split("/")[-1]

        if not known_id:
            pytest.skip("Demo dataset has no InfraDevice objects")

        await admin_page.goto("/path-traversal")

        # Open the source-side combobox (label = "Source Object"), then type the
        # UUID into the cmdk search input.
        source_combobox = admin_page.locator(":text('Source Object')").locator("..").get_by_role("combobox").first
        await source_combobox.click()

        search_input = admin_page.get_by_placeholder(re.compile(r"search by name|paste an object id", re.IGNORECASE))
        await search_input.fill(known_id)

        # The combobox should surface the resolved object as a selectable option.
        option = admin_page.get_by_role("option").first
        await expect(option).to_be_visible(timeout=5000)
        await option.click()

        # The picker shows the chip with the resolved id text.
        await expect(admin_page.get_by_text(known_id)).to_be_visible()
