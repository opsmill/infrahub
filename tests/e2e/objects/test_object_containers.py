"""Field sections on the detail page and in the edit form of the demo LAG interfaces.

The demo schema groups the fields of InfraLagInterface into the LACP, Layer 2
and Layer 3 sections. Opens port-channel1 of atl1-leaf1 (an
InfraLagInterfaceL2) and port-channel3 of atl1-leaf1 (the only
InfraLagInterfaceL3 of the dataset) on a throwaway branch, hence the
data_sites dependency.
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


class TestObjectContainers:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-containers")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_show_sections_on_the_detail_page_and_save_a_value_from_a_section_panel(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(
            f'/objects/InfraLagInterfaceL2?branch={branch}&filters=[{{"name":"name__value","value":"port-channel1"}}]'
        )
        await (
            admin_page.get_by_role("row")
            .filter(has_text="atl1-leaf1")
            .get_by_role("link", name="port-channel1", exact=True)
            .click()
        )

        await expect(admin_page.get_by_role("region", name="Details", exact=True)).to_be_visible()
        lacp_card = admin_page.get_by_role("region", name="LACP", exact=True)
        await expect(lacp_card).to_be_visible()
        await expect(lacp_card.get_by_text("Minimum links1")).to_be_visible()
        await expect(admin_page.get_by_role("region", name="Layer 2", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Advanced", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("region", name="Layer 3", exact=True)).to_have_count(0)

        await admin_page.get_by_test_id("edit-button").click()
        await (
            admin_page.get_by_label("sheet")
            .get_by_role("region", name="LACP", exact=True)
            .get_by_label("Minimum links")
            .fill("4")
        )
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("LagInterfaceL2 updated")).to_be_visible()
        await expect(admin_page.get_by_label("sheet")).to_be_hidden()
        await expect(lacp_card.get_by_text("Minimum links4")).to_be_visible()

        await admin_page.goto(f"/objects/InfraLagInterfaceL3?branch={branch}")
        await admin_page.get_by_role("link", name="port-channel3", exact=True).click()

        await expect(admin_page.get_by_role("region", name="Details", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("region", name="LACP", exact=True)).to_be_visible()
        layer3_card = admin_page.get_by_role("region", name="Layer 3", exact=True)
        await expect(layer3_card).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Advanced", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("region", name="Layer 2", exact=True)).to_have_count(0)

        await layer3_card.get_by_role("button", name="Layer 3", exact=True).click()
        await expect(layer3_card.get_by_text("MTU1500")).to_be_visible()
