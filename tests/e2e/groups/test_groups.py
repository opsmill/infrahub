"""Port of frontend/app/tests/e2e/groups/groups.spec.ts.

Serial: create a Standard Group, then add Builtin Tag members (blue, red) to it.
Shares one branch + the created group; depends on the demo data (arista_devices
group, blue/red tags).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestCoreGroup:
    @pytest.fixture(scope="class")
    def groups_branch(
        self, infrahub_client: InfrahubClientSync, infrastructure_data: None
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("groups-")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_create_a_new_standard_group(self, admin_page: Page, groups_branch: str) -> None:
        admin_page.goto(f"/objects/CoreGroup?branch={groups_branch}")
        expect(admin_page.get_by_test_id("object-items").get_by_role("link", name="arista_devices")).to_be_visible()

        # fill and submit form for new group
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Standard Group").click()
        admin_page.get_by_label("Name *").fill("TagConfigGroup")
        save_screenshot_for_docs(admin_page, "group_tagconfig_grp_new_grp")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("StandardGroup created")).to_be_visible()

    def test_add_members_to_standard_group(self, admin_page: Page, groups_branch: str) -> None:
        admin_page.goto(f"/objects/CoreGroup?branch={groups_branch}")

        admin_page.get_by_label("Hierarchy tree").get_by_text("TagConfigGroup").click()
        admin_page.get_by_text("Members0").click()
        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_role("combobox", name="Kind").click()
        admin_page.get_by_role("option", name="Tag Builtin").click()
        expect(admin_page.get_by_role("option", name="Tag Builtin")).to_be_hidden()
        admin_page.get_by_label("Tag", exact=True).click()
        admin_page.get_by_role("option", name="blue").click()

        save_screenshot_for_docs(admin_page, "group_tagconfig_grp_adding_members")

        admin_page.get_by_role("button", name="Save").click()
        admin_page.get_by_test_id("close-alert").click()

        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_role("combobox", name="Kind").click()
        admin_page.get_by_role("option", name="Tag Builtin").click()
        admin_page.get_by_label("Tag", exact=True).click()
        admin_page.get_by_role("option", name="red").click()
        expect(admin_page.get_by_role("option", name="red")).not_to_be_visible()
        admin_page.get_by_role("button", name="Save").click()
        admin_page.get_by_text("Members2").click()

        save_screenshot_for_docs(admin_page, "group_tagconfig_grp_new_members")
