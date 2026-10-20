from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, assert_never, cast

from graphene import Field, Int, String
from pydantic import ValidationError as PydanticValidationError

from infrahub import config
from infrahub.core.constants import (
    InfrahubKind,
    PermissionAction,
    RepositoryGitCondition,
    RepositoryGitUnavailableReason,
)
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository
from infrahub.core.registry import registry
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.git.activity.models import ActivityRunRecord, LastRunRecord, RepositoryActivityOperation
from infrahub.git.branch_mapping import get_mapped_remote_branch, remote_branch_is_imported
from infrahub.git.state.cache_keys import activity_last_run_key, activity_run_pattern, refs_check_last_key
from infrahub.git.state.factory import build_repository_git_state_reader
from infrahub.git.state.models import CommitLogRequest
from infrahub.git.state.reader import NOT_IMPLEMENTED_MESSAGE
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.repository import RepositoryActivity, RepositoryCommits
from infrahub.lock import get_lock_cache_key, get_requested_at_from_lock_token, get_worker_id_from_lock_token
from infrahub.log import get_logger
from infrahub.permissions.types import define_object_permission_from_branch

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.account import ObjectPermission
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()

DEFAULT_LIMIT = 10
DEFAULT_OFFSET = 0
MIN_LIMIT = 1
MAX_LIMIT = 100

COMMIT_GIT_FIELDS = frozenset({"condition", "remote_head", "pending_count", "fetched_at", "unavailable", "edges"})
"""Selecting none of these means no worker request is made at all."""

NOT_CLONED_MESSAGE = "The answering worker holds no local copy of this repository yet."


def _view_permission(kind: str, branch_name: str) -> ObjectPermission:
    schema = registry.get_node_schema(name=kind, branch=branch_name, duplicate=False)
    return define_object_permission_from_branch(schema=schema, action=PermissionAction.VIEW, branch_name=branch_name)


def _raise_unless_any_repository_is_viewable(graphql_context: GraphqlContext, branch_name: str) -> None:
    """Raise the view denial unless the caller can view at least one repository kind.

    The denial names the first kind rather than the one behind the id, so it reveals nothing about
    what the id is or whether it exists.

    Raises:
        PermissionDeniedError: When no repository kind is viewable.

    """
    permissions = [
        _view_permission(kind=kind, branch_name=branch_name)
        for kind in (InfrahubKind.REPOSITORY, InfrahubKind.READONLYREPOSITORY)
    ]
    if any(graphql_context.active_permissions.has_permission(permission=permission) for permission in permissions):
        return

    graphql_context.active_permissions.raise_for_permission(permission=permissions[0])


async def _load_generic_repository(graphql_context: GraphqlContext, repository_id: str) -> CoreGenericRepository | None:
    """Load the repository this id names on the request branch, or None when it names anything else."""
    try:
        repository = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=CoreGenericRepository,
            id=repository_id,
            branch=graphql_context.branch,
            at=graphql_context.at,
        )
    except NodeNotFoundError:
        return None

    # The lookup validates the requested kind only when it falls back to the default filter, so the
    # id of any other node resolves too and must not be answered as though it were a repository.
    if InfrahubKind.GENERICREPOSITORY not in repository.get_schema().inherit_from:
        return None

    return repository


async def load_repository_for_view(graphql_context: GraphqlContext, repository_id: str) -> CoreGenericRepository:
    """Load a repository on the request branch and enforce view permission on its concrete kind.

    The check is imperative because the query analyzer maps top-level fields to kinds by exact
    name and cannot see a custom query.

    Raises:
        NodeNotFoundError: When the caller may view some repository kind and this id names no
            repository they may view.
        PermissionDeniedError: When the caller may view no repository kind at all.

    """
    branch = graphql_context.branch
    repository = await _load_generic_repository(graphql_context=graphql_context, repository_id=repository_id)

    if repository is not None and graphql_context.active_permissions.has_permission(
        permission=_view_permission(kind=repository.get_kind(), branch_name=branch.name)
    ):
        return repository

    # One caller gets one answer for every rejection, whichever of the two it is, so neither the
    # existence of an id nor the kind behind it can be read back from the difference.
    _raise_unless_any_repository_is_viewable(graphql_context=graphql_context, branch_name=branch.name)
    raise NodeNotFoundError(branch_name=branch.name, node_type=InfrahubKind.GENERICREPOSITORY, identifier=repository_id)


