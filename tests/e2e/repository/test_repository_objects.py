"""Port of frontend/app/tests/e2e/repository/repository-objects.spec.ts.

Repository creation + objects view (a serial flow): register a NEW Read-Only
CoreRepository through the UI pointing at the public GitHub demo-edge URL, view
its (empty) repository-derived objects, then exercise the repository detail
actions (check connectivity, import latest commit, reimport current commit).

This spec creates its own repository through the UI, but the first test also
asserts the `demo-edge` link is visible in the repository list, so the class
depends on demo_edge_repo explicitly (relying on another domain's session
fixture having run first would break standalone/per-domain runs). Registering
the repo and the "Check connectivity" / "Import latest commit" actions require
network egress to github.com.

Serial handling: the source `describe.configure({ mode: "serial" })` shares a
single branch created in beforeAll and deleted in afterAll (only used as
setup/teardown; the test bodies navigate on main). Both tests depend on the
SAME class-scoped `branch` fixture and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha). The suite
runs single-process.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

GIT_REPO_URL = "https://github.com/opsmill/infrahub-demo-edge.git"
REPO_NAME = "test repository"


@pytest.mark.usefixtures("demo_edge_repo")
class TestRepositoryCreationAndObjectsView:
    @pytest.fixture(scope="class")
    async def branch(self, infrahub_client: InfrahubClient) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("repository-branch")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_repository_and_access_objects_view(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto("/objects/CoreGenericRepository")
        await expect(admin_page.get_by_role("link", name="demo-edge")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Read-Only Repository Core").click()
        await admin_page.get_by_role("textbox", name="Repository location *").fill(GIT_REPO_URL)
        await admin_page.get_by_role("textbox", name="Name *").fill(REPO_NAME)
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_role("link", name=REPO_NAME)).to_be_visible()
        await admin_page.get_by_role("link", name=REPO_NAME).click()
        await admin_page.get_by_role("link").filter(has_not_text="Group").filter(has_text="Objects").click()
        await expect(admin_page.get_by_text("No objects found for this")).to_be_visible()

    async def test_check_repository_actions(self, admin_page: Page, branch: str) -> None:
        # access repository detailed page
        await admin_page.goto("/")
        await admin_page.get_by_role("button", name="Integrations").click()
        await admin_page.get_by_role("menuitem", name="Git Repositories").click()
        await expect(admin_page.get_by_role("heading", name="Git Repository")).to_be_visible()
        await admin_page.get_by_role("link", name=REPO_NAME).click()
        await expect(admin_page.get_by_role("heading", name=REPO_NAME)).to_be_visible()

        # trigger connectivity action
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Check connectivity").click()
        await expect(admin_page.get_by_role("heading", name="Check repository connectivity")).to_be_visible()
        await admin_page.get_by_role("button", name="Check now").click()
        await expect(admin_page.get_by_text("Successfully accessed")).to_be_visible()
        await admin_page.get_by_role("button", name="Done").click()

        # trigger latest commit action
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Import latest commit").click()
        await expect(admin_page.get_by_text("Import from remote started.")).to_be_visible()

        # trigger current commit from remote action
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Reimport current commit").click()
        await expect(admin_page.get_by_text("Import of current commit")).to_be_visible()
