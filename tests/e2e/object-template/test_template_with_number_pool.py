"""Port of frontend/app/tests/e2e/object-template/template-with-number-pool.spec.ts.

Serial: create a CoreNumberPool for module_capacity, a patch-panel template that
allocates module_capacity from it, then a patch panel from that template, and
verify the allocated value + its source pool. Shares one branch + the created
pool/template (uniform fixtures keep definition order).
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
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestTemplateWithNumberPool:
    @pytest.fixture(scope="class")
    async def template_branch(
        self, infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("template-number-pool-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_a_number_pool_for_module_capacity(self, admin_page: Page, template_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={template_branch}")
        await expect(admin_page.get_by_role("link", name="Loopbacks pool")).to_be_visible()

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill("module capacity pool")
        await admin_page.get_by_label("Node *").click()
        await admin_page.get_by_role("option", name="Patch Panel Infra").click()
        await expect(admin_page.get_by_label("Number Attribute *")).to_contain_text("Module Capacity")
        await admin_page.get_by_label("Start range *").fill("100")
        await admin_page.get_by_label("End range *").fill("200")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_create_a_patch_panel_template_with_number_pool(self, admin_page: Page, template_branch: str) -> None:
        await admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Object Template")

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Patch Panel Infra").click()
        await admin_page.get_by_label("Template Name *").fill("number_pool_patch_panel_template")
        await admin_page.get_by_test_id("number-pool-button").click()
        await admin_page.get_by_role("option", name="module capacity pool").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()
        await expect(admin_page.get_by_label("Module Capacity")).to_contain_text("Allocated by pool")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraPatchPanel created")).to_be_visible()

        await admin_page.get_by_role("link", name="number_pool_patch_panel_template").click()
        await expect(admin_page.get_by_text("Module Capacitymodule")).to_be_visible()

    async def test_create_a_patch_panel_from_template_with_number_pool(
        self, admin_page: Page, template_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraPatchPanel?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Patch Panel")

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("button", name="Start from template").click()
        await admin_page.get_by_role("option", name="number_pool_patch_panel_template").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()
        await expect(admin_page.get_by_label("Module Capacity")).to_contain_text("Allocated by pool")

        await admin_page.get_by_role("textbox", name="Name *").fill("patch-panel-from-pool-template")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("PatchPanel created")).to_be_visible()

        # should show pool-allocated module_capacity on the patch panel detail view
        await admin_page.get_by_role("link", name="patch-panel-from-pool-template").click()
        await expect(admin_page.get_by_text("Module Capacity100")).to_be_visible()
        await admin_page.get_by_role("definition").filter(has_text="100").get_by_test_id("view-metadata-button").click()
        await expect(admin_page.get_by_role("cell", name="module capacity pool")).to_be_visible()
