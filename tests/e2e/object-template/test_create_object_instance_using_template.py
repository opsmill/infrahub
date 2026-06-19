"""Port of frontend/app/tests/e2e/object-template/create-object-instance-using-template.spec.ts.

Create a profile, then a template using that profile, then a node from the
template — verifying template + profile values are inherited. Runs on a
throwaway branch; depends on data_profiles_groups (upstream_profile) and
data_patch_template (Regular_Patch_Panel).
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

    from data.handles import PatchTemplateHandle, ProfilesGroupsHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestCreateObjectInstanceUsingTemplate:
    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        data_profiles_groups: ProfilesGroupsHandle,
        data_patch_template: PatchTemplateHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("object-template-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_create_nodes_from_a_template(self, admin_page: Page, branch: str) -> None:
        # should create profile first
        await admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        await expect(admin_page.get_by_role("heading", name="Profile")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="upstream_profile")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Patch Panel Infra").click()
        await admin_page.get_by_label("Profile Name *").fill("Profile for patch panel")
        await admin_page.get_by_label("Module Capacity").fill("1000")
        await admin_page.get_by_label("Description").fill("Description from profile")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraPatchPanel created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Profile for patch panel")).to_be_visible()

        # should create a template with the profile
        await admin_page.goto(f"/objects/CoreObjectTemplate?branch={branch}")
        await expect(admin_page.get_by_role("heading", name="Object Templates")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Regular_Patch_Panel")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Patch Panel Infra").click()
        await admin_page.get_by_label("Select profiles optional").click()
        await admin_page.get_by_role("option", name="Profile for patch panel").click()
        await expect(admin_page.get_by_test_id("source-profile-badge").first).to_be_visible()
        await expect(admin_page.get_by_role("textbox", name="Description")).to_have_value("Description from profile")
        await admin_page.get_by_label("Template Name *").fill("Template with profile")
        await admin_page.get_by_label("Module Capacity").fill("2000")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraPatchPanel created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Template with profile")).to_be_visible()

        # should create a node from the template
        await admin_page.goto(f"/objects/InfraPatchPanel?branch={branch}")
        await expect(admin_page.get_by_role("heading", name="Patch Panel")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("button", name="Start from template Pick a").click()
        await admin_page.get_by_role("option", name="Template with profile").click()
        await expect(admin_page.get_by_test_id("source-template-badge")).to_be_visible()
        await expect(admin_page.get_by_test_id("source-profile-badge")).to_be_visible()
        await expect(admin_page.get_by_role("textbox", name="Description")).to_have_value("Description from profile")
        await expect(admin_page.get_by_label("Module Capacity")).to_have_value("2000")
        await admin_page.get_by_label("Name *").fill("Test from template and profile")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("PatchPanel created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Test from template and profile")).to_be_visible()
        await expect(admin_page.get_by_text("2000")).to_be_visible()
        await expect(admin_page.get_by_text("Description from profile")).to_be_visible()
