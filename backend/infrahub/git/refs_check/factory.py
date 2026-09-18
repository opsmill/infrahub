"""Where the refs check's parts are named and assembled, and the only place that picks them."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from infrahub.core.constants import GLOBAL_BRANCH_NAME, RepositoryInternalStatus

from ..models import GitReadOnlyRepositoryCheckRefs, TrackedRef
from .checker import ReadOnlyRepositoryRefsChecker, RefNameValidator, RefsCheckScheduler
from .constants import REFS_CHECK_CLAIM_TTL_SECONDS, REFS_CHECK_RETRY_SECONDS, REFS_CHECK_TIMEOUT_SECONDS
from .gateway import GitRepositoryRefsGateway, git_check_ref_format

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.protocols import CoreReadOnlyRepository

    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from ..models import RepositoryData


def build_check_refs_model(
    repository_data: RepositoryData, branch_ids: Mapping[str, str]
) -> GitReadOnlyRepositoryCheckRefs | None:
    """Turn one repository's per-branch graph values into a check request, or None when there is nothing to check.

    The global branch is excluded: it carries branch-agnostic data and names no branch a worker
    could check out. A branch whose id is unknown is left out rather than guessed, because without
    it the convergence broadcast cannot name the branch it is about. A branch on which the
    repository is not active is left out too: its first import has not completed, so this worker
    has no local copy to compare a remote head against.
    """
    location = cast("CoreReadOnlyRepository", repository_data.repository).location.value
    if not location:
        return None

    refs = [
        TrackedRef(
            infrahub_branch_name=branch_name,
            infrahub_branch_id=branch_ids[branch_name],
            ref=info.ref,
            commit=repository_data.branches.get(branch_name),
        )
        for branch_name, info in repository_data.branch_info.items()
        if info.ref
        and branch_name in branch_ids
        and branch_name != GLOBAL_BRANCH_NAME
        and info.internal_status == RepositoryInternalStatus.ACTIVE.value
    ]
    if not refs:
        return None

    return GitReadOnlyRepositoryCheckRefs(
        repository_id=repository_data.repository_id,
        repository_name=repository_data.repository_name,
        location=location,
        refs=tuple(refs),
    )


def build_refs_checker(
    *,
    cache: InfrahubCache,
    message_bus: InfrahubMessageBus,
    lock_registry: InfrahubLockRegistry,
    client: InfrahubClient,
    scheduler: RefsCheckScheduler,
) -> ReadOnlyRepositoryRefsChecker:
    return ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=message_bus,
        lock_registry=lock_registry,
        gateway=GitRepositoryRefsGateway(client=client),
        ref_validator=RefNameValidator(check_ref_format=git_check_ref_format),
        scheduler=scheduler,
        claim_ttl_seconds=REFS_CHECK_CLAIM_TTL_SECONDS,
        detect_timeout_seconds=REFS_CHECK_TIMEOUT_SECONDS,
    )


def build_refs_scheduler(*, cache: InfrahubCache, interval_mins: int) -> RefsCheckScheduler:
    interval_seconds = interval_mins * 60
    return RefsCheckScheduler(
        cache=cache,
        interval_seconds=interval_seconds,
        # Never longer than the interval itself, or a short interval would make a failed
        # repository wait longer than a healthy one rather than less.
        retry_seconds=min(REFS_CHECK_RETRY_SECONDS, interval_seconds),
    )
