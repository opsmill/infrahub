from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    import logging
    from collections.abc import Collection, Iterable

    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.timestamp import Timestamp


def map_subscriber_ids_by_member(
    existing_subscribers: list[InfrahubNode],
    definition_name: str,
    log: logging.Logger | logging.LoggerAdapter,
) -> dict[str, str]:
    """Map each member id to its existing subscriber id, skipping subscribers whose object peer cannot be resolved.

    Such orphan rows can appear when a target node has been removed via a path that does not
    cascade-delete the subscriber.
    """
    subscriber_by_member: dict[str, str] = {}
    for subscriber in existing_subscribers:
        try:
            # The member id lives on the object peer; subscriber.object.id is None for some kinds.
            member_id = subscriber.object.peer.id
        except (ValueError, NodeNotFoundError):
            log.warning(
                f"Skipping orphan subscriber {subscriber.id} for definition {definition_name}: object peer unresolvable"
            )
            continue
        if member_id is None:
            continue
        subscriber_by_member[member_id] = subscriber.id
    return subscriber_by_member


@dataclass(frozen=True, slots=True)
class ArtifactCheckRecord:
    """A check of an artifact recorded by a proposed change."""

    artifact_id: str
    checked_at: Timestamp
    failed: bool


@dataclass(frozen=True, slots=True)
class ArtifactRecheckPlan:
    """The artifacts of a definition grouped by what can make their last check out of date.

    ``recent_ids`` were checked during the previous run, so only edits after ``recent_since`` can be missing
    from them. ``older_ids`` were checked before it, or never, and are compared with the edits after
    ``older_since``. ``recent_latest`` and ``older_latest`` are the latest checks of each group. ``always_ids``
    failed their last check or were checked before the branch point moved, so they are checked again whatever
    was edited.
    """

    recent_ids: frozenset[str]
    recent_since: Timestamp | None
    recent_latest: Timestamp | None
    older_ids: frozenset[str]
    older_since: Timestamp | None
    older_latest: Timestamp | None
    always_ids: frozenset[str]

    @property
    def edits_since(self) -> Timestamp | None:
        """Return the earliest time from which edits can make one of the grouped artifacts out of date."""
        times = [time for time in (self.recent_since, self.older_since) if time is not None]
        return min(times) if times else None


def plan_artifact_recheck(
    artifact_ids: Iterable[str],
    check_records: Iterable[ArtifactCheckRecord],
    previous_run_started_at: Timestamp | None,
    branched_from: Timestamp,
) -> ArtifactRecheckPlan:
    """Group the artifacts of a definition by their last check.

    An artifact never checked counts as checked at the branch point, since it was rendered from data that
    only edits on the branch can have changed.
    """
    last_checks: dict[str, ArtifactCheckRecord] = {}
    for record in check_records:
        known = last_checks.get(record.artifact_id)
        if known is None or known.checked_at < record.checked_at:
            last_checks[record.artifact_id] = record

    recent: dict[str, Timestamp] = {}
    older: dict[str, Timestamp] = {}
    always: set[str] = set()
    for artifact_id in artifact_ids:
        last_check = last_checks.get(artifact_id)
        if last_check is None:
            older[artifact_id] = branched_from
        elif last_check.failed or last_check.checked_at < branched_from:
            always.add(artifact_id)
        elif previous_run_started_at is not None and last_check.checked_at >= previous_run_started_at:
            recent[artifact_id] = last_check.checked_at
        else:
            older[artifact_id] = last_check.checked_at

    return ArtifactRecheckPlan(
        recent_ids=frozenset(recent),
        recent_since=previous_run_started_at if recent else None,
        recent_latest=max(recent.values()) if recent else None,
        older_ids=frozenset(older),
        older_since=min(older.values()) if older else None,
        older_latest=max(older.values()) if older else None,
        always_ids=frozenset(always),
    )


def should_render_artifact(
    artifact_id: str | None,
    regenerate_all_members: bool,
    impacted_artifacts: Collection[str],
) -> bool:
    """Returns a boolean to indicate if an artifact should be generated or not.

    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * regenerate_all_members is set, forcing every member to be regenerated regardless of impact
        * The artifact_id exists in the impacted_artifacts list
    Will return false if:
        * The artifact_id exists and is not in the impacted list.
    """
    if not artifact_id or regenerate_all_members:
        return True

    return artifact_id in impacted_artifacts


def run_generator(instance_id: str | None, regenerate_all_members: bool, impacted_instances: list[str]) -> bool:
    """Returns a boolean to indicate if a generator instance needs to be executed.

    Will return true if:
        * The instance_id wasn't set which could be that it's a new object that doesn't have a previous generator instance
        * regenerate_all_members is set, forcing every instance to be executed regardless of impact
        * The instance_id exists in the impacted_instances list
    Will return false if:
        * regenerate_all_members is not set and the instance_id exists and is not in the impacted list.

    """
    if not instance_id or regenerate_all_members:
        return True
    return instance_id in impacted_instances
