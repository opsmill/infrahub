"""Port of frontend/app/tests/e2e/groups/groups.spec.ts.

Serial: create a Standard Group, then add Builtin Tag members (blue, red) to it.
Shares one branch + the created group; depends on data_profiles_groups (the
arista_devices group shown in the list) and data_org_registry (the blue/red tags
added as members).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import OrgRegistryHandle, ProfilesGroupsHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestCoreGroup:
    @pytest.fixture(scope="class")
    async def groups_branch(
        self,
        infrahub_client: InfrahubClient,
        data_profiles_groups: ProfilesGroupsHandle,
        data_org_registry: OrgRegistryHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("groups-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_a_new_standard_group(self, admin_page: Page, groups_branch: str) -> None:
        await admin_page.goto(f"/objects/CoreGroup?branch={groups_branch}")
        await expect(
            admin_page.get_by_test_id("object-items").get_by_role("link", name="arista_devices")
        ).to_be_visible()

        # fill and submit form for new group
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Standard Group").click()
        await admin_page.get_by_label("Name *").fill("TagConfigGroup")
        await save_screenshot_for_docs(admin_page, "group_tagconfig_grp_new_grp")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("StandardGroup created")).to_be_visible()

    async def test_add_members_to_standard_group(self, admin_page: Page, groups_branch: str) -> None:
        await admin_page.goto(f"/objects/CoreGroup?branch={groups_branch}")

        await admin_page.get_by_label("Hierarchy tree").get_by_text("TagConfigGroup").click()
        await admin_page.get_by_text("Members0").click()
        await admin_page.get_by_test_id("open-relationship-form-button").click()
        await admin_page.get_by_role("combobox", name="Kind").click()
        await admin_page.get_by_role("option", name="Tag Builtin").click()
        await expect(admin_page.get_by_role("option", name="Tag Builtin")).to_be_hidden()
        await admin_page.get_by_label("Tag", exact=True).click()
        await admin_page.get_by_role("option", name="blue").click()

        await save_screenshot_for_docs(admin_page, "group_tagconfig_grp_adding_members")

        await admin_page.get_by_role("button", name="Save").click()
        await admin_page.get_by_test_id("close-alert").click()

        await admin_page.get_by_test_id("open-relationship-form-button").click()
        await admin_page.get_by_role("combobox", name="Kind").click()
        await admin_page.get_by_role("option", name="Tag Builtin").click()
        await admin_page.get_by_label("Tag", exact=True).click()
        await admin_page.get_by_role("option", name="red").click()
        await expect(admin_page.get_by_role("option", name="red")).not_to_be_visible()
        await admin_page.get_by_role("button", name="Save").click()
        await admin_page.get_by_text("Members2").click()

        await save_screenshot_for_docs(admin_page, "group_tagconfig_grp_new_members")
