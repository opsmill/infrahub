"""Port of frontend/app/tests/e2e/search.spec.ts.

Search-anywhere modal: open/close (click, Esc, Ctrl/Cmd+K), the Device menu
link, the no-results message, node + IPAM results, lookup by UUID, and loading
more results on scroll, including after a failed request. Runs anonymously; the
result tests rely on data_sites (the atl1 site, the 10.x prefix/loopback tree,
and AS174 transitively via org_registry) and the menu, except the scroll tests,
which create their own tags on a throwaway branch.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page, Route

SEARCH_FIRST_BATCH = 20
MATCHING_TAGS = SEARCH_FIRST_BATCH + 5
# An IP address, so the dialog also lists the Parent Prefixes group for this search.
TAG_SEARCH = "198.51.100.7"


class TestSearchAnywhere:
    async def test_open_search_anywhere_modal(self, page: Page) -> None:
        await page.goto("/")

        # open with click
        await page.get_by_test_id("search-anywhere-trigger").click()
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        # close with Esc
        await page.locator("body").press("Escape")
        await expect(page.get_by_test_id("search-anywhere")).not_to_be_visible()

        # open with the keyboard shortcut
        await page.keyboard.press("ControlOrMeta+k")
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

    async def test_displays_link_to_device_list(self, page: Page, infrastructure_menu: None) -> None:
        await page.goto("/")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        await page.get_by_test_id("search-anywhere-input").fill("devi")
        await expect(page.get_by_test_id("search-anywhere")).to_contain_text("Go to")
        await page.get_by_role("option", name="Menu Device").click()
        await expect(page.get_by_role("heading", name="Device")).to_be_visible()
        assert "/objects/InfraDevice" in page.url

    async def test_message_when_no_results_found(self, page: Page) -> None:
        await page.goto("/")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        await page.get_by_test_id("search-anywhere-input").fill("no_results_query_for_test")
        await expect(
            page.get_by_test_id("search-anywhere").get_by_role(
                "option", name="Search in docs: no_results_query_for_test"
            )
        ).to_be_visible()

    async def test_display_results_on_search_nodes(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        # a matching node result
        await page.get_by_test_id("search-anywhere-input").fill("atl1")
        await expect(
            page.get_by_test_id("search-anywhere").get_by_role("option", name="atl1 Location Site")
        ).to_be_visible()

        # a matching IPAM result
        await page.get_by_test_id("search-anywhere-input").fill("10.0")
        await expect(page.get_by_role("option", name="10.0.0.0/8 Ipam IP Prefix IP")).to_be_visible()
        await expect(page.get_by_role("option", name="10.0.0.0/16 Ipam IP Prefix IP")).to_be_visible()
        await expect(page.get_by_text("IP Namespacedefault").first).to_be_visible()
        await expect(page.get_by_text("IP NamespacedefaultAddress10.0.0.2/32Description-")).to_be_visible()

    async def test_display_result_when_searching_by_uuid(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/objects/InfraAutonomousSystem")

        await page.get_by_role("link", name="AS174 174").click()
        uuid = await page.locator("dd").first.text_content()
        assert uuid

        await page.get_by_test_id("search-anywhere-trigger").click()
        await expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        await page.get_by_test_id("search-anywhere-input").fill(uuid)
        await expect(page.get_by_role("option", name="AS174 174 Infra Autonomous System")).to_be_visible()

    @pytest.fixture
    async def branch_with_matching_tags(
        self, infrahub_client: InfrahubClient, branch_api: BranchAPI
    ) -> AsyncGenerator[tuple[str, str], None]:
        """A throwaway branch holding more tags than the first batch, all named after one IP address."""
        branch = generate_random_branch_name("search-load-more-")
        search = TAG_SEARCH
        await branch_api.create(branch)
        try:
            batch = await infrahub_client.create_batch()
            for index in range(MATCHING_TAGS):
                tag = await infrahub_client.create(kind="BuiltinTag", name=f"{search}-{index:02d}", branch=branch)
                batch.add(task=tag.save, node=tag)
            async for _ in batch.execute():
                pass
            yield branch, search
        finally:
            with contextlib.suppress(Exception):
                await branch_api.delete(branch)

    async def test_scrolling_to_the_end_lists_every_matching_object(
        self, page: Page, branch_with_matching_tags: tuple[str, str]
    ) -> None:
        branch, search = branch_with_matching_tags
        # GIVEN
        # A window this height keeps the first batch taller than the list, so it does not load more on its own.
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.goto(f"/?branch={branch}")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await page.get_by_test_id("search-anywhere-input").fill(search)
        dialog = page.get_by_test_id("search-anywhere")
        objects = dialog.get_by_role("group", name=re.compile(r"^Objects "))
        results = objects.get_by_role("option", name=search)
        await expect(results).to_have_count(SEARCH_FIRST_BATCH)
        await expect(objects).to_have_accessible_name(f"Objects {SEARCH_FIRST_BATCH}+")

        # WHEN
        await results.last.scroll_into_view_if_needed()

        # THEN
        await expect(results).to_have_count(MATCHING_TAGS)
        await expect(objects).to_have_accessible_name(f"Objects {MATCHING_TAGS}")
        await expect(dialog).to_contain_text(f"End of results · {MATCHING_TAGS} objects")

    async def test_a_failed_load_more_keeps_the_loaded_results(
        self, page: Page, branch_with_matching_tags: tuple[str, str]
    ) -> None:
        branch, search = branch_with_matching_tags

        async def fail_load_more(route: Route) -> None:
            request = route.request.post_data_json or {}
            if request.get("operationName") == "Search" and request["variables"]["limit"] > SEARCH_FIRST_BATCH + 1:
                await route.abort()
            else:
                await route.fallback()

        # GIVEN
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.route("**/graphql/**", fail_load_more)
        await page.goto(f"/?branch={branch}")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await page.get_by_test_id("search-anywhere-input").fill(search)
        dialog = page.get_by_test_id("search-anywhere")
        objects = dialog.get_by_role("group", name=re.compile(r"^Objects "))
        results = objects.get_by_role("option", name=search)
        parent_prefixes = dialog.get_by_text("No containing prefixes found")
        await expect(results).to_have_count(SEARCH_FIRST_BATCH)
        await expect(parent_prefixes).to_be_visible()

        # WHEN
        await results.last.scroll_into_view_if_needed()

        # THEN
        await expect(dialog).to_contain_text("Could not load more results")
        await expect(results).to_have_count(SEARCH_FIRST_BATCH)
        await expect(parent_prefixes).to_be_visible()

    async def test_a_search_of_only_spaces_lists_no_objects(
        self, page: Page, branch_with_matching_tags: tuple[str, str]
    ) -> None:
        branch, search = branch_with_matching_tags
        # GIVEN
        await page.goto(f"/?branch={branch}")
        await page.get_by_test_id("search-anywhere-trigger").click()
        await page.get_by_test_id("search-anywhere-input").fill(search)
        objects = page.get_by_test_id("search-anywhere").get_by_role("group", name=re.compile(r"^Objects"))
        await expect(objects).to_be_visible()

        # WHEN
        await page.get_by_test_id("search-anywhere-input").fill("   ")

        # THEN
        await expect(objects).to_have_count(0)
