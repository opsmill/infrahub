"""Unit tests for the Prefect install flows.

These tests mock the InfrahubRepository + MarketplaceClient boundaries so the
flow logic can run without git, a worker, or a live upstream. They target the
three highest-risk code paths: rollback on push failure, malformed collection
bundle rejection, and non-dict YAML rejection in the direct flow.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003  -- used as a runtime fixture type annotation for pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub import lock
from infrahub.marketplace.models import (
    MarketplaceInstallDirectPayload,
    MarketplaceInstallItem,
    MarketplaceInstallPayload,
)
from infrahub.marketplace.tasks import (
    MarketplaceInstallError,
    _commit_and_push,
    _fetch_one_item,
    install_marketplace_schemas_direct,
)


@pytest.fixture(autouse=True)
def _init_local_lock() -> None:
    """The install flow wraps commit-and-push in a lock; use the local driver
    in tests so we don't need a running Redis."""
    lock.initialize_lock(local_only=True)


def _make_repo_payload(**overrides: Any) -> MarketplaceInstallPayload:
    defaults: dict[str, Any] = {
        "marketplace_url": "https://example.com",
        "initiator_account_id": "acc-1",
        "initiator_username": "alice",
        "repository_id": "repo-1",
        "branch_name": "main",
        "items": [MarketplaceInstallItem(kind="schema", namespace="ns", name="foo", semver=None)],
    }
    defaults.update(overrides)
    return MarketplaceInstallPayload(**defaults)


def _make_direct_payload(**overrides: Any) -> MarketplaceInstallDirectPayload:
    defaults: dict[str, Any] = {
        "marketplace_url": "https://example.com",
        "initiator_account_id": "acc-1",
        "initiator_username": "alice",
        "branch_name": "main",
        "items": [MarketplaceInstallItem(kind="schema", namespace="ns", name="foo", semver=None)],
    }
    defaults.update(overrides)
    return MarketplaceInstallDirectPayload(**defaults)


@pytest.mark.asyncio
async def test_commit_and_push_rolls_back_on_push_failure(tmp_path: Path) -> None:
    """If repo.push returns False, the worktree must be reset to the pre-commit HEAD."""
    payload = _make_repo_payload()
    schema_files = [("foo.yml", "type: CoreNode\n")]

    git_repo = MagicMock()
    git_repo.head.commit.hexsha = "deadbeef"
    git_repo.index.commit.return_value = "cafebabe"

    worktree = MagicMock(directory=str(tmp_path))
    repo = MagicMock()
    repo.create_branch_in_git = AsyncMock()
    repo.push = AsyncMock(return_value=False)  # simulate push failure
    repo.get_git_repo_worktree.return_value = git_repo
    repo.get_worktree.return_value = worktree

    sdk = MagicMock()
    sdk.get = AsyncMock(return_value=MagicMock(name=MagicMock(value="repo-name")))

    with (
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
        patch("infrahub.git.repository.InfrahubRepository.init", AsyncMock(return_value=repo)),
        pytest.raises(MarketplaceInstallError, match="no remote origin"),
    ):
        await _commit_and_push.fn(payload=payload, schema_files=schema_files)

    # Rollback: head.reset must have been called with the pre-commit ref
    git_repo.head.reset.assert_called_once_with(commit="deadbeef", index=True, working_tree=True)


@pytest.mark.asyncio
async def test_commit_and_push_rolls_back_on_commit_failure(tmp_path: Path) -> None:
    """If index.commit itself raises, rollback still fires and the original exception propagates."""
    payload = _make_repo_payload()
    schema_files = [("foo.yml", "type: CoreNode\n")]

    git_repo = MagicMock()
    git_repo.head.commit.hexsha = "deadbeef"
    git_repo.index.commit.side_effect = RuntimeError("commit exploded")

    worktree = MagicMock(directory=str(tmp_path))
    repo = MagicMock()
    repo.create_branch_in_git = AsyncMock()
    repo.push = AsyncMock(return_value=True)
    repo.get_git_repo_worktree.return_value = git_repo
    repo.get_worktree.return_value = worktree

    sdk = MagicMock()
    sdk.get = AsyncMock(return_value=MagicMock(name=MagicMock(value="repo-name")))

    with (
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
        patch("infrahub.git.repository.InfrahubRepository.init", AsyncMock(return_value=repo)),
        pytest.raises(RuntimeError, match="commit exploded"),
    ):
        await _commit_and_push.fn(payload=payload, schema_files=schema_files)

    git_repo.head.reset.assert_called_once_with(commit="deadbeef", index=True, working_tree=True)
    repo.push.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_and_push_uses_initiator_as_author(tmp_path: Path) -> None:
    """Commit author must be the initiator, not the worker's default git identity."""
    payload = _make_repo_payload(initiator_username="bob", initiator_account_id="acc-42")
    schema_files = [("foo.yml", "type: CoreNode\n")]

    git_repo = MagicMock()
    git_repo.head.commit.hexsha = "deadbeef"
    git_repo.index.commit.return_value = "cafebabe"

    worktree = MagicMock(directory=str(tmp_path))
    repo = MagicMock()
    repo.create_branch_in_git = AsyncMock()
    repo.push = AsyncMock(return_value=True)
    repo.get_git_repo_worktree.return_value = git_repo
    repo.get_worktree.return_value = worktree

    sdk = MagicMock()
    sdk.get = AsyncMock(return_value=MagicMock(name=MagicMock(value="repo-name")))

    with (
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
        patch("infrahub.git.repository.InfrahubRepository.init", AsyncMock(return_value=repo)),
    ):
        await _commit_and_push.fn(payload=payload, schema_files=schema_files)

    _args, kwargs = git_repo.index.commit.call_args
    actor = kwargs["author"]
    assert actor.name == "bob"
    assert actor.email == "acc-42@infrahub.local"
    # Committer should equal author so `git log --author=bob` surfaces the install.
    assert kwargs["committer"] is actor


