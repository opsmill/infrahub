"""Port of frontend/app/tests/e2e/groups/groups-filter.spec.ts.

CoreGroup list: toggling the "internal groups" filter shows/hides internal
(e.g. computed_) groups while regular groups (Engineering Team) stay visible.
Depends on data_sites: the Engineering Team account group comes via its rbac
dependency, and the internal computed_* groups only appear once devices with
computed attributes exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestCoreGroupFiltering:
    async def test_toggles_visibility_of_internal_groups(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/objects/CoreGroup")

        show_internal_groups_filter = page.get_by_role("row", name="internal groups is hidden")
        hide_internal_groups_filter = page.get_by_role("row", name="Hide internal groups")
        engineering_team_link = page.get_by_test_id("object-items").get_by_role("link", name="Engineering Team")
        computed_group_link = page.get_by_test_id("object-items").get_by_role("link", name="computed_").first

        await expect(show_internal_groups_filter).to_be_visible()
        await expect(engineering_team_link).to_be_visible()
        await expect(computed_group_link).to_be_hidden()

        await show_internal_groups_filter.click()

        await expect(hide_internal_groups_filter).to_be_visible()
        await expect(engineering_team_link).to_be_visible()
