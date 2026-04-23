"""Prefect workflow: download selected Marketplace items and commit them to a writable repo."""

from __future__ import annotations

from pathlib import Path

import yaml
from git import Actor
from prefect import flow, task
from prefect.cache_policies import NONE

from infrahub import lock
from infrahub.log import get_logger
from infrahub.marketplace.client import (
    MarketplaceClient,
    MarketplaceNotFoundError,
    MarketplaceTimeoutError,
    MarketplaceUnreachableError,
)
from infrahub.marketplace.models import (  # noqa: TC001  -- Prefect resolves flow parameter types at runtime
    MarketplaceInstallDirectPayload,
    MarketplaceInstallItem,
    MarketplaceInstallPayload,
)
from infrahub.workers.dependencies import get_client


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
    log = get_logger()

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
    log = get_logger()

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


async def _fetch_all_items(*, marketplace_url: str, items: list[MarketplaceInstallItem]) -> list[tuple[str, str]]:
    """Download every item. Returns (relative_path, content) tuples.

    Raises MarketplaceInstallError on any fetch failure.
    """
    log = get_logger()
    results: list[tuple[str, str]] = []
    async with MarketplaceClient(base_url=marketplace_url) as client:
        for item in items:
            try:
                fetched = await _fetch_one_item(client=client, item=item)
            except MarketplaceNotFoundError as exc:
                raise MarketplaceInstallError(
                    f"marketplace item not found: {item.kind}:{item.namespace}/{item.name}"
                ) from exc
            except (MarketplaceUnreachableError, MarketplaceTimeoutError) as exc:
                raise MarketplaceInstallError(
                    f"marketplace unreachable while fetching {item.namespace}/{item.name}"
                ) from exc
            results.extend(fetched)
            log.info("fetched marketplace item: %s/%s (%d files)", item.namespace, item.name, len(fetched))
    return results


async def _fetch_one_item(client: MarketplaceClient, item: MarketplaceInstallItem) -> list[tuple[str, str]]:
    """Return (relative_path, content) tuples for a single item (schema or collection).

    Kept as a plain async function rather than a Prefect ``@task`` so the live
    ``httpx.AsyncClient`` argument doesn't need to cross a serialization
    boundary if this flow is ever moved to a distributed executor.
    """
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


def _write_schema_files_to_worktree(worktree_path: Path, schema_files: list[tuple[str, str]]) -> list[str]:
    """Write schema YAML into `<worktree>/schemas/`; seed `.infrahub.yml` if absent.

    Returns the list of absolute file paths to stage in the git index.
    """
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
    return files_to_add


def _build_commit_message(payload: MarketplaceInstallPayload, n_files: int) -> str:
    item_summary = ", ".join(f"{item.namespace}/{item.name}" for item in payload.items)
    return (
        f"Add {n_files} marketplace schema file(s) via Schema Marketplace\n"
        f"\n"
        f"Items: {item_summary}\n"
        f"Installed by: {payload.initiator_username}\n"
    )


@task(name="commit-schemas-to-repo", cache_policy=NONE)
async def _commit_and_push(payload: MarketplaceInstallPayload, schema_files: list[tuple[str, str]]) -> str:
    """Write files, stage, commit, and push. Raise on any step — nothing is pushed on failure.

    Serialized per ``(repository_id, branch_name)`` via the Infrahub lock
    registry so two concurrent installs against the same target can't race
    on the shared on-disk worktree.
    """
    from infrahub.git.repository import InfrahubRepository

    log = get_logger()
    sdk = get_client()
    repo_node = await sdk.get(kind="CoreRepository", id=payload.repository_id)
    repo_name = repo_node.name.value  # type: ignore[union-attr]

    repo = await InfrahubRepository.init(id=payload.repository_id, name=repo_name, client=sdk)

    # create_branch_in_git is idempotent — covers "Infrahub branch created with
    # sync_with_git=False" and "user typed a freeform branch name" without a
    # separate UI prompt.
    try:
        await repo.create_branch_in_git(branch_name=payload.branch_name, push_origin=True)
    except Exception as exc:
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

    lock_name = f"{payload.repository_id}-{payload.branch_name}"
    async with lock.registry.get(name=lock_name, namespace="marketplace-install"):
        files_to_add = _write_schema_files_to_worktree(worktree_path, schema_files)
        commit_message = _build_commit_message(payload, len(schema_files))
        actor = Actor(name=payload.initiator_username, email=f"{payload.initiator_account_id}@infrahub.local")

        # Snapshot the pre-commit ref so we can roll the worktree back on any
        # failure. Without this, a failed push leaves the local worktree ahead
        # of origin — next use of the same branch would either push the stale
        # commit during an unrelated operation or confuse subsequent diffs.
        try:
            pre_commit_ref: str | None = git_repo.head.commit.hexsha
        except Exception:
            # Orphan branch / empty repo — nothing to reset to.
            pre_commit_ref = None

        try:
            git_repo.index.add(files_to_add)
            commit = git_repo.index.commit(commit_message, author=actor, committer=actor)
            commit_sha = str(commit)
            log.info("committed %d files as %s", len(schema_files), commit_sha)

            pushed = await repo.push(branch_name=payload.branch_name)
            if not pushed:
                raise MarketplaceInstallError("repository has no remote origin; refusing to leave local-only commit")
        except Exception:
            if pre_commit_ref is not None:
                try:
                    git_repo.head.reset(commit=pre_commit_ref, index=True, working_tree=True)
                    log.info("rolled worktree back to %s after install failure", pre_commit_ref)
                except Exception as reset_exc:
                    log.warning("failed to roll worktree back after install failure: %s", reset_exc)
            raise
        log.info("pushed branch %s", payload.branch_name)
        return commit_sha
