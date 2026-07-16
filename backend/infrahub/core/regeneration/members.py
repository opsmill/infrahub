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
    managed_branch: bool,
    impacted_artifacts: list[str],
) -> bool:
    """Returns a boolean to indicate if an artifact should be generated or not.

    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * The source branch is synced with git and has file modifications (managed_branch)
        * The artifact_id exists in the impacted_artifacts list
    Will return false if:
        * The artifact_id exists and is not in the impacted list.
    """
    if not artifact_id or managed_branch:
        return True

    return artifact_id in impacted_artifacts


def run_generator(instance_id: str | None, managed_branch: bool, impacted_instances: list[str]) -> bool:
    """Returns a boolean to indicate if a generator instance needs to be executed.

    Will return true if:
        * The instance_id wasn't set which could be that it's a new object that doesn't have a previous generator instance
        * The source branch is set to sync with Git which would indicate that it could contain updates in git to the generator
        * The instance_id exists in the impacted_instances list
    Will return false if:
        * The source branch is a not one that syncs with git and the instance_id exists and is not in the impacted list.

    """
    if not instance_id or managed_branch:
        return True
    return instance_id in impacted_instances