def _unavailable_message(reason: RepositoryGitUnavailableReason) -> str:
    match reason:
        case RepositoryGitUnavailableReason.NOT_CLONED:
            return NOT_CLONED_MESSAGE
        case RepositoryGitUnavailableReason.NOT_IMPLEMENTED:
            return NOT_IMPLEMENTED_MESSAGE
        case _:
            assert_never(reason)


def _unavailable_payload(reason: RepositoryGitUnavailableReason, error_message: str | None) -> dict[str, Any]:
    return {"reason": reason, "message": error_message or _unavailable_message(reason=reason)}


async def _resolve_checked_at(graphql_context: GraphqlContext, repository: CoreGenericRepository) -> datetime | None:
    """Return when the remote of a read-only repository was last checked for movement.

    A read-write repository returns None: its sync fetches the remote, so its fetch time already
    answers this. Best-effort: an unreachable cache, a flushed one or an unreadable value all read
    as never checked rather than failing the query.
    """
    if repository.get_kind() != InfrahubKind.READONLYREPOSITORY:
        return None

    key = refs_check_last_key(repository_id=repository.get_id())
    cache = graphql_context.active_service.cache
    try:
        value = await cache.get(key=key)
    # A best-effort field must not fail the query around it, whichever cache backend raised.
    except Exception:
        log.warning("Could not read the refs check time", repository_id=repository.get_id(), exc_info=True)
        return None
    if value is None:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        log.warning("Ignoring an unreadable refs check time", repository_id=repository.get_id(), value=value)
        return None


def _resolve_paging(limit: int | None, offset: int | None) -> tuple[int, int]:
    """Apply the documented paging defaults, then bound both values.

    Both arguments are nullable in the schema, so a caller can send an explicit null as readily as
    omitting them; each means "use the default" rather than "no limit".

    Raises:
        ValidationError: When either value falls outside its documented range.

    """
    resolved_limit = DEFAULT_LIMIT if limit is None else limit
    resolved_offset = DEFAULT_OFFSET if offset is None else offset

    if resolved_limit < MIN_LIMIT or resolved_limit > MAX_LIMIT:
        raise ValidationError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    if resolved_offset < 0:
        raise ValidationError("offset must be greater than or equal to 0")

    return resolved_limit, resolved_offset


def _resolve_remote_branch(
    repository_default_branch: str | None, infrahub_branch_name: str, branch_is_synced_with_git: bool
) -> str | None:
    """Return the remote branch this Infrahub branch reads.

    Returns None when the repository names no default branch, and when a sync would not import the
    branch this one maps to.
    """
    if not repository_default_branch:
        return None

    remote_branch = get_mapped_remote_branch(
        branch_name=infrahub_branch_name,
        repository_default_branch=repository_default_branch,
        infrahub_default_branch=registry.default_branch,
    )
    # Calling a branch untracked that a sync would still import onto would contradict the commit
    # reported next to it.
    if not remote_branch_is_imported(
        remote_branch_name=remote_branch,
        branch_is_synced_with_git=branch_is_synced_with_git,
        repository_default_branch=repository_default_branch,
        infrahub_default_branch=registry.default_branch,
        import_sync_branch_names=config.SETTINGS.git.import_sync_branch_names,
    ):
        return None
    return remote_branch


def _resolve_git_ref(
    repository: CoreGenericRepository, infrahub_branch_name: str, branch_is_synced_with_git: bool
) -> str | None:
    """Return the remote branch or tracked ref this Infrahub branch reads, or None when untracked.

    Raises:
        ValidationError: When the repository kind has no git state to read.

    """
    match repository.get_kind():
        case InfrahubKind.REPOSITORY:
            return _resolve_remote_branch(
                repository_default_branch=cast("CoreRepository", repository).default_branch.value,
                infrahub_branch_name=infrahub_branch_name,
                branch_is_synced_with_git=branch_is_synced_with_git,
            )
        case InfrahubKind.READONLYREPOSITORY:
            return cast("CoreReadOnlyRepository", repository).ref.value or None
        case unsupported_kind:
            raise ValidationError(f"Reading git state is not supported for a {unsupported_kind}")


