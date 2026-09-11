from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from graphene import Field, Int, String

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
from infrahub.git.branch_mapping import get_mapped_remote_branch, remote_branch_is_imported
from infrahub.git.state.factory import build_repository_git_state_reader
from infrahub.git.state.models import CommitLogRequest
from infrahub.git.state.reader import NOT_IMPLEMENTED_MESSAGE
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.repository import RepositoryBranchDrifts, RepositoryCommits
from infrahub.permissions.types import define_object_permission_from_branch

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.account import ObjectPermission
    from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
    from infrahub.git.state.models import CommitLogResult
    from infrahub.graphql.initialization import GraphqlContext

DEFAULT_LIMIT = 10
DEFAULT_OFFSET = 0
MIN_LIMIT = 1
MAX_LIMIT = 100

COMMIT_GIT_FIELDS = frozenset({"condition", "remote_head", "pending_count", "fetched_at", "unavailable", "edges"})
"""Selecting none of these means no worker request is made at all."""

GENERIC_UNAVAILABLE_MESSAGE = "No git-derived answer could be produced for this repository."

UNAVAILABLE_MESSAGES: dict[RepositoryGitUnavailableReason, str] = {
    RepositoryGitUnavailableReason.NOT_CLONED: "The answering worker holds no local copy of this repository yet.",
    RepositoryGitUnavailableReason.NOT_IMPLEMENTED: NOT_IMPLEMENTED_MESSAGE,
    RepositoryGitUnavailableReason.TIMEOUT: "No worker answered within the configured time.",
}


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


def _unavailable_payload(result: CommitLogResult | None, reason: RepositoryGitUnavailableReason) -> dict[str, Any]:
    return {
        "reason": reason,
        "message": (
            result.error_message
            if result and result.error_message
            else UNAVAILABLE_MESSAGES.get(reason, GENERIC_UNAVAILABLE_MESSAGE)
        ),
        "warm_up_task_id": result.warm_up_task_id if result else None,
    }


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


def _resolve_git_ref(
    repository: CoreGenericRepository, infrahub_branch_name: str, branch_is_synced_with_git: bool
) -> str | None:
    """Return the remote branch or tracked ref this Infrahub branch reads, or None when untracked.

    Raises:
        ValidationError: When the repository kind has no git state to read.

    """
    match repository.get_kind():
        case InfrahubKind.REPOSITORY:
            repository_default_branch = cast("CoreRepository", repository).default_branch.value
            if not repository_default_branch:
                return None
            remote_branch = get_mapped_remote_branch(
                branch_name=infrahub_branch_name,
                repository_default_branch=repository_default_branch,
                infrahub_default_branch=registry.default_branch,
            )
            # Calling a branch untracked that a sync would still import onto would contradict the
            # imported_commit answered next to it.
            if not remote_branch_is_imported(
                remote_branch_name=remote_branch,
                branch_is_synced_with_git=branch_is_synced_with_git,
                repository_default_branch=repository_default_branch,
                infrahub_default_branch=registry.default_branch,
                import_sync_branch_names=config.SETTINGS.git.import_sync_branch_names,
            ):
                return None
            return remote_branch
        case InfrahubKind.READONLYREPOSITORY:
            return cast("CoreReadOnlyRepository", repository).ref.value or None
        case unsupported_kind:
            raise ValidationError(f"Reading git state is not supported for a {unsupported_kind}")


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
            payload["unavailable"] = _unavailable_payload(result=result, reason=result.unavailable_reason)

        return payload


class RepositoryBranchDriftResolver:
    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        repository_id: str,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context

        repository = await load_repository_for_view(graphql_context=graphql_context, repository_id=repository_id)

        return {
            "repository_id": repository.get_id(),
            "edges": [],
            "unavailable": _unavailable_payload(result=None, reason=RepositoryGitUnavailableReason.NOT_IMPLEMENTED),
        }


InfrahubRepositoryCommits = Field(
    RepositoryCommits,
    repository_id=String(required=True),
    limit=Int(required=False, description="Page size, 1 to 100. Default 10."),
    offset=Int(required=False, description="Default 0."),
    description="Paged commit log for a repository on the request branch.",
    resolver=RepositoryCommitsResolver.resolve,
    required=True,
)

InfrahubRepositoryBranchDrift = Field(
    RepositoryBranchDrifts,
    repository_id=String(required=True),
    description="Per-branch drift for a repository.",
    resolver=RepositoryBranchDriftResolver.resolve,
    required=True,
)
