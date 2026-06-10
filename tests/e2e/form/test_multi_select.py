"""Port of frontend/app/tests/e2e/form/multi-select.spec.ts.

Verify multi-select behaviour: select multiple tags, remove a tag from its
selected badge, and create a new tag directly from the multi-select. Runs on a
throwaway branch and relies on data_sites (the Ethernet11 interface; the
blue/green/red tags come transitively).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestVerifyMultiSelectBehaviour:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_sites: SitesHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("multi-select")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_select_remove_and_create_tags_using_multi_select(self, admin_page: Page, branch: str) -> None:
        # Navigate to Ethernet11
        await admin_page.goto(f"/objects/InfraInterfaceL2?branch={branch}")
        await admin_page.get_by_role("link", name="Ethernet11", exact=True).first.click()

        await admin_page.get_by_test_id("edit-button").click()

        # Select multiple tags
        await admin_page.get_by_label("Tags").click()
        await admin_page.get_by_role("option", name="blue").click()
        await expect(admin_page.get_by_role("option", name="blue")).not_to_be_visible()
        await admin_page.get_by_role("option", name="green").click()
        await expect(admin_page.get_by_role("option", name="green")).not_to_be_visible()
        await admin_page.get_by_role("option", name="red").click()
        await expect(admin_page.get_by_role("option", name="red")).not_to_be_visible()
        await expect(admin_page.locator("form")).to_contain_text("blue×green×red×")

        # Remove a tag when clicking on selected badge
        await admin_page.get_by_text("red×").get_by_label("Remove").click()
        await expect(admin_page.locator("form")).to_contain_text("blue×green×")

        # Create a new tag directly on multi select
        await admin_page.get_by_role("button", name="+ Add new Tag").click()
        await admin_page.get_by_test_id("new-object-form").get_by_label("Name *").fill("new tag")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("new tag×")).to_be_visible()