def _viewable_branches(graphql_context: GraphqlContext, kind: str, branches: list[Branch]) -> list[Branch]:
    """Drop the branches the caller holds no view permission for.

    The decision turns only on whether a branch is the default one, so the one covering every other
    branch is resolved once rather than once per branch.
    """
    others = [branch for branch in branches if branch.name != registry.default_branch]
    may_view_default = graphql_context.active_permissions.has_permission(
        permission=_view_permission(kind=kind, branch_name=registry.default_branch)
    )
    may_view_others = bool(others) and graphql_context.active_permissions.has_permission(
        permission=_view_permission(kind=kind, branch_name=others[0].name)
    )
    return [
        branch
        for branch in branches
        if (may_view_default if branch.name == registry.default_branch else may_view_others)
    ]


class RepositoryCommitsResolver:
    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        repository_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch

        resolved_limit, resolved_offset = _resolve_paging(limit=limit, offset=offset)

        repository = await load_repository_for_view(graphql_context=graphql_context, repository_id=repository_id)
        git_ref = _resolve_git_ref(
            repository=repository,
            infrahub_branch_name=branch.name,
            branch_is_synced_with_git=branch.sync_with_git,
        )
        imported_commit = repository.commit.value or None

        payload: dict[str, Any] = {
            "repository_id": repository.get_id(),
            "branch_name": branch.name,
            "git_ref": git_ref,
            "imported_commit": imported_commit,
            "edges": [],
        }

        fields = extract_graphql_fields(info=info)
        checked_at = None
        if "checked_at" in fields:
            checked_at = await _resolve_checked_at(graphql_context=graphql_context, repository=repository)
        payload["checked_at"] = checked_at

        if git_ref is None:
            payload["condition"] = RepositoryGitCondition.NOT_TRACKED
            return payload

        if not COMMIT_GIT_FIELDS & set(fields):
            return payload

        reader = build_repository_git_state_reader(message_bus=graphql_context.active_service.message_bus)
        result = await reader.commits(
            request=CommitLogRequest(
                repository_id=repository.get_id(),
                repository_name=str(repository.name.value),
                repository_kind=repository.get_kind(),
                location=str(repository.location.value),
                infrahub_branch_name=branch.name,
                git_ref=git_ref,
                imported_commit=imported_commit,
                limit=resolved_limit,
                offset=resolved_offset,
                include_pending_count="pending_count" in fields,
            )
        )

        payload["condition"] = result.condition
        payload["remote_head"] = result.remote_head
        payload["pending_count"] = result.pending_count
        payload["fetched_at"] = result.fetched_at
        if result.imported_commit:
            payload["imported_commit"] = result.imported_commit
        payload["edges"] = [
            {
                "node": {
                    "hash": commit.hash,
                    "short_hash": commit.short_hash,
                    "summary": commit.summary,
                    "message": commit.message,
                    "author_name": commit.author_name,
                    "authored_at": commit.authored_at,
                    "committed_at": commit.committed_at,
                    "state": commit.state,
                }
            }
            for commit in result.commits
        ]
        # CommitLogResult ties the reason and the condition together, so this agrees with
        # condition == UNAVAILABLE by construction.
        if result.unavailable_reason is not None:
            payload["unavailable"] = _unavailable_payload(
                reason=result.unavailable_reason, error_message=result.error_message
            )

        return payload


async def _read_active_runs(cache: InfrahubCache, repository_id: str) -> list[ActivityRunRecord]:
    keys = await cache.list_keys(filter_pattern=activity_run_pattern(repository_id=repository_id))
    # An idle repository is the common case under polling, so it costs no second round trip.
    if not keys:
        return []
    runs = []
    # A record can expire between the listing and the read, which leaves its value empty.
    for value in await cache.get_values(keys=keys):
        if value is None:
            continue
        try:
            runs.append(ActivityRunRecord.model_validate_json(value))
        except PydanticValidationError:
            log.warning("Ignoring an unreadable repository run record", repository_id=repository_id)
    return sorted(runs, key=lambda run: run.started_at)


