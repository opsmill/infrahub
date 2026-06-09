"""Port of frontend/app/tests/e2e/profile/profile.spec.ts.

Profile page (Account settings): the unauthenticated header state, and the
account details shown for the admin, read-write (Chloe O'Brian) and read-only
(Jack Bauer) accounts. Each test mirrors the source `beforeEach` 500-response
guard. The read-write / read-only cases use demo accounts, so they need the
`infrastructure_data` fixture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page, Response


def _install_500_guard(page: Page) -> list[str]:
    """Mirror the source `beforeEach`: collect any HTTP 500 responses."""
    server_errors: list[str] = []

    def _record_500(response: Response) -> None:
        if response.status == 500:
            server_errors.append(response.url)

    page.on("response", _record_500)
    return server_errors


class TestProfileNotLoggedIn:
    def test_should_see_login_and_no_user_avatar_on_header(self, page: Page) -> None:
        server_errors = _install_500_guard(page)

        page.goto("/")

        expect(page.get_by_test_id("unauthenticated-menu-trigger")).to_be_visible()
        expect(page.get_by_test_id("authenticated-menu-trigger")).to_be_hidden()

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"


class TestProfileAdmin:
    def test_should_access_the_profile_page(self, admin_page: Page) -> None:
        server_errors = _install_500_guard(admin_page)

        # go to profile page
        admin_page.goto("/")
        admin_page.get_by_test_id("authenticated-menu-trigger").click()
        admin_page.get_by_role("menuitem", name="Account settings").click()

        # display account details
        expect(admin_page.get_by_role("heading", name="Admin", exact=True)).to_be_visible()
        expect(admin_page.get_by_text("Nameadmin")).to_be_visible()
        expect(admin_page.get_by_text("LabelAdmin")).to_be_visible()

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"


class TestProfileReadWrite:
    def test_should_access_the_profile_page(self, read_write_page: Page, infrastructure_data: None) -> None:
        server_errors = _install_500_guard(read_write_page)

        # go to profile page
        read_write_page.goto("/")
        read_write_page.get_by_test_id("authenticated-menu-trigger").click()
        read_write_page.get_by_role("menuitem", name="Account settings").click()

        # display account details
        expect(read_write_page.get_by_role("heading", name="Chloe O'Brian", exact=True)).to_be_visible()
        expect(read_write_page.get_by_text("LabelChloe O'Brian")).to_be_visible()

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"


class TestProfileReadOnly:
    def test_should_access_the_profile_page(self, read_only_page: Page, infrastructure_data: None) -> None:
        server_errors = _install_500_guard(read_only_page)

        # go to profile page
        read_only_page.goto("/")
        read_only_page.get_by_test_id("authenticated-menu-trigger").click()
        read_only_page.get_by_role("menuitem", name="Account settings").click()

        # display account details
        expect(read_only_page.get_by_role("heading", name="Jack Bauer", exact=True)).to_be_visible()
        expect(read_only_page.get_by_text("LabelJack Bauer")).to_be_visible()

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"
