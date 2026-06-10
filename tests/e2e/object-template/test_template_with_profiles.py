"""Port of frontend/app/tests/e2e/object-template/template-with-profiles.spec.ts.

Serial: create a device profile, a device template that uses it, then a device
from the template — verifying the profile values are inherited (via metadata).
Shares one branch + the created profile/template; depends on the demo data
(upstream_profile, Regular_Patch_Panel, atl1-core1, Cisco IOS).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestTemplateWithProfiles:
    @pytest.fixture(scope="class")
    def template_branch(
        self, infrahub_client: InfrahubClientSync, infrastructure_data: None
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("template-with-profiles-")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_create_a_device_profile_for_templates(self, admin_page: Page, template_branch: str) -> None:
        admin_page.goto(f"/objects/CoreProfile?branch={template_branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Profile")
        expect(admin_page.get_by_role("link", name="upstream_profile")).to_be_visible()

        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Device").click()
        admin_page.get_by_label("Profile Name *").fill("device_spine_profile")
        admin_page.get_by_label("Status").click()
        admin_page.get_by_role("option", name="Active").click()
        admin_page.get_by_label("Role").click()
        admin_page.get_by_role("option", name="Spine Router").click()
        admin_page.get_by_role("button", name="Save").click()

        expect(admin_page.get_by_role("link", name="device_spine_profile")).to_be_visible()

    def test_create_a_template_and_assign_profile_to_it(self, admin_page: Page, template_branch: str) -> None:
        admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Object Template")
        expect(admin_page.get_by_role("link", name="Regular_Patch_Panel")).to_be_visible()

        # create device template
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Device").click()
        expect(admin_page.get_by_role("button", name="Select profiles optional")).to_be_visible()
        admin_page.get_by_role("button", name="Select profiles optional").click()
        admin_page.get_by_role("option", name="device_spine_profile").click()
        expect(admin_page.get_by_test_id("source-profile-badge").first).to_be_visible()
        admin_page.get_by_test_id("source-profile-badge").nth(1).click()
        admin_page.get_by_label("Template Name *").fill("device_spine_template")
        admin_page.get_by_label("Platform").click()
        admin_page.get_by_text("Cisco IOS", exact=True).click()
        admin_page.get_by_label("Type", exact=True).fill("spine")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("InfraDevice created")).to_be_visible()

        # navigate back and verify profile is assigned to the template
        admin_page.goto(f"/objects/CoreObjectTemplate?branch={template_branch}")
        admin_page.get_by_role("link", name="device_spine_template").click()
        admin_page.get_by_role("definition").filter(has_text="Active").get_by_test_id("view-metadata-button").click()
        expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="device_spine_profile")
        ).to_be_visible()

    def test_create_object_from_template_with_profile_inherits_values(
        self, admin_page: Page, template_branch: str
    ) -> None:
        admin_page.goto(f"/objects/InfraDevice?branch={template_branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Device")
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()

        # create device from template
        admin_page.get_by_test_id("create-object-button").click()
        expect(admin_page.get_by_role("button", name="Start from template")).to_be_visible()
        admin_page.get_by_role("button", name="Start from template").click()
        admin_page.get_by_role("option", name="device_spine_template").click()

        # verify profile is shown as selected and the form is populated from template/profile
        expect(admin_page.get_by_role("button", name="Select profiles optional")).to_be_visible()
        expect(admin_page.get_by_text("device_spine_profile×")).to_be_visible()
        expect(admin_page.get_by_label("Status")).to_contain_text("Active")
        expect(admin_page.get_by_label("Role")).to_contain_text("Spine Router")
        expect(admin_page.get_by_test_id("source-profile-badge").first).to_be_visible()
        expect(admin_page.get_by_test_id("source-profile-badge").nth(1)).to_be_visible()

        admin_page.get_by_role("textbox", name="Name *").fill("spine-router-01")
        admin_page.get_by_role("button", name="Save").click()

        # navigate to object details
        # The toast id carries the created node's uuid suffix, so prefix-match it.
        expect(admin_page.locator('[id^="alert-success-Device-created"]')).to_contain_text("Device created")
        admin_page.get_by_role("link", name="spine-router-01").click()

        # verify inherited profile values
        admin_page.get_by_role("definition").filter(has_text="Active").get_by_test_id("view-metadata-button").click()
        expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="device_spine_profile")
        ).to_be_visible()
