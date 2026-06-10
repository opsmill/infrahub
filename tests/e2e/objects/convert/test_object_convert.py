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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestObjectDetailsConvert:
    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        data_sites: SitesHandle,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("object-convert")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_convert_an_interface_l3_to_an_interface_l2(self, admin_page: Page, branch: str) -> None:
        # access object details and convert page
        admin_page.goto(f"/objects/InfraInterface?branch={branch}")
        admin_page.get_by_role("link", name="Ethernet1", exact=True).first.click()
        admin_page.get_by_test_id("object-details-menu").click()
        admin_page.get_by_role("menuitem", name="Convert object type").click()
        save_screenshot_for_docs(admin_page, "object_convert_button")
        expect(admin_page.get_by_text("SOURCE")).to_be_visible()
        expect(admin_page.get_by_text("NameEthernet1")).to_be_visible()
        expect(admin_page.get_by_test_id("convert-source").get_by_text("Deviceatl1-edge1")).to_be_visible()

        # display the interface L3 form with default values from the source object
        admin_page.get_by_text("Select target object type").click()
        admin_page.get_by_placeholder("Filter...").fill("l2")
        admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()
        expect(admin_page.get_by_role("combobox").filter(has_text="atl1-edge1• Device")).to_be_visible()
        save_screenshot_for_docs(admin_page, "object_convert_mapping")
        admin_page.get_by_role("combobox").filter(has_text="atl1-edge1• Device").click()

        expect(admin_page.get_by_role("option", name="atl1-edge1 Matched Device")).to_be_visible()

        expect(admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Name")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Connected Endpoint")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="Connected to atl1-edge2::")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="• LACP Priority")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="• Enabled")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="Active• Status")).to_be_visible()
        expect(admin_page.get_by_role("combobox").filter(has_text="Peer• Role")).to_be_visible()

        # select other values from the source object
        # Select an option from the dropdown
        admin_page.get_by_role("combobox", name="Layer2 Mode *").click()
        admin_page.get_by_role("option", name="Access").click()

        # Select an option for the text value from another field in the source object
        admin_page.get_by_role("combobox").filter(has_text="Ethernet1• Name").click()
        expect(admin_page.get_by_role("option", name="Ethernet1 Matched Name")).to_be_visible()
        expect(admin_page.get_by_role("option", name="Connected to atl1-edge2::")).to_be_visible()
        admin_page.get_by_role("option", name="Connected to atl1-edge2::").click()

        # Select an option for the number value from another field in the source object
        admin_page.get_by_role("combobox").filter(has_text="• LACP Priority").click()
        expect(admin_page.get_by_role("option", name="Matched LACP Priority")).to_be_visible()
        expect(admin_page.get_by_role("option", name="Speed")).to_be_visible()
        admin_page.get_by_text("10000Speed").click()
        expect(
            admin_page.locator("div")
            .filter(has_text=re.compile(r"^LACP Priority Number10000• SpeedFrom sourceCustom value$"))
            .get_by_role("combobox")
        ).to_be_visible()

        # Select an option for the dropdown value from another field in the source object
        admin_page.get_by_role("combobox").filter(has_text="Active• Status").click()
        expect(admin_page.get_by_role("option", name="Active Matched Status")).to_be_visible()

        # Submit and check object values
        admin_page.get_by_role("button", name="Convert", exact=True).click()
        expect(admin_page.get_by_text("Successfully converted")).to_be_visible()
        expect(admin_page.get_by_text("NameConnected to atl1-edge2::")).to_be_visible()
        admin_page.get_by_text("LACP Priority10000").click()
        expect(
            admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="Interface L2")
        ).to_be_visible()
