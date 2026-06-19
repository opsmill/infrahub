"""Port of frontend/app/tests/e2e/objects/list/object-list-select-range.spec.ts.

/objects/:objectKind - shift-click range selection of list rows: forward,
backward, from the first row, extend/shrink a range, deselect forward/backward,
anchor reset after select-all, and last-click-as-anchor. Each test is
self-contained, navigating and selecting independently, so it gets its own
throwaway branch cut from main, hence the data_sites dependency (at least 7
device rows; exactly 3 tags via the transitive org-registry slice).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestSelectRange:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("select-range")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_select_range_forward(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).not_to_be_checked()

    async def test_should_select_range_backward(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(4).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).not_to_be_checked()

    async def test_should_select_range_starting_from_first_row(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(0).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(2).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).not_to_be_checked()

    async def test_should_extend_range_with_additional_shift_click(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click(modifiers=["Shift"])

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(5).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(6)).not_to_be_checked()

    async def test_should_shrink_range_with_shift_click_closer_to_anchor(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(5).click(modifiers=["Shift"])

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).not_to_be_checked()

    async def test_should_deselect_range_forward_when_shift_clicking_a_selected_row(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(4).click(modifiers=["Shift"])

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).not_to_be_checked()

    async def test_should_deselect_range_backward_when_shift_clicking_a_selected_row(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(4).click(modifiers=["Shift"])

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).not_to_be_checked()

    async def test_should_reset_anchor_after_selecting_all_rows(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell")).to_have_count(3)
        await admin_page.get_by_test_id("select-all-rows").click()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(1).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()

    async def test_should_use_last_click_as_shift_click_anchor(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(6).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(2).click(modifiers=["Shift"])

        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(4).click()
        await admin_page.get_by_test_id("identifier-checkbox-cell").nth(3).click(modifiers=["Shift"])

        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(0)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(1)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(2)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(3)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(4)).not_to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(5)).to_be_checked()
        await expect(admin_page.get_by_test_id("identifier-checkbox-cell").nth(6)).to_be_checked()
