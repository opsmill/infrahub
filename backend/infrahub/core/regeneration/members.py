from __future__ import annotations

from typing import TYPE_CHECKING

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
        object_id = subscriber.object.id
        if object_id is None:
            log.warning(
                f"Skipping orphan subscriber {subscriber.id} for definition {definition_name}: object peer unresolvable"
            )
            continue
        subscriber_by_member[object_id] = subscriber.id
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
