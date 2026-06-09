"""Port of frontend/app/tests/e2e/profile/account-tokens.spec.ts.

Account tokens tab on the profile page: the unauthenticated redirect, and (as
admin) creating/deleting a token with no expiration date on the logged-in
account. Operates only on the admin's own account, so it needs no demo data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestProfileTokensNotAdmin:
    def test_should_not_access_profile_tokens(self, page: Page) -> None:
        page.goto("/profile?tab=tokens")
        expect(page.get_by_text("Open Proposed changes", exact=True)).to_be_visible()


class TestProfileTokensAdmin:
    def test_should_create_and_delete_account_without_expiration_date(self, admin_page: Page) -> None:
        # go to profile page and access tokens
        admin_page.goto("/")
        admin_page.get_by_test_id("authenticated-menu-trigger").click()
        admin_page.get_by_role("menuitem", name="Account settings").click()
        admin_page.get_by_text("Tokens").click()
        expect(admin_page.get_by_test_id("account-token-Created automatically")).to_be_visible()
        admin_page.get_by_role("button", name="Add account token").click()
        expect(admin_page.get_by_role("button", name="Save")).to_be_visible()
        save_screenshot_for_docs(admin_page, "profile_tokens")

        # create a new token
        admin_page.get_by_label("Name *").fill("test token")
        save_screenshot_for_docs(admin_page, "profile_tokens_create")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("For security reasons we cannot show it again.")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Confirm")).to_be_visible()
        save_screenshot_for_docs(admin_page, "profile_tokens_copy")
        admin_page.get_by_role("button", name="Confirm").click()
        expect(admin_page.get_by_role("button", name="Confirm")).not_to_be_visible()

        account_token_card = admin_page.get_by_test_id("account-token-test token")

        # verify the new token
        expect(account_token_card).to_contain_text("test token")
        expect(account_token_card).to_contain_text("This token has no expiration date")

        # delete the new token
        account_token_card.get_by_role("button", name="Delete token test token").click()
        admin_page.get_by_test_id("modal-delete-confirm").click()
        expect(admin_page.get_by_text("Are you sure you want to")).not_to_be_visible()
        expect(account_token_card).not_to_be_visible()
