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

BAND_TIMEOUT_MS = 30_000


class TestBranchDetailsRepositoryImportError:
    async def test_import_error_band_links_to_the_task_page(
        self, admin_page: Page, broken_repository: Callable[..., Awaitable[tuple[str, str, str]]]
    ) -> None:
        # A branch without Git sync lists only read-only repositories, so its card would not show
        # the broken CoreRepository.
        branch, repository_name, task_id = await broken_repository(sync_with_git=True)

        await admin_page.goto(f"/branches/{quote(branch, safe='')}")

        # The table is paged and ordered by name on the server, so the repository's row may sit on
        # another page; its band comes from a separate failing-repositories query and is always shown.
        repositories_card = admin_page.get_by_test_id("branch-repositories-card")
        bands = repositories_card.get_by_test_id("repository-error-band")
        await expect(bands.first).to_be_visible(timeout=BAND_TIMEOUT_MS)
        # Only the first three bands show until "Show all"; other tests may leave failing repositories.
        show_all = repositories_card.get_by_role("button", name="Show all")
        if await show_all.is_visible():
            await show_all.click()

        band = bands.filter(has_text=repository_name)
        await expect(band).to_be_visible(timeout=BAND_TIMEOUT_MS)
        await expect(band).to_contain_text("import failed")
        await expect(band).to_contain_text("is missing a configuration file")

        await band.get_by_role("link", name="View task log").click()
        await expect(admin_page).to_have_url(re.compile(rf"/tasks/{re.escape(task_id)}"))
