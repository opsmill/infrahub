"""Port of frontend/app/tests/e2e/objects/object-dropdown-creation.spec.ts.

Create a related object inline from a relationship dropdown (a Tag from the
InfraDevice creation form), and assert a dropdown attribute (CoreWebhook) does
not expose the inline add-option button. A 500-response guard is registered on
every test. Operates on the demo dataset on a throwaway branch, hence the
infrastructure_data dependency.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from helpers import BranchAPI
    from playwright.sync_api import Page, Response


class TestObjectDropdownCreation:
    @pytest.fixture(autouse=True)
    def fail_on_500(self, admin_page: Page) -> None:
        def _handler(response: Response) -> None:
            if response.status == 500:
                assert response.url == "This URL responded with a 500 status"

        admin_page.on("response", _handler)

    @pytest.fixture
    def branch(
        self,
        branch_api: BranchAPI,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name()
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_should_open_the_creation_form_and_open_the_tag_option_creation_form(
        self, admin_page: Page, branch: str
    ) -> None:
        admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        # Open creation form
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("button", name="Start from scratch").click()

        # Open tags options
        admin_page.get_by_label("Tags").click()

        # Add new option
        admin_page.get_by_role("button", name="+ Add new Tag").click()

        # Assert form content is visible
        expect(admin_page.get_by_text("Create Tag")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Save")).to_be_visible()

        # Create a new tag
        admin_page.get_by_test_id("new-object-form").get_by_label("Name").fill("new-tag")
        admin_page.get_by_test_id("new-object-form").get_by_label("Description").fill("New tag description")

        # Submit
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Tag created")).to_be_visible()

        # Closes the form
        admin_page.get_by_role("button", name="Cancel").click()

    def test_should_not_be_able_to_create_a_new_option_for_dropdown(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/CoreWebhook?branch={branch}")
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Custom Webhook Core").click()
        admin_page.get_by_role("combobox", name="Branch Scope").click()
        expect(admin_page.get_by_test_id("add-option-button")).to_be_hidden()
