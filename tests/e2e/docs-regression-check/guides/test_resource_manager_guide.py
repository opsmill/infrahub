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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.sync_api import Page


@pytest.mark.skip(reason="`test.describe.fixme` in the source (Guide - Resources Manager); preserved as skipped.")
class TestResourcesManagerGuide:
    def test_ip_address_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create prefix 10.100.0.0/24
        admin_page.goto("/ipam")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Prefix *").fill("10.100.0.0/24")
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_rss_prefix_10_100_0")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("IPPrefix created")).to_be_visible()

        # create IP pool - 10.100.0.0/24
        admin_page.goto("/resource-manager")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="IP Address Pool Core").click()
        admin_page.get_by_role("textbox", name="Name *").fill("My IP address pool")
        admin_page.get_by_role("spinbutton", name="Default Prefix Length").fill("24")
        admin_page.get_by_test_id("side-panel-container").locator("div").filter(has_text="Resources *").first.click()
        admin_page.locator("form").get_by_placeholder("Filter...").fill("10.100.0")
        admin_page.get_by_role("option", name="10.100.0.0/").click()
        admin_page.locator("div").filter(has_text=re.compile(r"^Resources \*$")).click()
        admin_page.get_by_role("combobox", name="IPAM Namespace *").click()
        admin_page.get_by_role("option", name="default").click()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_ip")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("IP address pool created")).to_be_visible()

        # use pool to allocate IP on a device
        admin_page.goto("/objects/InfraDevice")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("combobox", name="Site").click()
        admin_page.get_by_role("option", name="atl1").click()
        admin_page.get_by_role("textbox", name="Name *").fill("dev-123")
        admin_page.get_by_role("textbox", name="Type *").fill("MX204")
        admin_page.get_by_test_id("select-open-pool-option-button").click()
        expect(admin_page.get_by_role("option", name="My IP address pool")).to_be_visible()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_device_before")
        admin_page.get_by_role("option", name="My IP address pool").click()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_device_after")
        admin_page.get_by_role("button", name="Save").click()

    def test_ip_prefix_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create prefix 10.100.1.0/24
        admin_page.goto("/ipam")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Prefix *").fill("10.100.1.0/24")
        admin_page.get_by_role("combobox", name="Member Type").click()
        admin_page.locator("div").filter(has_text=re.compile(r"^Prefix$")).click()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_rss_prefix_10_100_1")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("IPPrefix created")).to_be_visible()

        # create prefix pool - 10.100.1.0/24
        admin_page.goto("/resource-manager")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="IP Prefix Pool Core").click()
        admin_page.get_by_role("textbox", name="Name *").fill("Customer Service Pool")
        admin_page.get_by_label("Default Prefix Length").fill("31")
        admin_page.get_by_test_id("side-panel-container").locator("div").filter(has_text="Resources *").first.click()
        admin_page.locator("form").get_by_placeholder("Filter...").fill("10.100.1")
        admin_page.get_by_role("option", name="10.100.1.0/").click()
        admin_page.locator("div").filter(has_text=re.compile(r"^Resources \*$")).click()
        admin_page.get_by_role("combobox", name="IPAM Namespace *").click()
        admin_page.get_by_role("option", name="default").click()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_prefix")
        admin_page.get_by_role("button", name="Save").click()

    def test_number_pool(self, admin_page: Page, data_sites: SitesHandle) -> None:
        # create number pool - VLAN ID
        admin_page.goto("/resource-manager")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Number Pool Core").click()
        admin_page.get_by_label("Name *").fill("My VLAN ID Pool")
        admin_page.get_by_label("Node *").click()
        filter_input = admin_page.get_by_placeholder("Filter...").nth(1)
        filter_input.fill("VLAN")
        admin_page.get_by_text("VLAN Infra").click()
        expect(admin_page.get_by_label("Number Attribute *")).to_contain_text("Vlan Id")
        admin_page.get_by_role("spinbutton", name="Start range *").fill("100")
        admin_page.get_by_role("spinbutton", name="End range *").fill("1000")
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Number pool created")).to_be_visible()

        # use pool to allocate ID to a VLAN
        admin_page.goto("/objects/InfraVLAN")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("textbox", name="Name *").fill("My vlan")
        admin_page.get_by_test_id("number-pool-button").click()
        expect(admin_page.get_by_role("option", name="My VLAN ID Pool")).to_be_visible()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan_before")
        admin_page.get_by_role("option", name="My VLAN ID Pool").click()
        save_screenshot_for_docs(admin_page, "guides/resources-manager/resource_manager_pool_vlan_after")
        admin_page.get_by_role("button", name="Save").click()
