"""Port of frontend/app/tests/e2e/groups/groups-filter.spec.ts.

CoreGroup list: toggling the "internal groups" filter shows/hides internal
(e.g. computed_) groups while regular groups (Engineering Team) stay visible.
Depends on the demo data (the Engineering Team account group).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestCoreGroupFiltering:
    def test_toggles_visibility_of_internal_groups(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/objects/CoreGroup")

        show_internal_groups_filter = page.get_by_role("row", name="internal groups is hidden")
        hide_internal_groups_filter = page.get_by_role("row", name="Hide internal groups")
        engineering_team_link = page.get_by_test_id("object-items").get_by_role("link", name="Engineering Team")
        computed_group_link = page.get_by_test_id("object-items").get_by_role("link", name="computed_").first

        expect(show_internal_groups_filter).to_be_visible()
        expect(engineering_team_link).to_be_visible()
        expect(computed_group_link).to_be_hidden()

        show_internal_groups_filter.click()

        expect(hide_internal_groups_filter).to_be_visible()
        expect(engineering_team_link).to_be_visible()
