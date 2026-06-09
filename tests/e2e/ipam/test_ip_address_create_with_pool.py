"""Port of frontend/app/tests/e2e/ipam/ip-address-create-with-pool.spec.ts.

Allocate an IP address from the seeded "Management addresses pool". The first
allocation off a fresh branch is deterministic: 172.16.0.31/16.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestAllocateIpAddressWithPool:
    @pytest.fixture
    def branch(self, branch_api: BranchAPI, infrastructure_data: None) -> Generator[str, None, None]:
        name = generate_random_branch_name("ip-address-pool-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_create_an_ip_address_using_a_pool(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/ipam/ip_addresses?branch={branch}")
        admin_page.get_by_test_id("create-object-button").click()

        admin_page.get_by_test_id("select-open-pool-option-button").click()
        admin_page.get_by_role("option", name="Management addresses pool").click()
        expect(admin_page.get_by_label("Address *")).to_contain_text("Allocated by pool")
        expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("Management addresses pool")
        admin_page.get_by_label("Description").fill("address from pool")
        admin_page.get_by_role("button", name="Save").click()

        expect(admin_page.get_by_text("IP Address 172.16.0.31/16 created")).to_be_visible()
        admin_page.get_by_test_id("object-list-search-bar").get_by_role("searchbox", name="Search").fill(
            "172.16.0.31/16"
        )
        expect(admin_page.get_by_text("address from pool")).to_be_visible()
