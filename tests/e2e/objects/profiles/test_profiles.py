"""Port of frontend/app/tests/e2e/objects/profiles/profiles.spec.ts.

/objects/CoreProfile - Profiles page (a serial flow): create a BuiltinTag
profile, view and edit it, create a tag that uses the profile, verify the
profile metadata propagates, edit the profile and see the change reflected,
remove the profile from the tag, and finally delete the profile (resetting the
object's attribute).

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the `profile test tag` / `tag with profile` objects it creates across tests.
Every test depends on the SAME fixtures (admin_page + branch) and the chain
relies on pytest's default definition-order collection (see the README's
serial-specs gotcha). The branch is cut from main, which carries
the demo dataset (the `upstream_profile`, the `blue` tag), hence the
infrastructure_data dependency.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestProfiles:
    @pytest.fixture(scope="class")
    def branch(
        self,
        infrahub_client: InfrahubClientSync,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("profiles")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_create_a_new_profile(self, admin_page: Page, branch: str) -> None:
        # Navigate to CoreProfile page
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Profile")
        expect(admin_page.get_by_role("link", name="upstream_profile")).to_be_visible()

        # Create a new profile
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Tag Builtin").click()
        admin_page.get_by_label("Profile Name *").fill("profile test tag")
        admin_page.get_by_label("Description").fill("A profile for E2E test")
        admin_page.get_by_role("button", name="Save").click()

        # Verify profile creation success
        expect(
            # The toast id carries the created node's uuid suffix, so prefix-match it.
            admin_page.locator('[id^="alert-success-BuiltinTag-created"]').get_by_text("BuiltinTag created")
        ).to_be_visible()
        expect(admin_page.get_by_role("link", name="profile test tag")).to_be_visible()

    def test_access_view_and_edit_profile(self, admin_page: Page, branch: str) -> None:
        # Navigate to CoreProfile page
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Profile")
        profile_link = admin_page.get_by_role("link", name="profile test tag")
        expect(profile_link).to_be_visible(timeout=30_000)
        admin_page.get_by_role("link", name="profile test tag").click()

        expect(admin_page.get_by_text("Profile Nameprofile test tag")).to_be_visible()
        expect(admin_page.get_by_text("Profile Priority1000")).to_be_visible()
        expect(admin_page.get_by_text("DescriptionA profile for E2E")).to_be_visible()

        # return to profiles list using breadcrumb
        admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="Profile", exact=True).click()
        expect(admin_page.get_by_role("heading", name="Profile")).to_be_visible()
        assert "/objects/CoreProfile" in admin_page.url

    def test_create_an_object_with_a_profile(self, admin_page: Page, branch: str) -> None:
        # Navigate to object creation page
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        expect(admin_page.get_by_role("link", name="blue")).to_be_visible()
        admin_page.get_by_test_id("create-object-button").click()

        # Select profile and enter details
        admin_page.get_by_label("Select profiles").click()
        profile_option = admin_page.get_by_role("option", name="profile test tag")
        expect(profile_option).to_be_visible(timeout=30_000)
        admin_page.get_by_role("option", name="profile test tag").click()
        admin_page.get_by_label("Select profiles").click()

        # Verify initial input fields for profile
        expect(admin_page.get_by_label("Name *")).to_be_empty()
        expect(admin_page.get_by_label("Description")).to_have_value("A profile for E2E test")

        expect(admin_page.get_by_test_id("source-profile-badge")).to_be_visible()
        expect(admin_page.get_by_test_id("source-profile-badge")).to_contain_text("profile test tag")
        admin_page.get_by_test_id("source-profile-badge").hover()
        expect(admin_page.get_by_test_id("source-profile-tooltip").first).to_be_visible()
        expect(admin_page.get_by_role("link", name="profile test tag").first).to_be_visible()
        admin_page.get_by_label("Name *").click()  # hide tooltip

        admin_page.get_by_label("Name *").fill("tag with profile")
        admin_page.get_by_role("button", name="Save").click()

        # Verify object creation
        expect(admin_page.locator('[id^="alert-success-Tag-created"]')).to_contain_text("Tag created")
        admin_page.get_by_role("link", name="tag with profile").click()

        # Verify profile metadata
        admin_page.get_by_text("Nametag with profile").get_by_test_id("view-metadata-button").click()
        expect(admin_page.get_by_test_id("metadata-tooltip").get_by_text("Source-")).to_be_visible()
        admin_page.get_by_text("Nametag with profile").get_by_test_id(
            "view-metadata-button"
        ).click()  # to close popover
        admin_page.get_by_text("DescriptionA profile for E2E").get_by_test_id("view-metadata-button").click()
        expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="profile test tag")
        ).to_be_visible()

        # Verify profile link
        admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="profile test tag").click()
        assert "/objects/ProfileBuiltinTag/" in admin_page.url

    def test_edit_used_profile_reflects_in_object(self, admin_page: Page, branch: str) -> None:
        # Navigate to an used profile
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("heading")).to_contain_text("Profile")
        admin_page.get_by_role("link", name="profile test tag").click()

        # Edit the profile
        admin_page.get_by_test_id("edit-button").click()
        admin_page.get_by_label("Description").fill("A profile for E2E test edited")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("DescriptionA profile for E2E test edited")).to_be_visible()

        # Verify the changes in an object using the edited profile
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        admin_page.get_by_role("link", name="tag with profile").click()
        expect(admin_page.get_by_role("heading", name="tag with profile")).to_be_visible()

        # Refresh profile is an async task
        deadline = Deadline("the edited profile description to propagate to the tag")
        while admin_page.get_by_text("DescriptionA profile for E2E test edited").is_hidden():
            deadline.tick()
            admin_page.reload()
            expect(admin_page.get_by_text("DescriptionA profile for E2E test")).to_be_visible()

    def test_edit_profile_of_tag_without_touching_other_fields(self, admin_page: Page, branch: str) -> None:
        # got to edit form of tag
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        admin_page.get_by_role("link", name="tag with profile").click()
        admin_page.get_by_test_id("edit-button").click()

        # remove profile from tag
        admin_page.get_by_text("profile test tag×").get_by_test_id("remove-option").click()
        expect(admin_page.get_by_label("Description")).to_be_empty()
        admin_page.get_by_role("button", name="Save").click()

        expect(admin_page.get_by_test_id("object-details").get_by_text("Description-")).to_be_visible()

    def test_delete_profile_and_reset_object_attribute(self, admin_page: Page, branch: str) -> None:
        # Navigate to CoreProfile page
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")

        # Delete the profile
        admin_page.get_by_test_id("actions-cell-profile test tag").click()
        admin_page.get_by_role("menuitem", name="Delete").click()
        expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            "Are you sure you want to remove profile test tag?"
        )
        admin_page.get_by_test_id("modal-delete-confirm").click()

        # Verify profile deletion
        expect(admin_page.get_by_text("Object profile test tag deleted")).to_be_visible()

        # Object attribute using profile value should be reset
        admin_page.goto(f"/objects/BuiltinTag?branch={branch}")
        admin_page.get_by_role("link", name="tag with profile").click()
        expect(admin_page.get_by_text("Description-", exact=True)).to_be_visible()
        admin_page.get_by_text("Description-").get_by_test_id("view-metadata-button").click()
        expect(admin_page.get_by_test_id("metadata-tooltip").get_by_text("Source-")).to_be_visible()
