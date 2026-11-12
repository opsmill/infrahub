"""Rack elevation: view both faces of a rack, place items from the drawing, and download the item list.

Runs on a rack model that provides the ``data_rack_elevation`` fixture; it is skipped on the base branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from data.handles import RackElevationHandle
    from playwright.async_api import Locator, Page

ITEM_NAMES = ["leaf1", "leaf2", "srv1", "pp1", "blank1", "pdu1", "spare1"]


def _item(page: Page, name: str, face: str | None = None, position: int | None = None) -> Locator:
    selector = f'[data-testid="rack-item-{name}"]'
    if face is not None:
        selector += f'[data-face="{face}"]'
    if position is not None:
        selector += f'[data-position="{position}"]'
    return page.locator(selector)


async def _enter_move_mode(page: Page, name: str, from_list: str | None = None) -> None:
    if from_list is not None:
        await page.get_by_test_id(from_list).get_by_test_id(f"rack-item-{name}").click()
        return
    await _item(page, name, face="front").first.hover()
    await page.get_by_test_id(f"rack-item-move-{name}").click()


class TestRackElevation:
    async def test_elevation_places_items_and_exports_the_item_list(
        self, admin_page: Page, data_rack_elevation: RackElevationHandle
    ) -> None:
        await admin_page.goto(f"/objects/LocationRack/{data_rack_elevation.racks['R1']}/elevation")

        # leaf1 is full depth, so it is drawn at unit 12 on both faces
        await expect(_item(admin_page, "leaf1", face="front", position=12)).to_be_visible()
        await expect(_item(admin_page, "leaf1", face="rear", position=12)).to_be_visible()
        # pp1 is half depth and mounted on the rear
        await expect(_item(admin_page, "pp1", face="rear", position=10)).to_be_visible()
        await expect(_item(admin_page, "pp1", face="front")).to_have_count(0)
        await expect(admin_page.get_by_test_id("rack-list-zero-u").get_by_test_id("rack-item-pdu1")).to_be_visible()
        await expect(
            admin_page.get_by_test_id("rack-list-unpositioned").get_by_test_id("rack-item-spare1")
        ).to_be_visible()

        # move spare1 to unit 5 on the front
        await _enter_move_mode(admin_page, "spare1", from_list="rack-list-unpositioned")
        await admin_page.get_by_test_id("rack-unit-front-5").click()
        await expect(_item(admin_page, "spare1", face="front", position=5)).to_be_visible()
        await expect(
            admin_page.get_by_test_id("rack-list-unpositioned").get_by_test_id("rack-item-spare1")
        ).to_have_count(0)

        # moving srv1 (2U) to unit 12 is refused because it would need unit 13
        await _enter_move_mode(admin_page, "srv1")
        await admin_page.get_by_test_id("rack-unit-front-12").click()
        await expect(admin_page.get_by_text("do not fit in rack R1")).to_be_visible()
        await expect(_item(admin_page, "srv1", face="front", position=1)).to_be_visible()
        await expect(_item(admin_page, "srv1", position=12)).to_have_count(0)

        # the CSV has one line per item of the rack
        async with admin_page.expect_download() as download_info:
            await admin_page.get_by_test_id("rack-export-csv").click()
        download = await download_info.value
        path = await download.path()
        assert path is not None
        lines = path.read_text(encoding="utf-8").splitlines()
        for name in ITEM_NAMES:
            assert len([line for line in lines if name in line.split(",")]) == 1, name
        assert not [line for line in lines if "spare2" in line]
