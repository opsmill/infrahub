"""Git repositories card on the branch details page: the import error band."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from playwright.async_api import Page


class TestBranchDetailsRepositoryImportError:
    async def test_import_error_band_links_to_the_task_page(
        self, admin_page: Page, broken_repository: Callable[..., Awaitable[tuple[str, str, str]]]
    ) -> None:
        # A branch without Git sync lists only read-only repositories, so its card would not show
        # the broken CoreRepository.
        branch, repository_name, task_id = await broken_repository(sync_with_git=True)

        await admin_page.goto(f"/branches/{quote(branch, safe='')}")

        repositories_card = admin_page.get_by_test_id("branch-repositories-card")
        await expect(repositories_card.get_by_role("row").filter(has_text=repository_name)).to_be_visible()

        band = repositories_card.get_by_test_id("repository-error-band").filter(has_text=repository_name)
        await expect(band).to_contain_text("import failed")
        await expect(band).to_contain_text("is missing a configuration file")

        await band.get_by_role("link", name="View task log").click()
        await expect(admin_page).to_have_url(re.compile(rf"/tasks/{re.escape(task_id)}"))
