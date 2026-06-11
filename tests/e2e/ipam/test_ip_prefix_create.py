"""Port of frontend/app/tests/e2e/ipam/ip-prefix-create.spec.ts.

Create a root prefix manually, allocate an available child prefix from it, then
allocate IP addresses from the child prefix's pool. Runs on its own throwaway
branch (created via the API). The TS spec is `test.slow()`.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import IpamPoolsHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestAllocateIpPrefix:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_ipam_pools: IpamPoolsHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-prefix-create-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_create_prefix_allocate_child_and_addresses(self, admin_page: Page, branch: str) -> None:
        # Navigate to IPAM root and open create prefix form
        await admin_page.goto(f"/ipam?branch={branch}")
        await expect(
            admin_page.get_by_test_id("identifier-cell").get_by_role("link", name="10.0.0.0/8")
        ).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()

        # Create a root IP prefix 11.0.0.0/8 manually
        await admin_page.get_by_label("Prefix *").fill("11.0.0.0/8")
        await admin_page.get_by_label("Member Type").click()
        await admin_page.get_by_role("option", name="Prefix Prefix serves as").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Prefix 11.0.0.0/8 created")).to_be_visible()
        await expect(admin_page.get_by_label("Prefix *")).not_to_be_visible()

        # Allocate the available child prefix 11.0.0.0/9 from the root prefix
        await admin_page.get_by_test_id("identifier-cell").get_by_role("link", name="11.0.0.0/8").click()
        await admin_page.get_by_test_id("ip-prefix-available").get_by_role("button", name="11.0.0.0/9").click()
        await expect(admin_page.get_by_label("Prefix *")).to_have_value("11.0.0.0/9")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Prefix 11.0.0.0/9 created")).to_be_visible()
        await expect(admin_page.get_by_label("Prefix *")).not_to_be_visible()

        # Verify child prefix details and available ip addresses
        await admin_page.get_by_test_id("identifier-cell").get_by_role("link", name="11.0.0.0/9").click()
        await expect(
            admin_page.get_by_test_id("ip-address-available").get_by_role("button", name="11.0.0.1/9 11.127.255.254/9")
        ).to_be_visible()
        await expect(admin_page.get_by_text("More than 65536 IP addresses")).to_be_visible()

        # Allocate the first IP address (11.0.0.1/9) from the table
        await (
            admin_page.get_by_test_id("ip-address-available")
            .get_by_role("button", name="11.0.0.1/9 11.127.255.254/9")
            .click()
        )
        await expect(admin_page.get_by_label("Address *")).to_have_value("11.0.0.1/9")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Address 11.0.0.1/9 created")).to_be_visible()
        await expect(
            admin_page.get_by_test_id("identifier-cell").get_by_role("link", name="11.0.0.1/9")
        ).to_be_visible()
        await expect(
            admin_page.get_by_test_id("ip-address-available").get_by_role("button", name="11.0.0.2/9")
        ).to_be_visible()

        # Creation form should suggest an available IP address within the parent prefix
        await admin_page.get_by_test_id("create-object-button").click()
        await expect(admin_page.get_by_label("Address *")).to_have_value("11.0.0.2/9")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Address 11.0.0.2/9 created")).to_be_visible()
