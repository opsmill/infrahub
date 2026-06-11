"""Port of frontend/app/tests/e2e/objects/convert/object-convert.spec.ts.

Object details "Convert object type": convert an InfraInterfaceL3 (Ethernet1 on
atl1-edge1) to an InfraInterfaceL2, mapping source-object field values onto the
target form. Runs as Admin on a throwaway branch cut from main; the data_sites
dependency provides atl1-edge1's Ethernet1 (connected to atl1-edge2 via the
per-site cabling) with the speed/role/status values the mapping form asserts.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectDetailsConvert:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-convert")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_convert_an_interface_l3_to_an_interface_l2(self, admin_page: Page, branch: str) -> None:
        # access object details and convert page
        await admin_page.goto(f"/objects/InfraInterface?branch={branch}")
        await admin_page.get_by_role("link", name="Ethernet1", exact=True).first.click()
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Convert object type").click()
        await save_screenshot_for_docs(admin_page, "object_convert_button")
        await expect(admin_page.get_by_text("SOURCE")).to_be_visible()
        await expect(admin_page.get_by_text("NameEthernet1")).to_be_visible()
        await expect(admin_page.get_by_test_id("convert-source").get_by_text("Deviceatl1-edge1")).to_be_visible()

        # display the interface L3 form with default values from the source object
        await admin_page.get_by_text("Select target object type").click()
        await admin_page.get_by_placeholder("Filter...").fill("l2")
        await admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()
        await expect(admin_page.get_by_role("combobox").filter(has_text="atl1-edge1• Device")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "object_convert_mapping")
        await admin_page.get_by_role("combobox").filter(has_text="atl1-edge1• Device").click()

        await expect(admin_page.get_by_role("option", name="atl1-edge1 Matched Device")).to_be_visible()

        await expect(admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Name")).to_be_visible()
        await expect(
            admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Connected Endpoint")
        ).to_be_visible()
        await expect(admin_page.get_by_role("combobox").filter(has_text="Connected to atl1-edge2::")).to_be_visible()
        await expect(admin_page.get_by_role("combobox").filter(has_text="• LACP Priority")).to_be_visible()
        await expect(admin_page.get_by_role("combobox").filter(has_text="• Enabled")).to_be_visible()
        await expect(admin_page.get_by_role("combobox").filter(has_text="Active• Status")).to_be_visible()
        await expect(admin_page.get_by_role("combobox").filter(has_text="Peer• Role")).to_be_visible()

        # select other values from the source object
        # Select an option from the dropdown
        await admin_page.get_by_role("combobox", name="Layer2 Mode *").click()
        await admin_page.get_by_role("option", name="Access").click()

        # Select an option for the text value from another field in the source object
        await admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Name").click()
        await expect(admin_page.get_by_role("option", name="Ethernet1 Matched Name")).to_be_visible()
        await expect(admin_page.get_by_role("option", name="Connected to atl1-edge2::")).to_be_visible()
        await admin_page.get_by_role("option", name="Connected to atl1-edge2::").click()

        # Select an option for the number value from another field in the source object
        await admin_page.get_by_role("combobox").filter(has_text="• LACP Priority").click()
        await expect(admin_page.get_by_role("option", name="Matched LACP Priority")).to_be_visible()
        await expect(admin_page.get_by_role("option", name="Speed")).to_be_visible()
        await admin_page.get_by_text("10000Speed").click()
        await expect(
            admin_page.locator("div")
            .filter(has_text=re.compile(r"^LACP Priority Number10000• SpeedFrom sourceCustom value$"))
            .get_by_role("combobox")
        ).to_be_visible()

        # Select an option for the dropdown value from another field in the source object
        await admin_page.get_by_role("combobox").filter(has_text="Active• Status").click()
        await expect(admin_page.get_by_role("option", name="Active Matched Status")).to_be_visible()

        # Submit and check object values
        await admin_page.get_by_role("button", name="Convert", exact=True).click()
        await expect(admin_page.get_by_text("Successfully converted")).to_be_visible()
        await expect(admin_page.get_by_text("NameConnected to atl1-edge2::")).to_be_visible()
        await admin_page.get_by_text("LACP Priority10000").click()
        await expect(
            admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="Interface L2")
        ).to_be_visible()