@pytest.mark.asyncio
async def test_fetch_one_item_rejects_malformed_collection_bundle() -> None:
    """A collection bundle whose 'schemas' is a non-list must raise."""
    client = MagicMock()
    client.fetch_collection_bundle = AsyncMock(return_value={"schemas": "not-a-list"})
    item = MarketplaceInstallItem(kind="collection", namespace="ns", name="bundle", semver=None)

    with pytest.raises(MarketplaceInstallError, match="malformed collection bundle"):
        await _fetch_one_item(client=client, item=item)


@pytest.mark.asyncio
async def test_fetch_one_item_skips_malformed_schema_entries() -> None:
    """Individual entries missing name/content must be silently skipped, not exploded."""
    client = MagicMock()
    client.fetch_collection_bundle = AsyncMock(
        return_value={
            "schemas": [
                {"name": "good", "content": "yaml: 1\n"},
                {"name": "missing-content"},  # skipped
                "not-a-dict",  # skipped
                {"name": "good2", "content": "yaml: 2\n"},
            ]
        }
    )
    item = MarketplaceInstallItem(kind="collection", namespace="ns", name="bundle", semver=None)
    result = await _fetch_one_item(client=client, item=item)
    assert {path for path, _ in result} == {"bundle/good.yml", "bundle/good2.yml"}


@pytest.mark.asyncio
async def test_direct_install_rejects_non_dict_yaml() -> None:
    """A YAML body that doesn't parse to a mapping must raise before any schema.load call."""
    payload = _make_direct_payload()

    async def _fake_fetch_all(*, marketplace_url: str, items: list[MarketplaceInstallItem]) -> list[tuple[str, str]]:
        # valid YAML, but a list, not a mapping
        return [("foo.yml", "- not\n- a\n- mapping\n")]

    sdk = MagicMock()
    sdk.schema.load = AsyncMock()

    with (
        patch("infrahub.marketplace.tasks._fetch_all_items", _fake_fetch_all),
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
        pytest.raises(MarketplaceInstallError, match="did not parse to a schema document"),
    ):
        await install_marketplace_schemas_direct.fn(payload=payload)

    sdk.schema.load.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_install_rejects_invalid_yaml() -> None:
    """Invalid YAML must surface a MarketplaceInstallError, not a raw YAMLError."""
    payload = _make_direct_payload()

    async def _fake_fetch_all(*, marketplace_url: str, items: list[MarketplaceInstallItem]) -> list[tuple[str, str]]:
        return [("foo.yml", "key: [unclosed\n")]

    sdk = MagicMock()
    sdk.schema.load = AsyncMock()

    with (
        patch("infrahub.marketplace.tasks._fetch_all_items", _fake_fetch_all),
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
        pytest.raises(MarketplaceInstallError, match="invalid YAML"),
    ):
        await install_marketplace_schemas_direct.fn(payload=payload)


@pytest.mark.asyncio
async def test_direct_install_no_items_returns_zero_applied() -> None:
    """If fetch returns nothing, we short-circuit without calling schema.load."""
    payload = _make_direct_payload()

    async def _empty_fetch(*, marketplace_url: str, items: list[MarketplaceInstallItem]) -> list[tuple[str, str]]:
        return []

    sdk = MagicMock()
    sdk.schema.load = AsyncMock()

    with (
        patch("infrahub.marketplace.tasks._fetch_all_items", _empty_fetch),
        patch("infrahub.marketplace.tasks.get_client", return_value=sdk),
    ):
        result = await install_marketplace_schemas_direct.fn(payload=payload)

    assert result == {"applied": 0}
    sdk.schema.load.assert_not_awaited()
