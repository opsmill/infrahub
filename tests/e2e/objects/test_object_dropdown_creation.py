"""Port of frontend/app/tests/e2e/objects/object-dropdown-creation.spec.ts.

Create a related object inline from a relationship dropdown (a Tag from the
InfraDevice creation form), and assert a dropdown attribute (CoreWebhook) does
not expose the inline add-option button. A 500-response guard is registered on
every test. The device/webhook forms need only the schema (the test creates its
own tag inline), hence the schema_base dependency on the throwaway branch.
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

    from helpers import BranchAPI
    from playwright.async_api import Page, Response


class TestObjectDropdownCreation:
    @pytest.fixture(autouse=True)
    async def fail_on_500(self, admin_page: Page) -> AsyncGenerator[None, None]:
        # Collect-then-assert: Playwright swallows exceptions raised inside a
        # response handler, so an inline assert there can never fail the test
        # (the TS source had the same flaw). The fixture must be async — even
        # the .on() registration goes through the playwright connection, which
        # requires the running session loop. The handler itself stays sync.
        server_errors: list[str] = []

        def _handler(response: Response) -> None:
            if response.status == 500:
                server_errors.append(response.url)

        admin_page.on("response", _handler)
        yield
        assert not server_errors, f"Unexpected 500 responses: {server_errors}"

    @pytest.fixture
    async def branch(
        self,
        branch_api: BranchAPI,
        schema_base: None,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name()
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_open_the_creation_form_and_open_the_tag_option_creation_form(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        # Open creation form
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("button", name="Start from scratch").click()

        # Open tags options
        await admin_page.get_by_label("Tags").click()

        # Add new option
        await admin_page.get_by_role("button", name="+ Add new Tag").click()

        # Assert form content is visible
        await expect(admin_page.get_by_text("Create Tag")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Save")).to_be_visible()

        # Create a new tag
        await admin_page.get_by_test_id("new-object-form").get_by_label("Name").fill("new-tag")
        await admin_page.get_by_test_id("new-object-form").get_by_label("Description").fill("New tag description")

        # Submit
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Tag created")).to_be_visible()

        # Closes the form
        await admin_page.get_by_role("button", name="Cancel").click()

    async def test_should_not_be_able_to_create_a_new_option_for_dropdown(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/CoreWebhook?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Custom Webhook Core").click()
        await admin_page.get_by_role("combobox", name="Branch Scope").click()
        await expect(admin_page.get_by_test_id("add-option-button")).to_be_hidden()
