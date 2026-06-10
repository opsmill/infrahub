"""Port of frontend/app/tests/e2e/object-template/template-with-ip-pool.spec.ts.

Serial: create a device template whose primary_address is allocated from the
"Loopbacks pool", create a device from that template, then verify the
pool-allocated address on the detail view. Shares one branch + the created
template across the tests (uniform fixtures keep definition order).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import IpamPoolsHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestTemplateWithIpPool:
    @pytest.fixture(scope="class")
    async def template_branch(
        self, infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("template-pool-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_device_template_with_pool_for_primary_address(
        self, admin_page: Page, template_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Object Template")

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Device Infra").click()
        await admin_page.get_by_label("Template Name *").fill("pool_device_template")
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="Loopbacks pool").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()
        await expect(admin_page.get_by_label("Primary_Address")).to_contain_text("Allocated by pool")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraDevice created")).to_be_visible()

    async def test_template_pool_values_excluded_from_create_mutation(
        self, admin_page: Page, template_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Device")

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("button", name="Start from template").click()
        await admin_page.get_by_role("option", name="pool_device_template").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()
        await expect(admin_page.get_by_label("Primary IP Address")).to_contain_text("Loopbacks pool")

        await admin_page.get_by_role("textbox", name="Name *").fill("device-from-pool-template")
        await admin_page.get_by_role("textbox", name="Type *").fill("test type")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Device created")).to_be_visible()

    async def test_pool_allocated_primary_address_on_detail_view(self, admin_page: Page, template_branch: str) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={template_branch}")
        await admin_page.get_by_role("link", name="device-from-pool-template").click()
        # the allocated IP should be visible as a link
        await expect(admin_page.get_by_text("Primary IP Address10.0.0.")).to_be_visible()
