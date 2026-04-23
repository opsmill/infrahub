"""Prefect workflow: download selected Marketplace items and commit them to a writable repo."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

import yaml

from infrahub.marketplace.client import (
    MarketplaceClient,
    MarketplaceNotFoundError,
    MarketplaceTimeoutError,
    MarketplaceUnreachableError,
    make_marketplace_client,
)
from infrahub.marketplace.models import (
    MarketplaceInstallDirectPayload,
    MarketplaceInstallItem,
    MarketplaceInstallPayload,
)
from infrahub.workers.dependencies import get_client

if TYPE_CHECKING:
    pass


class MarketplaceInstallError(RuntimeError):
    """Raised when install fails; repo is left unchanged on remote."""


@flow(
    name="marketplace-schema-install",
    flow_run_name="install-{payload.repository_id}",
)
async def install_marketplace_schemas(payload: MarketplaceInstallPayload) -> dict:
    """Download selected Marketplace items and commit them to a Git repo.

    Rollback invariant (FR-020 / SC-005): on any failure before `push()` returns,
    the target repository's remote state is unchanged. The local worktree is
    ephemeral per-branch; GitPython's `index.commit` only affects the local
    clone until `push()` actually transmits it.
    """
    log = get_run_logger()

    schema_files = await _fetch_all_items(marketplace_url=payload.marketplace_url, items=payload.items)
    if not schema_files:
        log.warning("marketplace install: no schema files to install")
        return {"commit": None, "files_written": 0}

    commit_sha = await _commit_and_push(payload=payload, schema_files=schema_files)
    return {"commit": commit_sha, "files_written": len(schema_files)}


@flow(
    name="marketplace-schema-install-direct",
    flow_run_name="install-direct-{payload.branch_name}",
)
async def install_marketplace_schemas_direct(payload: MarketplaceInstallDirectPayload) -> dict:
    """Download selected Marketplace items and apply them directly to Infrahub.

    Uses the SDK's ``schema.load`` (POST /api/schema/load) -- no Git repository
    is touched. The target branch must already exist. On any failure during
    fetching or parsing the schemas, the Infrahub schema is unchanged; on
    partial failures during apply, Infrahub's schema-load endpoint is itself
    transactional per request (either all schemas in the payload apply or none
    do -- see backend/infrahub/api/schema.py).
    """
    log = get_run_logger()

    schema_files = await _fetch_all_items(marketplace_url=payload.marketplace_url, items=payload.items)
    if not schema_files:
        log.warning("marketplace direct install: no schema files to apply")
        return {"applied": 0}

    parsed: list[dict] = []
    for path, content in schema_files:
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise MarketplaceInstallError(f"invalid YAML in marketplace file {path}: {exc}") from exc
        if not isinstance(doc, dict):
            raise MarketplaceInstallError(f"marketplace file {path} did not parse to a schema document")
        parsed.append(doc)

    sdk = get_client()
    await sdk.schema.load(schemas=parsed, branch=payload.branch_name)
    log.info("applied %d schema document(s) directly to branch %s", len(parsed), payload.branch_name)
    return {"applied": len(parsed)}


async def _fetch_all_items(
    *, marketplace_url: str, items: list[MarketplaceInstallItem]
) -> list[tuple[str, str]]:
    """Download every item. Returns (relative_path, content) tuples.

    Raises MarketplaceInstallError on any fetch failure.
    """
    log = get_run_logger()
    results: list[tuple[str, str]] = []
    async with MarketplaceClient(base_url=marketplace_url) as client:
        for item in items:
            try:
                fetched = await _fetch_one_item(client=client, item=item)
            except MarketplaceNotFoundError as exc:
                raise MarketplaceInstallError(f"marketplace item not found: {item.kind}:{item.namespace}/{item.name}") from exc
            except (MarketplaceUnreachableError, MarketplaceTimeoutError) as exc:
                raise MarketplaceInstallError(f"marketplace unreachable while fetching {item.namespace}/{item.name}") from exc
            results.extend(fetched)
            log.info("fetched marketplace item: %s/%s (%d files)", item.namespace, item.name, len(fetched))
    return results


@task(name="fetch-marketplace-item", cache_policy=NONE)
async def _fetch_one_item(
    client: MarketplaceClient, item: MarketplaceInstallItem
) -> list[tuple[str, str]]:
    """Return (relative_path, content) tuples for a single item (schema or collection)."""
    if item.kind == "schema":
        text, _resolved = await client.fetch_schema_content_by_ref(
            namespace=item.namespace, name=item.name, semver=item.semver
        )
        return [(f"{item.name}.yml", text)]
    if item.kind == "collection":
        bundle = await client.fetch_collection_bundle(namespace=item.namespace, name=item.name)
        schemas = bundle.get("schemas") or []
        if not isinstance(schemas, list):
            raise MarketplaceInstallError(f"malformed collection bundle for {item.namespace}/{item.name}")
        return [
            (f"{item.name}/{schema['name']}.yml", schema["content"])
            for schema in schemas
            if isinstance(schema, dict) and "name" in schema and "content" in schema
        ]
    raise MarketplaceInstallError(f"unknown item kind: {item.kind!r}")


@task(name="commit-schemas-to-repo", cache_policy=NONE)
async def _commit_and_push(
    payload: MarketplaceInstallPayload, schema_files: list[tuple[str, str]]
) -> str:
    """Write files, stage, commit, and push. Raise on any step — nothing is pushed on failure."""
    from infrahub.git.repository import InfrahubRepository

    log = get_run_logger()
    sdk = get_client()
    repo_node = await sdk.get(kind="CoreRepository", id=payload.repository_id)
    repo_name = repo_node.name.value  # type: ignore[union-attr]

    repo = await InfrahubRepository.init(id=payload.repository_id, name=repo_name, client=sdk)

    # Ensure the target branch exists locally (and is pushed to origin if we
    # have a remote). create_branch_in_git is idempotent -- it's a no-op when
    # the branch is already present. Covers the "Infrahub branch created with
    # sync_with_git=False" and "user typed a freeform branch name" cases
    # without a separate UI prompt.
    try:
        await repo.create_branch_in_git(branch_name=payload.branch_name, push_origin=True)
    except Exception as exc:  # noqa: BLE001
        raise MarketplaceInstallError(
            f"couldn't prepare git branch {payload.branch_name!r} on repository {repo_name!r}: {exc}"
        ) from exc

    git_repo = repo.get_git_repo_worktree(identifier=payload.branch_name)
    if git_repo is None:
        raise MarketplaceInstallError(f"no local worktree for branch {payload.branch_name!r}")
    worktree = repo.get_worktree(identifier=payload.branch_name)
    if worktree is None:
        raise MarketplaceInstallError(f"no worktree registered for branch {payload.branch_name!r}")

    worktree_path = Path(worktree.directory)
    schemas_dir = worktree_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    files_to_add: list[str] = []
    for relative_path, content in schema_files:
        file_path = schemas_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        files_to_add.append(str(file_path))

    infrahub_yml = worktree_path / ".infrahub.yml"
    if not infrahub_yml.exists():
        infrahub_yml.write_text("---\nschemas:\n  - schemas\n", encoding="utf-8")
        files_to_add.append(str(infrahub_yml))

    item_summary = ", ".join(f"{item.namespace}/{item.name}" for item in payload.items)
    commit_message = (
        f"Add {len(schema_files)} marketplace schema file(s) via Schema Marketplace\n"
        f"\n"
        f"Items: {item_summary}\n"
        f"Installed by: {payload.initiator_username}\n"
    )
    git_repo.index.add(files_to_add)
    commit = git_repo.index.commit(commit_message)
    commit_sha = str(commit)
    log.info("committed %d files as %s", len(schema_files), commit_sha)

    pushed = await repo.push(branch_name=payload.branch_name)
    if not pushed:
        # Remote push didn't happen — treat as a failure so the repo-sync does not
        # erroneously pick up a never-pushed commit from the local worktree.
        raise MarketplaceInstallError("repository has no remote origin; refusing to leave local-only commit")
    log.info("pushed branch %s", payload.branch_name)
    return commit_sha
