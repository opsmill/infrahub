"""Port of frontend/app/tests/e2e/object-template/template-with-profiles.spec.ts.

Serial: create a device profile, a device template that uses it, then a device
from the template — verifying the profile values are inherited (via metadata).
Shares one branch + the created profile/template; depends on data_sites
(atl1-core1 in the device list; Cisco IOS via its org_registry dependency),
data_profiles_groups (upstream_profile) and data_patch_template
(Regular_Patch_Panel).
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

    from data.handles import PatchTemplateHandle, ProfilesGroupsHandle, SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestTemplateWithProfiles:
    @pytest.fixture(scope="class")
    async def template_branch(
        self,
        infrahub_client: InfrahubClient,
        data_sites: SitesHandle,
        data_profiles_groups: ProfilesGroupsHandle,
        data_patch_template: PatchTemplateHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("template-with-profiles-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_a_device_profile_for_templates(self, admin_page: Page, template_branch: str) -> None:
        await admin_page.goto(f"/objects/CoreProfile?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Profile")
        await expect(admin_page.get_by_role("link", name="upstream_profile")).to_be_visible()

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Device").click()
        await admin_page.get_by_label("Profile Name *").fill("device_spine_profile")
        await admin_page.get_by_label("Status").click()
        await admin_page.get_by_role("option", name="Active").click()
        await admin_page.get_by_label("Role").click()
        await admin_page.get_by_role("option", name="Spine Router").click()
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_role("link", name="device_spine_profile")).to_be_visible()

    async def test_create_a_template_and_assign_profile_to_it(self, admin_page: Page, template_branch: str) -> None:
        await admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Object Template")
        await expect(admin_page.get_by_role("link", name="Regular_Patch_Panel")).to_be_visible()

        # create device template
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Device").click()
        await expect(admin_page.get_by_role("button", name="Select profiles optional")).to_be_visible()
        await admin_page.get_by_role("button", name="Select profiles optional").click()
        await admin_page.get_by_role("option", name="device_spine_profile").click()
        await expect(admin_page.get_by_test_id("source-profile-badge").first).to_be_visible()
        await admin_page.get_by_test_id("source-profile-badge").nth(1).click()
        await admin_page.get_by_label("Template Name *").fill("device_spine_template")
        await admin_page.get_by_label("Platform").click()
        await admin_page.get_by_text("Cisco IOS", exact=True).click()
        await admin_page.get_by_label("Type", exact=True).fill("spine")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraDevice created")).to_be_visible()

        # navigate back and verify profile is assigned to the template
        await admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        await admin_page.get_by_role("link", name="device_spine_template").click()
        await (
            admin_page.get_by_role("definition")
            .filter(has_text="Active")
            .get_by_test_id("view-metadata-button")
            .click()
        )
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="device_spine_profile")
        ).to_be_visible()

    async def test_create_object_from_template_with_profile_inherits_values(
        self, admin_page: Page, template_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={template_branch}")
        await expect(admin_page.get_by_role("heading")).to_contain_text("Device")
        await expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()

        # create device from template
        await admin_page.get_by_test_id("create-object-button").click()
        await expect(admin_page.get_by_role("button", name="Start from template")).to_be_visible()
        await admin_page.get_by_role("button", name="Start from template").click()
        await admin_page.get_by_role("option", name="device_spine_template").click()

        # verify profile is shown as selected and the form is populated from template/profile
        await expect(admin_page.get_by_role("button", name="Select profiles optional")).to_be_visible()
        await expect(admin_page.get_by_text("device_spine_profile×")).to_be_visible()
        await expect(admin_page.get_by_label("Status")).to_contain_text("Active")
        await expect(admin_page.get_by_label("Role")).to_contain_text("Spine Router")
        await expect(admin_page.get_by_test_id("source-profile-badge").first).to_be_visible()
        await expect(admin_page.get_by_test_id("source-profile-badge").nth(1)).to_be_visible()

        await admin_page.get_by_role("textbox", name="Name *").fill("spine-router-01")
        await admin_page.get_by_role("button", name="Save").click()

        # navigate to object details
        # The toast id carries the created node's uuid suffix, so prefix-match it.
        await expect(admin_page.locator('[id^="alert-success-Device-created"]')).to_contain_text("Device created")
        await admin_page.get_by_role("link", name="spine-router-01").click()

        # verify inherited profile values
        await (
            admin_page.get_by_role("definition")
            .filter(has_text="Active")
            .get_by_test_id("view-metadata-button")
            .click()
        )
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="device_spine_profile")
        ).to_be_visible()
