"""Port of frontend/app/tests/e2e/profile/account-tokens.spec.ts.

Account tokens tab on the profile page: the unauthenticated redirect, and (as
admin) creating/deleting a token with no expiration date on the logged-in
account. Operates only on the admin's own account, so it needs no demo data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestProfileTokensNotAdmin:
    async def test_should_not_access_profile_tokens(self, page: Page) -> None:
        await page.goto("/profile?tab=tokens")
        await expect(page.get_by_text("Open Proposed changes", exact=True)).to_be_visible()


class TestProfileTokensAdmin:
    async def test_should_create_and_delete_account_without_expiration_date(self, admin_page: Page) -> None:
        # go to profile page and access tokens
        await admin_page.goto("/")
        await admin_page.get_by_test_id("authenticated-menu-trigger").click()
        await admin_page.get_by_role("menuitem", name="Account settings").click()
        await admin_page.get_by_text("Tokens").click()
        await expect(admin_page.get_by_test_id("account-token-Created automatically")).to_be_visible()
        await admin_page.get_by_role("button", name="Add account token").click()
        await expect(admin_page.get_by_role("button", name="Save")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "profile_tokens")

        # create a new token
        await admin_page.get_by_label("Name *").fill("test token")
        await save_screenshot_for_docs(admin_page, "profile_tokens_create")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("For security reasons we cannot show it again.")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Confirm")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "profile_tokens_copy")
        await admin_page.get_by_role("button", name="Confirm").click()
        await expect(admin_page.get_by_role("button", name="Confirm")).not_to_be_visible()

        account_token_card = admin_page.get_by_test_id("account-token-test token")

        # verify the new token
        await expect(account_token_card).to_contain_text("test token")
        await expect(account_token_card).to_contain_text("This token has no expiration date")

        # delete the new token
        await account_token_card.get_by_role("button", name="Delete token test token").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Are you sure you want to")).not_to_be_visible()
        await expect(account_token_card).not_to_be_visible()