async def _read_last_runs(cache: InfrahubCache, repository_id: str) -> list[LastRunRecord]:
    keys = [
        activity_last_run_key(repository_id=repository_id, operation=operation.value)
        for operation in RepositoryActivityOperation
    ]
    last_runs = []
    for value in await cache.get_values(keys=keys):
        if value is None:
            continue
        try:
            last_runs.append(LastRunRecord.model_validate_json(value))
        except PydanticValidationError:
            log.warning("Ignoring an unreadable repository last run record", repository_id=repository_id)
    return sorted(last_runs, key=lambda last_run: last_run.finished_at, reverse=True)


async def _read_lock(cache: InfrahubCache, repository_name: str) -> dict[str, Any] | None:
    token = await cache.get(key=get_lock_cache_key(name=repository_name, namespace="repository"))
    worker_id = get_worker_id_from_lock_token(token)
    if worker_id is None:
        return None
    return {"worker_id": worker_id, "requested_at": get_requested_at_from_lock_token(token)}


def _viewable_branch_names(graphql_context: GraphqlContext, kind: str, branch_names: set[str]) -> set[str]:
    """Keep the names of the branches that still exist and that the caller may view."""
    branches = [branch for name in branch_names if (branch := registry.branch.get(name)) is not None]
    return {branch.name for branch in _viewable_branches(graphql_context=graphql_context, kind=kind, branches=branches)}


class RepositoryActivityResolver:
    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        id: str,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context

        repository = await load_repository_for_view(graphql_context=graphql_context, repository_id=id)
        # The records are keyed by id, so a repository named in the request is read under its id.
        repository_id = repository.get_id()
        # The cache holds only the current state, so the requested time does not apply to these reads.
        cache = graphql_context.active_service.cache
        active_runs, last_runs, lock = await asyncio.gather(
            _read_active_runs(cache=cache, repository_id=repository_id),
            _read_last_runs(cache=cache, repository_id=repository_id),
            _read_lock(cache=cache, repository_name=str(repository.name.value)),
        )

        recorded_branches = {run.branch_name for run in active_runs if run.branch_name is not None} | {
            branch.branch_name for last_run in last_runs for branch in last_run.branches
        }
        viewable = _viewable_branch_names(
            graphql_context=graphql_context, kind=repository.get_kind(), branch_names=recorded_branches
        )

        return {
            "repository_id": repository_id,
            "active_runs": {
                "edges": [
                    {"node": run.model_dump()}
                    for run in active_runs
                    if run.branch_name is None or run.branch_name in viewable
                ]
            },
            "last_runs": {
                "edges": [
                    {
                        "node": {
                            "operation": last_run.operation,
                            "started_at": last_run.started_at,
                            "finished_at": last_run.finished_at,
                            "branches": {
                                "edges": [
                                    {"node": branch.model_dump()}
                                    for branch in last_run.branches
                                    if branch.branch_name in viewable
                                ]
                            },
                        }
                    }
                    for last_run in last_runs
                ]
            },
            "lock": lock,
        }


InfrahubRepositoryActivity = Field(
    RepositoryActivity,
    id=String(required=True, description="ID or name of a read-write or read-only repository."),
    description="What is running on a repository now, the last run of each operation, and which worker holds the "
    "repository lock. The answer is the same on every branch.",
    resolver=RepositoryActivityResolver.resolve,
    required=True,
)

InfrahubRepositoryCommits = Field(
    RepositoryCommits,
    repository_id=String(required=True),
    limit=Int(required=False, description="Page size, 1 to 100. Default 10."),
    offset=Int(required=False, description="Default 0."),
    description="Paged commit log for a repository on the request branch.",
    resolver=RepositoryCommitsResolver.resolve,
    required=True,
)
