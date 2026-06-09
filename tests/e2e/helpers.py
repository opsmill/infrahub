"""Shared helpers for the pytest-playwright e2e suite.

Python ports of frontend/app/tests/utils.ts and
frontend/app/tests/e2e/utils/graphql.ts so the behaviour matches the legacy
TypeScript suite.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from constants import AUTHENTICATED_MENU_TRIGGER
from playwright.sync_api import expect

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


def generate_random_branch_name(prefix: str = "") -> str:
    """Port of generateRandomBranchName: a random suffix to avoid collisions."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


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
