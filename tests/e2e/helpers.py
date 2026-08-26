"""Shared helpers for the pytest-playwright e2e suite (fully async).

Python ports of frontend/app/tests/utils.ts and
frontend/app/tests/e2e/utils/graphql.ts so the behaviour matches the legacy
TypeScript suite. Everything runs on pytest-asyncio's session event loop,
shared with pytest-playwright-asyncio's browser fixtures.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from constants import AUTHENTICATED_MENU_TRIGGER
from playwright.async_api import expect

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Locator, Page

# docs/docs/media relative to the repo root (helpers.py is tests/e2e/helpers.py).
_DOCS_MEDIA_DIR = Path(__file__).resolve().parents[2] / "docs" / "docs" / "media"

_RESPONSE_DELAY = int(os.environ.get("INFRAHUB_TESTING_RESPONSE_DELAY") or "0")


class Deadline:
    """Bound a reload-until-condition poll loop.

    The legacy TS suite relied on Playwright's per-test timeout (3 min in CI) to
    bound its ``while (...) reload()`` loops; this suite deliberately runs without
    a per-test timeout, so an async effect that never materializes (artifact
    generation, activity-log propagation, profile refresh) would otherwise spin
    until the CI job ceiling and take the whole run down with it. Await ``tick()``
    on every iteration: it pauses briefly (the loop conditions are
    immediate-return locator checks) and fails the test once the deadline
    expires. The budget doubles in response-delay mode, mirroring the widened
    ``expect`` timeout.
    """

    def __init__(self, waiting_for: str, timeout: float = 180.0) -> None:
        self._waiting_for = waiting_for
        self._timeout = timeout * (2 if _RESPONSE_DELAY else 1)
        self._expires_at = time.monotonic() + self._timeout

    async def tick(self, pause: float = 0.5) -> None:
        if time.monotonic() >= self._expires_at:
            raise AssertionError(f"Timed out after {self._timeout:.0f}s waiting for {self._waiting_for}")
        await asyncio.sleep(pause)


def generate_random_branch_name(prefix: str = "") -> str:
    """Port of generateRandomBranchName: a random suffix to avoid collisions.

    The suffix must stay hexadecimal. Playwright's ``name`` option substring-matches, and the
    branch selector renders the current branch name on every page, so a suffix that spells a word
    the suites locate by ("save", "name", "path", "main", ...) makes that locator match two
    elements and the test dies with a strict-mode violation. None of those names are spellable in
    hex; a wider alphabet reintroduces the flake at roughly one branch in twelve thousand.
    """
    return f"{prefix}{uuid.uuid4().hex[:12]}"


async def save_screenshot_for_docs(page: Page, filename: str) -> None:
    """Port of saveScreenshotForDocs: capture a docs screenshot.

    No-op unless UPDATE_DOCS_SCREENSHOTS is set (matching the TS helper).
    """
    if not os.environ.get("UPDATE_DOCS_SCREENSHOTS"):
        return
    # The published documentation is written against the light theme, while a development stack now
    # starts dark. Without pinning it here, a regeneration run would quietly turn every screenshot
    # in the docs dark.
    await page.evaluate(
        """() => {
            localStorage.setItem("infrahub.theme.choice", "light");
            document.documentElement.classList.remove("dark");
        }"""
    )
    # The flip triggers observer-driven re-renders (diagrams and the sandbox rebuild whole
    # subtrees), so settle the network and let two frames paint before capturing.
    await page.wait_for_load_state("networkidle")
    await page.evaluate("() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    await page.screenshot(path=str(_DOCS_MEDIA_DIR / f"{filename}.png"), animations="disabled")


def get_data_table_row(page: Page, name: str) -> Locator:
    """Port of getDataTableRow: the data-table row containing a link with the exact name."""
    return page.get_by_test_id("data-table-row").filter(has=page.get_by_role("link", name=name, exact=True))


async def select_pool(page: Page, pool_name: str) -> None:
    """Open a from-pool field's pool picker and select the pool by name.

    The "open the resource-pool dropdown, then click the named pool" pair is
    identical across every from-pool allocation flow (IPAM create, object
    create / relationship / bulk-edit, object templates), so it lives here once.
    Callers keep their own surrounding navigation, field fills and assertions.
    """
    await page.get_by_test_id("select-open-pool-option-button").click()
    await page.get_by_role("option", name=pool_name).click()


async def login(page: Page, username: str, password: str) -> None:
    """Port of the auth.setup.ts UI login flow.

    Navigates to /login, optionally opens the credentials form (SSO-enabled UI),
    fills the credentials, submits, and waits for the authenticated user menu.
    """
    await page.goto("/login")
    await expect(page.get_by_text("Log in to your account")).to_be_visible()

    # In SSO-enabled deployments the credentials form is hidden behind this button.
    credentials_button = page.get_by_role("button", name="Log in with your credentials")
    if await credentials_button.is_visible():
        await credentials_button.click()

    await page.get_by_label("Username").fill(username)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Log in", exact=True).click()

    await expect(page.get_by_test_id(AUTHENTICATED_MENU_TRIGGER)).to_be_visible()


async def select_combobox_option(page: Page, label: str, option: str) -> None:
    """Open a Combobox by its accessible name and pick an option by its exact label.

    The preference forms use a searchable Combobox — a button trigger (its
    accessible name is ``label``) that opens a dialog holding a searchbox and a
    listbox. Typing into the search narrows the list, which the virtualized
    timezone picker needs (only rendered options are in the DOM) and the short
    date-format list tolerates. The option is then clicked by its exact label, so
    a value that is a prefix of another (``yyyy-MM-dd HH:mm`` vs
    ``yyyy-MM-dd HH:mm:ss``) still resolves unambiguously.
    """
    await page.get_by_role("button", name=label, exact=True).click()
    dialog = page.get_by_role("dialog", name=label)
    await dialog.get_by_role("searchbox").fill(option)
    await dialog.get_by_role("option", name=option, exact=True).click()


class BranchAPI:
    """Port of tests/e2e/utils/graphql.ts branch helpers.

    Mirrors createBranchAPI / mergeBranchAPI / deleteBranchAPI.
    The legacy helper POSTed raw GraphQL mutations to ``${INFRAHUB_ADDRESS}/graphql``
    with the admin ``X-INFRAHUB-KEY`` token. Here we drive the equivalent
    mutations through the async SDK client, which authenticates with the same
    admin credentials. Used by specs to create/merge/delete throwaway branches
    via the API (instead of the UI) in setup/teardown.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def create(self, name: str, *, sync_with_git: bool = False) -> None:
        await self._client.branch.create(branch_name=name, sync_with_git=sync_with_git)

    async def merge(self, name: str) -> bool:
        return await self._client.branch.merge(branch_name=name)

    async def delete(self, name: str) -> bool:
        return await self._client.branch.delete(branch_name=name)
