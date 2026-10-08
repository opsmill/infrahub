"""The "Push to remote" section of a repository whose remote refuses the push of a merge.

Each test adds a repository of its own from a Git directory that the containers mount, with a
pre-receive hook that refuses every push to main. A branch of that repository changes a file and is
merged, so the merge waits to be pushed. The section is viewed from another branch, because it
always shows the state of the default branch. Needs no demo dataset.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from infrahub_sdk.testing.repository import GitRepo
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Locator, Page

REPOSITORY_FIXTURE = Path(__file__).resolve().parents[3] / "backend/tests/fixtures/repos/conflict-01/initial__main"

REJECT_MAIN_HOOK = """#!/bin/sh
while read old new ref; do
    if [ "$ref" = "refs/heads/main" ]; then
        echo "branch main is protected" >&2
        exit 1
    fi
done
exit 0
"""

DELIVERY_STATUS_QUERY = """
query DeliveryStatus($id: ID!) {
    CoreRepository(ids: [$id]) {
        edges { node { delivery_status { value } } }
    }
}
"""

# The Git configuration of the test machine, such as commit signing, must not change the commits of the test.
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "e2e",
    "GIT_AUTHOR_EMAIL": "e2e@example.com",
    "GIT_COMMITTER_NAME": "e2e",
    "GIT_COMMITTER_EMAIL": "e2e@example.com",
}


@dataclass(frozen=True)
class RefusedDelivery:
    repository_id: str
    branch_name: str
    view_branch: str
    remote: Path
    hook: Path
    trunk_commit: str
    branch_commit: str

    @property
    def url(self) -> str:
        return f"/objects/CoreRepository/{self.repository_id}?branch={self.view_branch}"


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _detail_row(page: Page, label: str) -> Locator:
    return page.locator("dl").filter(has=page.get_by_text(label, exact=True))


async def _wait_for_delivery_status(client: InfrahubClient, repository_id: str, status: str) -> None:
    deadline = Deadline(f"the push state '{status}' of the repository")
    while True:
        data = await client.execute_graphql(query=DELIVERY_STATUS_QUERY, variables={"id": repository_id})
        if (data["CoreRepository"]["edges"][0]["node"]["delivery_status"]["value"] or "none") == status:
            return
        await deadline.tick(pause=2)


class TestRepositoryDelivery:
    @pytest.fixture
    async def refused_delivery(
        self,
        infrahub_client: InfrahubClient,
        infrahub_compose_dir: Path,
        infrahub_provisioned_externally: bool,
        branch_api: BranchAPI,
        monkeypatch: pytest.MonkeyPatch,
    ) -> AsyncGenerator[RefusedDelivery, None]:
        if infrahub_provisioned_externally:
            pytest.skip("The remote of the repository must be a directory that the containers mount")
        for name, value in GIT_ENV.items():
            monkeypatch.setenv(name, value)

        repository_name = generate_random_branch_name("delivery-repo-")
        branch_name = generate_random_branch_name("delivery-")
        view_branch = generate_random_branch_name("delivery-view-")
        remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        git_repo = GitRepo(name=repository_name, src_directory=REPOSITORY_FIXTURE, dst_directory=remote_dir)
        remote = remote_dir / repository_name

        # The remote has main checked out, and Git refuses a push to a checked-out branch by default.
        _git(remote, "config", "receive.denyCurrentBranch", "ignore")
        # The branch exists before the repository is added, so the first synchronization imports it.
        _git(remote, "checkout", "-q", "-b", branch_name)
        (remote / "README.md").write_text(f"# Changed on {branch_name}\n", encoding="utf-8")
        _git(remote, "commit", "-q", "-am", f"Change the README on {branch_name}")
        _git(remote, "checkout", "-q", "main")
        trunk_commit = _git(remote, "rev-parse", "main")
        branch_commit = _git(remote, "rev-parse", branch_name)
        hook = remote / ".git" / "hooks" / "pre-receive"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(REJECT_MAIN_HOOK, encoding="utf-8")
        hook.chmod(0o755)

        await git_repo.add_to_infrahub(infrahub_client)
        repository = await infrahub_client.get(kind="CoreRepository", name__value=repository_name)
        deadline = Deadline(f"the import of the branch {branch_name}")
        while branch_name not in await infrahub_client.branch.all():
            await deadline.tick(pause=2)
        while (
            await infrahub_client.get(kind="CoreRepository", id=repository.id, branch=branch_name)
        ).commit.value != branch_commit:
            await deadline.tick(pause=2)

        await branch_api.create(view_branch)
        await branch_api.merge(branch_name)
        await _wait_for_delivery_status(infrahub_client, repository.id, "action-required")

        yield RefusedDelivery(
            repository_id=repository.id,
            branch_name=branch_name,
            view_branch=view_branch,
            remote=remote,
            hook=hook,
            trunk_commit=trunk_commit,
            branch_commit=branch_commit,
        )

        for name in (view_branch, branch_name):
            with contextlib.suppress(Exception):
                await branch_api.delete(name)
        with contextlib.suppress(Exception):
            await repository.delete()

    async def test_retry_pushes_the_merge_once_the_remote_accepts_it(
        self, admin_page: Page, infrahub_client: InfrahubClient, refused_delivery: RefusedDelivery
    ) -> None:
        await admin_page.goto(refused_delivery.url)
        await expect(admin_page.get_by_text("Action required", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Push refused by the remote", exact=True)).to_be_visible()
        await expect(_detail_row(admin_page, "Message from the remote")).to_contain_text("branch main is protected")
        pending_merges = _detail_row(admin_page, "Pending merges").get_by_role("listitem")
        await expect(pending_merges).to_have_count(1)
        await expect(pending_merges).to_contain_text(refused_delivery.branch_name)

        refused_delivery.hook.unlink()
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Retry push").click()
        await expect(admin_page.get_by_text("Retry of the pending pushes started.")).to_be_visible()

        await _wait_for_delivery_status(infrahub_client, refused_delivery.repository_id, "none")
        await admin_page.reload()
        await expect(admin_page.get_by_text("Nothing pending", exact=True)).to_be_visible()
        _git(refused_delivery.remote, "merge-base", "--is-ancestor", refused_delivery.branch_commit, "main")

    async def test_abandon_drops_the_merge_and_advises_a_reimport(
        self, admin_page: Page, infrahub_client: InfrahubClient, refused_delivery: RefusedDelivery
    ) -> None:
        await admin_page.goto(refused_delivery.url)
        await expect(admin_page.get_by_text("Action required", exact=True)).to_be_visible()

        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Abandon pending push").click()
        modal = admin_page.get_by_role("dialog")
        await expect(modal.get_by_role("listitem")).to_have_count(1)
        await expect(modal.get_by_role("listitem")).to_contain_text(refused_delivery.branch_name)
        await modal.get_by_role("button", name="Abandon", exact=True).click()
        await expect(admin_page.get_by_text("Abandonment of the pending pushes started.")).to_be_visible()

        await _wait_for_delivery_status(infrahub_client, refused_delivery.repository_id, "none")
        await admin_page.reload()
        await expect(admin_page.get_by_text("Nothing pending", exact=True)).to_be_visible()
        await expect(_detail_row(admin_page, "Last abandonment")).to_be_visible()
        await expect(_detail_row(admin_page, "Abandoned by")).to_contain_text("admin")
        await expect(_detail_row(admin_page, "Abandoned merges")).to_contain_text(refused_delivery.branch_name)
        await expect(_detail_row(admin_page, "Recorded commit")).to_contain_text(refused_delivery.trunk_commit[:7])
        await expect(
            admin_page.get_by_text("The default branch can hold repository objects that the recorded commit lacks.")
        ).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Reimport current commit")).to_be_visible()
