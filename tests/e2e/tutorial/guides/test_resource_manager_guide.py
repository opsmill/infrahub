"""Port of guides/resource_manager_guide.spec.ts.

Preserved as skipped: the source describe is `test.describe.fixme` (the Resources
Manager guide walkthrough is disabled in the legacy suite). Bodies are ported so
coverage maps 1:1.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


@pytest.mark.skip(reason="`test.describe.fixme` in the source (Guide - Resources Manager); preserved as skipped.")
class TestResourcesManagerGuide:
    async def test_ip_address_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create prefix 10.100.0.0/24
        await admin_page.goto("/ipam")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Prefix *").fill("10.100.0.0/24")
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_rss_prefix_10_100_0")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IPPrefix created")).to_be_visible()

        # create IP pool - 10.100.0.0/24
        await admin_page.goto("/resource-manager")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="IP Address Pool Core").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("My IP address pool")
        await admin_page.get_by_role("spinbutton", name="Default Prefix Length").fill("24")
        await admin_page.get_by_label("sheet").locator("div").filter(has_text="Resources *").first.click()
        await admin_page.locator("form").get_by_placeholder("Filter...").fill("10.100.0")
        await admin_page.get_by_role("option", name="10.100.0.0/").click()
        await admin_page.locator("div").filter(has_text=re.compile(r"^Resources \*$")).click()
        await admin_page.get_by_role("combobox", name="IPAM Namespace *").click()
        await admin_page.get_by_role("option", name="default").click()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_ip")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP address pool created")).to_be_visible()

        # use pool to allocate IP on a device
        await admin_page.goto("/objects/InfraDevice")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Site").click()
        await admin_page.get_by_role("option", name="atl1").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("dev-123")
        await admin_page.get_by_role("textbox", name="Type *").fill("MX204")
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await expect(admin_page.get_by_role("option", name="My IP address pool")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_device_before")
        await admin_page.get_by_role("option", name="My IP address pool").click()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_device_after")
        await admin_page.get_by_role("button", name="Save").click()

    async def test_ip_prefix_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create prefix 10.100.1.0/24
        await admin_page.goto("/ipam")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Prefix *").fill("10.100.1.0/24")
        await admin_page.get_by_role("combobox", name="Member Type").click()
        await admin_page.locator("div").filter(has_text=re.compile(r"^Prefix$")).click()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_rss_prefix_10_100_1")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IPPrefix created")).to_be_visible()

        # create prefix pool - 10.100.1.0/24
        await admin_page.goto("/resource-manager")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="IP Prefix Pool Core").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("Customer Service Pool")
        await admin_page.get_by_label("Default Prefix Length").fill("31")
        await admin_page.get_by_label("sheet").locator("div").filter(has_text="Resources *").first.click()
        await admin_page.locator("form").get_by_placeholder("Filter...").fill("10.100.1")
        await admin_page.get_by_role("option", name="10.100.1.0/").click()
        await admin_page.locator("div").filter(has_text=re.compile(r"^Resources \*$")).click()
        await admin_page.get_by_role("combobox", name="IPAM Namespace *").click()
        await admin_page.get_by_role("option", name="default").click()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_prefix")
        await admin_page.get_by_role("button", name="Save").click()

    async def test_number_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create number pool - VLAN ID
        await admin_page.goto("/resource-manager")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill("My VLAN ID Pool")
        await admin_page.get_by_label("Node *").click()
        filter_input = admin_page.get_by_placeholder("Filter...").nth(1)
        await filter_input.fill("VLAN")
        await admin_page.get_by_text("VLAN Infra").click()
        await expect(admin_page.get_by_label("Number Attribute *")).to_contain_text("Vlan Id")
        await admin_page.get_by_role("spinbutton", name="Start range *").fill("100")
        await admin_page.get_by_role("spinbutton", name="End range *").fill("1000")
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

        # use pool to allocate ID to a VLAN
        await admin_page.goto("/objects/InfraVLAN")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("My vlan")
        await admin_page.get_by_test_id("number-pool-button").click()
        await expect(admin_page.get_by_role("option", name="My VLAN ID Pool")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan_before")
        await admin_page.get_by_role("option", name="My VLAN ID Pool").click()
        await save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan_after")
        await admin_page.get_by_role("button", name="Save").click()
