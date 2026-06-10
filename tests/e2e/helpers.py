"""Shared helpers for the pytest-playwright e2e suite.

Python ports of frontend/app/tests/utils.ts and
frontend/app/tests/e2e/utils/graphql.ts so the behaviour matches the legacy
TypeScript suite.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from constants import AUTHENTICATED_MENU_TRIGGER
from playwright.sync_api import expect

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Locator, Page

# docs/docs/media relative to the repo root (helpers.py is tests/e2e/helpers.py).
_DOCS_MEDIA_DIR = Path(__file__).resolve().parents[2] / "docs" / "docs" / "media"

_RESPONSE_DELAY = int(os.environ.get("INFRAHUB_TESTING_RESPONSE_DELAY") or "0")


class Deadline:
    """Bound a reload-until-condition poll loop.

    The legacy TS suite relied on Playwright's per-test timeout (3 min in CI) to
    bound its ``while (...) reload()`` loops; this suite deliberately runs without
    a per-test timeout, so an async effect that never materializes (artifact
    generation, activity-log propagation, profile refresh) would otherwise spin
    until the CI job ceiling and take the whole run down with it. Call ``tick()``
    on every iteration: it pauses briefly (the loop conditions are
    immediate-return locator checks) and fails the test once the deadline
    expires. The budget doubles in response-delay mode, mirroring the widened
    ``expect`` timeout.
    """

    def __init__(self, waiting_for: str, timeout: float = 180.0) -> None:
        self._waiting_for = waiting_for
        self._timeout = timeout * (2 if _RESPONSE_DELAY else 1)
        self._expires_at = time.monotonic() + self._timeout

    def tick(self, pause: float = 0.5) -> None:
        if time.monotonic() >= self._expires_at:
            raise AssertionError(f"Timed out after {self._timeout:.0f}s waiting for {self._waiting_for}")
        time.sleep(pause)


def generate_random_branch_name(prefix: str = "") -> str:
    """Port of generateRandomBranchName: a random suffix to avoid collisions."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def save_screenshot_for_docs(page: Page, filename: str) -> None:
    """Port of saveScreenshotForDocs: capture a docs screenshot.

    No-op unless UPDATE_DOCS_SCREENSHOTS is set (matching the TS helper).
    """
    if not os.environ.get("UPDATE_DOCS_SCREENSHOTS"):
        return
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(_DOCS_MEDIA_DIR / f"{filename}.png"), animations="disabled")


def get_data_table_row(page: Page, name: str) -> Locator:
    """Port of getDataTableRow: the data-table row containing a link with the exact name."""
    return page.get_by_test_id("data-table-row").filter(has=page.get_by_role("link", name=name, exact=True))


def login(page: Page, username: str, password: str) -> None:
    """Port of the auth.setup.ts UI login flow.

    Navigates to /login, optionally opens the credentials form (SSO-enabled UI),
    fills the credentials, submits, and waits for the authenticated user menu.
    """
    page.goto("/login")
    expect(page.get_by_text("Log in to your account")).to_be_visible()

    # In SSO-enabled deployments the credentials form is hidden behind this button.
    credentials_button = page.get_by_role("button", name="Log in with your credentials")
    if credentials_button.is_visible():
        credentials_button.click()

    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in", exact=True).click()

    expect(page.get_by_test_id(AUTHENTICATED_MENU_TRIGGER)).to_be_visible()


class BranchAPI:
    """Port of tests/e2e/utils/graphql.ts branch helpers.

    Mirrors createBranchAPI / mergeBranchAPI / deleteBranchAPI.
    The legacy helper POSTed raw GraphQL mutations to ``${INFRAHUB_ADDRESS}/graphql``
    with the admin ``X-INFRAHUB-KEY`` token. Here we drive the equivalent
    mutations through the SDK sync client, which authenticates with the same
    admin credentials. Used by specs to create/merge/delete throwaway branches
    via the API (instead of the UI) in setup/teardown.
    """

    def __init__(self, client: InfrahubClientSync) -> None:
        self._client = client

    def create(self, name: str, *, sync_with_git: bool = False) -> None:
        self._client.branch.create(branch_name=name, sync_with_git=sync_with_git)

    def merge(self, name: str) -> bool:
        return self._client.branch.merge(branch_name=name)

    def delete(self, name: str) -> bool:
        return self._client.branch.delete(branch_name=name)
