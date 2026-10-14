"""Where the refs check's parts are named and assembled, and the only place that picks them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import GLOBAL_BRANCH_NAME, RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.core.repository_branch_status.factory import build_repository_branch_attributes_source

from ..models import GitReadOnlyRepositoryCheckRefs, TrackedRef
from .checker import ReadOnlyRepositoryRefsChecker, RefNameValidator, RefsCheckScheduler
from .constants import (
    REFS_CHECK_CLAIM_TTL_SECONDS,
    REFS_CHECK_GIT_KILL_MARGIN_SECONDS,
    REFS_CHECK_RETRY_SECONDS,
    REFS_CHECK_TIMEOUT_SECONDS,
)
from .gateway import GitRepositoryRefsGateway, git_check_ref_format
from .ref_missing import GraphRefMissingStatusStore, RefMissingImportGate

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub_sdk.client import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from ..models import RepositoryData
    from .ref_missing import RefMissingStatusStore
    from .tracked_commit import TrackedCommitReader


def build_check_refs_model(
    repository_data: RepositoryData, branch_ids: Mapping[str, str]
) -> GitReadOnlyRepositoryCheckRefs | None:
    """Turn one repository's per-branch graph values into a check request, or None when there is nothing to check.

    The global branch is excluded: it carries branch-agnostic data and names no branch a worker
    could check out. A branch whose id is unknown is left out rather than guessed, because without
    it the convergence broadcast cannot name the branch it is about. A branch on which the
    repository is not active is left out too, since an inactive repository is not one this worker
    is expected to be holding a copy of.
    """
    location = repository_data.location
    if not location:
        return None

    refs = [
        TrackedRef(
            infrahub_branch_name=branch_name,
            infrahub_branch_id=branch_ids[branch_name],
            ref=info.ref,
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
    tracked_commit_reader: TrackedCommitReader,
    ref_missing_store: RefMissingStatusStore,
) -> ReadOnlyRepositoryRefsChecker:
    gateway = GitRepositoryRefsGateway(client=client, list_kill_after_seconds=_list_kill_after_seconds())
    return ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=message_bus,
        lock_registry=lock_registry,
        gateway=gateway,
        ref_validator=RefNameValidator(check_ref_format=git_check_ref_format),
        scheduler=scheduler,
        tracked_commit_reader=tracked_commit_reader,
        ref_missing_store=ref_missing_store,
        claim_ttl_seconds=REFS_CHECK_CLAIM_TTL_SECONDS,
        detect_timeout_seconds=REFS_CHECK_TIMEOUT_SECONDS,
    )


def build_ref_missing_store(*, db: InfrahubDatabase, client: InfrahubClient) -> GraphRefMissingStatusStore:
    return GraphRefMissingStatusStore(
        db=db,
        client=client,
        build_attributes_source=build_repository_branch_attributes_source,
        find_branch=registry.get_branch_from_registry,
    )


def build_ref_missing_import_gate(*, db: InfrahubDatabase, client: InfrahubClient) -> RefMissingImportGate:
    return RefMissingImportGate(
        store=build_ref_missing_store(db=db, client=client),
        gateway=GitRepositoryRefsGateway(client=client, list_kill_after_seconds=_list_kill_after_seconds()),
    )


def _list_kill_after_seconds() -> float:
    # Sooner than the wall-clock ceiling on the listing, so a hung remote ends as a git failure
    # with the process gone rather than as an abandoned await over a process still running.
    return REFS_CHECK_TIMEOUT_SECONDS - REFS_CHECK_GIT_KILL_MARGIN_SECONDS


def build_refs_scheduler(*, cache: InfrahubCache, interval_mins: int) -> RefsCheckScheduler:
    interval_seconds = interval_mins * 60
    return RefsCheckScheduler(
        cache=cache,
        interval_seconds=interval_seconds,
        # Never longer than the interval itself, or a short interval would make a failed
        # repository wait longer than a healthy one rather than less.
        retry_seconds=min(REFS_CHECK_RETRY_SECONDS, interval_seconds),
    )
