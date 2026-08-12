"""Port of frontend/app/tests/e2e/objects/object-groups.spec.ts.

Object groups manager: create a BuiltinTag, open its Groups manager, add two
demo groups (arista_devices / backbone_interfaces), filter the list, leave a
group and confirm the add-form retains the remaining default. Runs on a
throwaway branch cut from main; the arista_devices / backbone_interfaces group
memberships are populated by the topology stage, hence the data_topology
dependency on the branch fixture.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import TopologyHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestObjectGroupsUpdate:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_topology: TopologyHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-groups")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_contain_initial_values_and_update_them(self, admin_page: Page, branch: str) -> None:
        # access the tags and create a new one
        await admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        await expect(admin_page.get_by_role("link", name="blue")).to_be_visible()
        await expect(admin_page.get_by_test_id("create-object-button")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Name *").fill("group-tag")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Tag created")).to_be_visible()

        # go to the new tag
        await admin_page.get_by_role("link", name="group-tag").click()
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Groups").click()
        await expect(admin_page.get_by_role("heading", name="Manage groups", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("There are no groups to display")).to_be_visible()

        # open groups manager
        await admin_page.get_by_test_id("open-group-form-button").click()

        # add groups to an object
        await admin_page.get_by_label("Add groups *").click()
        await admin_page.get_by_role("option", name="arista_devices").click()
        await admin_page.get_by_role("option", name="backbone_interfaces").click()
        await admin_page.get_by_label("Add groups *").click()  # to close the combobox
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("2 groups added")).to_be_visible()
        await expect(admin_page.get_by_text("2 groups added")).to_be_hidden()

        # auto-generated toggle button not visible if there is no auto-generated groups
        await expect(admin_page.get_by_role("button", name="auto-generated")).not_to_be_visible()

        # Scope the manager-list assertions to the group-manager sheet: after the SlideOver ->
        # Sheet migration the group links/controls can match duplicates elsewhere on the page.
        group_manager = admin_page.get_by_test_id("group-manager")

        # new groups are visible in groups manager
        await expect(group_manager.get_by_role("link", name="arista_devices")).to_be_visible()
        await expect(group_manager.get_by_role("link", name="backbone_interfaces")).to_be_visible()
        await expect(group_manager.get_by_role("link", name="Standard Group").first).to_be_visible()

        # filter groups
        await group_manager.get_by_placeholder("filter groups...").fill("ari")
        await expect(group_manager.get_by_role("link", name="arista_devices")).to_be_visible()
        await expect(group_manager.get_by_role("link", name="backbone_interfaces")).not_to_be_visible()

        await group_manager.get_by_placeholder("filter groups...").fill("")
        await expect(group_manager.get_by_role("link", name="arista_devices")).to_be_visible()
        await expect(group_manager.get_by_role("link", name="backbone_interfaces")).to_be_visible()

        # leave arista_devices group
        await group_manager.get_by_test_id("leave-group-button").first.click()
        await expect(admin_page.get_by_role("heading", name="Leave Group")).to_be_visible()
        await expect(admin_page.get_by_text("Are you sure you want to leave group arista_devices?")).to_be_visible()
        await admin_page.get_by_test_id("modal-delete-confirm").click()

        # arista_devices group is not visible in groups manager
        await expect(group_manager.get_by_role("link", name="backbone_interfaces")).to_be_visible()
        await expect(group_manager.get_by_role("link", name="arista_devices")).not_to_be_visible()

        # add group form default values is visible
        await group_manager.get_by_test_id("open-group-form-button").click()
        await expect(admin_page.get_by_text("backbone_interfaces×")).to_be_visible()
        await expect(admin_page.get_by_text("arista_devices×")).not_to_be_visible()
