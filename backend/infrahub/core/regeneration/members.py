from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    import logging

    from infrahub_sdk.node import InfrahubNode


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


def should_render_artifact(
    artifact_id: str | None,
    regenerate_all_members: bool,
    impacted_artifacts: list[str],
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


def run_generator(
    instance_id: str | None,
    regenerate_all_members: bool,
    impacted_instances: list[str],
    member_changed_on_branch: bool | None = None,
) -> bool:
    """Whether a generator must run for one target.

    With an existing run record, the target runs on a forced pass or when the record is among those
    the change impacted. Without a record, the target runs when the branch itself changed it; a caller
    that cannot determine that (``member_changed_on_branch`` left as ``None``) treats a missing record
    as a new target and runs it.
    """
    if regenerate_all_members:
        return True
    if not instance_id:
        if member_changed_on_branch is None:
            return True
        return member_changed_on_branch
    return instance_id in impacted_instances
