from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from graphene import Field, Int, String

from infrahub.core.constants import (
    InfrahubKind,
    PermissionAction,
    RepositoryGitCondition,
    RepositoryGitUnavailableReason,
)
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository
from infrahub.core.registry import registry
from infrahub.exceptions import ValidationError
from infrahub.git.branch_mapping import get_mapped_remote_branch
from infrahub.git.state.factory import build_repository_git_state_reader
from infrahub.git.state.models import CommitLogRequest
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.repository import RepositoryBranchDrifts, RepositoryCommits
from infrahub.permissions.types import define_object_permission_from_branch

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
    from infrahub.git.state.models import CommitLogResult
    from infrahub.graphql.initialization import GraphqlContext

DEFAULT_LIMIT = 10
MIN_LIMIT = 1
MAX_LIMIT = 100

COMMIT_GIT_FIELDS = frozenset({"condition", "remote_head", "pending_count", "fetched_at", "unavailable", "edges"})
"""Selecting none of these means no worker request is made at all."""

UNAVAILABLE_MESSAGES: dict[RepositoryGitUnavailableReason, str] = {
    RepositoryGitUnavailableReason.NOT_CLONED: "The answering worker holds no local copy of this repository yet.",
    RepositoryGitUnavailableReason.NOT_IMPLEMENTED: "Reading git state from a worker is not available in this version.",
    RepositoryGitUnavailableReason.TIMEOUT: "No worker answered within the configured time.",
}


async def load_repository_for_view(graphql_context: GraphqlContext, repository_id: str) -> CoreGenericRepository:
    """Load a repository on the request branch and enforce view permission on its concrete kind.

    The check is imperative because the query analyzer maps top-level fields to kinds by exact
    name and cannot see a custom query.
    """
    branch = graphql_context.branch
    repository = await NodeManager.get_one_by_id_or_default_filter(
        db=graphql_context.db,
        kind=CoreGenericRepository,
        id=repository_id,
        branch=branch,
    )

    schema = registry.get_node_schema(name=repository.get_kind(), branch=branch.name, duplicate=False)
    permission = define_object_permission_from_branch(
        schema=schema, action=PermissionAction.VIEW, branch_name=branch.name
    )
    graphql_context.active_permissions.raise_for_permission(permission=permission)

    return repository


def _unavailable_payload(result: CommitLogResult | None, reason: RepositoryGitUnavailableReason) -> dict[str, Any]:
    return {
        "reason": reason,
        "message": (result.error_message if result and result.error_message else UNAVAILABLE_MESSAGES[reason]),
        "warm_up_task_id": result.warm_up_task_id if result else None,
    }


def _validate_paging(limit: int, offset: int) -> None:
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise ValidationError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    if offset < 0:
        raise ValidationError("offset must be greater than or equal to 0")


def _resolve_git_ref(
    repository: CoreGenericRepository, infrahub_branch_name: str, branch_is_synced_with_git: bool
) -> str | None:
    """Return the remote branch or tracked ref this Infrahub branch reads, or None when untracked.

    Raises:
        ValidationError: When the repository kind has no git state to read.

    """
    match repository.get_kind():
        case InfrahubKind.REPOSITORY:
            # A branch Infrahub deliberately never imports may still share a name with a real
            # remote branch, so mapping it through would report drift for history that is not meant
            # to arrive.
            if not branch_is_synced_with_git:
                return None
            repository_default_branch = cast("CoreRepository", repository).default_branch.value
            if not repository_default_branch:
                return None
            return get_mapped_remote_branch(
                branch_name=infrahub_branch_name,
                repository_default_branch=repository_default_branch,
                infrahub_default_branch=registry.default_branch,
            )
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
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch

        _validate_paging(limit=limit, offset=offset)

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
                limit=limit,
                offset=offset,
                include_pending_count="pending_count" in fields,
            )
        )

        payload["condition"] = result.condition
        payload["remote_head"] = result.remote_head
        payload["pending_count"] = result.pending_count
        payload["fetched_at"] = result.fetched_at
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
        if result.unavailable_reason:
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
    description="Paged commit log for a repository on the request branch. Requires view permission on the repository.",
    resolver=RepositoryCommitsResolver.resolve,
    required=True,
)

InfrahubRepositoryBranchDrift = Field(
    RepositoryBranchDrifts,
    repository_id=String(required=True),
    description="Per-branch drift for a repository. Requires view permission on the repository.",
    resolver=RepositoryBranchDriftResolver.resolve,
    required=True,
)
