from inspect import isawaitable
from typing import Any, Callable

from graphql import DocumentNode, GraphQLResolveInfo, OperationDefinitionNode, OperationType

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.merge.write_blocker import MergeWriteBlocker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]
# BranchDelete is expected to verify that it is not deleting the merging branch
ALLOWED_MUTATIONS_DURING_MERGE = ["BranchCreate", "BranchDelete"]


def branch_status_middleware(document: DocumentNode) -> list[Callable[..., Any]] | None:
    """Middleware to execute `document` with: the branch status check when it holds a mutation, else none.

    The check gates the top-level fields of a mutation only, but graphql-core calls a middleware for every field
    it resolves: for a query, it would cost one call per field, more than a million for a large query, and
    check nothing. The operation definitions decide, not the fields they select, so that a mutation whose
    top-level fields come from a fragment is still checked.
    """
    for definition in document.definitions:
        if isinstance(definition, OperationDefinitionNode) and definition.operation == OperationType.MUTATION:
            return [raise_on_mutation_for_branch_status]
    return None


def raise_on_mutation_for_branch_status(next: Any, root: Any, info: GraphQLResolveInfo, **kwargs: Any) -> Any:  # noqa: A002
    # Stay synchronous outside the gated case: an async middleware would return a coroutine for
    # every resolved field, forcing the whole execution onto graphql-core's async completion path.
    # That per-field overhead is what let a single IntrospectionQuery monopolize a worker's event
    # loop for 10+ seconds.
    if info.operation.operation.value == "mutation" and info.path.prev is None:
        return _gate_top_level_mutation(next, root, info, kwargs)
    return next(root, info, **kwargs)


async def _gate_top_level_mutation(next: Any, root: Any, info: GraphQLResolveInfo, kwargs: dict[str, Any]) -> Any:  # noqa: A002
    # Only gate at the top-level mutation field so the merge-protection cache key is read once per
    # mutation rather than once per resolved field.
    # Use .field_name to get the field being resolved in case the mutation includes top-level fields
    mutation_name = info.field_name
    merge_write_blocker = MergeWriteBlocker(cache=info.context.active_service.cache)
    branch_status_checker = BranchStatusChecker(db=info.context.db, merge_write_blocker=merge_write_blocker)
    if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
        branch_status_checker.check_needs_rebase_status(branch=info.context.branch)
    if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
        branch_status_checker.check_merge_status(branch=info.context.branch)
    if mutation_name not in ALLOWED_MUTATIONS_DURING_MERGE:
        await branch_status_checker.check_merging_status(branch=info.context.branch)

    result = next(root, info, **kwargs)
    if isawaitable(result):
        return await result
    return result
