"""Port of frontend/app/tests/e2e/login.spec.ts.

Covers: SSO-enabled vs disabled login screens (config mocked via routing),
credential login, invalid-credentials error, redirect-to-initial-page after
login, logout, redirect-home when already logged in, and access-token refresh +
retry on 401.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from constants import ADMIN_CREDENTIALS
from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import ScenarioBranchesHandle
    from playwright.sync_api import Page, Route


def _disable_sso(page: Page) -> None:
    def handler(route: Route) -> None:
        response = route.fetch()
        body = response.json()
        body["sso"] = {"providers": [], "enabled": False}
        route.fulfill(json=body)

    page.route("**/api/config", handler)


def _enable_sso(page: Page) -> None:
    def handler(route: Route) -> None:
        response = route.fetch()
        body = response.json()
        body["sso"] = {
            "providers": [
                {
                    "name": "google",
                    "display_label": "Google",
                    "icon": "mdi:google",
                    "protocol": "oauth2",
                    "authorize_path": "/api/oauth2/google/authorize",
                    "token_path": "/api/oauth2/google/token",
                }
            ],
            "enabled": True,
        }
        route.fulfill(json=body)

    page.route("**/api/config", handler)


class TestLoginNotLoggedIn:
    def test_sso_enabled_shows_sso_and_credentials(self, page: Page) -> None:
        _enable_sso(page)
        page.goto("/login")

        # should display Google SSO button
        expect(page.get_by_role("link", name="Continue with Google")).to_be_visible()

        # should display username and password fields
        page.get_by_role("button", name="Log in with your credentials").click()
        expect(page.get_by_label("Username")).to_be_visible()
        expect(page.get_by_label("Password")).to_be_visible()

        # go back to log in with SSO
        page.get_by_role("button", name="Log in with SSO").click()
        expect(page.get_by_role("link", name="Continue with Google")).to_be_visible()

    def test_sso_disabled_logs_in_the_user(self, page: Page) -> None:
        _disable_sso(page)
        page.goto("/")

        page.get_by_role("link", name="Log in anonymous").click()

        expect(page.get_by_text("Log in to your account")).to_be_visible()
        page.get_by_label("Username").fill(ADMIN_CREDENTIALS["username"])
        page.get_by_label("Password").fill(ADMIN_CREDENTIALS["password"])
        page.get_by_role("button", name="Log in").click()

        expect(page.get_by_test_id("authenticated-menu-trigger")).to_be_visible()

    def test_sso_disabled_shows_error_on_failed_auth(self, page: Page) -> None:
        _disable_sso(page)
        page.goto("/")

        page.get_by_role("link", name="Log in anonymous").click()

        expect(page.get_by_text("Log in to your account")).to_be_visible()
        page.get_by_label("Username").fill("wrong username")
        page.get_by_label("Password").fill("wrong password")
        page.get_by_role("button", name="Log in").click()

        expect(page.locator("#alert-error-sign-in")).to_contain_text("Invalid username or password")

    def test_redirect_to_initial_page_after_login(
        self, page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        # The initial page targets the `atl1-delete-upstream` branch, hence the
        # data_scenario_branches dependency.
        _disable_sso(page)
        # Match JS toISOString(): a trailing Z, not +00:00 (whose + decodes to a
        # space in the query string, making the `at` timestamp invalid).
        date = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        initial_page = f"/objects/BuiltinTag?at={date}&branch=atl1-delete-upstream"
        page.goto(initial_page)

        page.get_by_role("link", name="Log in anonymous").click()

        expect(page.get_by_text("Log in to your account")).to_be_visible()
        page.get_by_label("Username").fill(ADMIN_CREDENTIALS["username"])
        page.get_by_label("Password").fill(ADMIN_CREDENTIALS["password"])
        page.get_by_role("button", name="Log in").click()

        expect(page.get_by_test_id("authenticated-menu-trigger")).to_be_visible()
        assert initial_page in page.url


class TestLoginLoggedIn:
    def test_logs_out_the_user(self, admin_page: Page) -> None:
        admin_page.goto("/")

        admin_page.get_by_test_id("authenticated-menu-trigger").click()
        admin_page.get_by_role("menuitem", name="Logout").click()

        expect(admin_page.get_by_role("link", name="Log in anonymous")).to_be_visible()

    def test_redirect_homepage_if_already_logged_in(self, admin_page: Page) -> None:
        admin_page.goto("/login")

        expect(admin_page.get_by_text("Open Proposed changes", exact=True)).to_be_visible()

    def test_refresh_access_token_and_retry(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        # Needs the seeded BuiltinTag "blue", loaded transitively by data_scenario_branches.
        block_request = {"value": True}  # force a 401 on the first BuiltinTag call

        def handler(route: Route) -> None:
            request_data = route.request.post_data_json
            if request_data and request_data.get("operationName") == "BuiltinTag" and block_request["value"]:
                block_request["value"] = False
                route.fulfill(
                    status=401,
                    json={
                        "data": None,
                        "errors": [{"message": "Expired Signature", "extensions": {"code": 401}}],
                    },
                )
            else:
                route.fallback()

        admin_page.route("**/graphql/main**", handler)
        admin_page.goto("/objects/BuiltinTag")

        expect(admin_page.get_by_role("link", name="blue")).to_be_visible()
