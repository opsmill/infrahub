from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, cast

from infrahub.exceptions import ResourceNotFoundError
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub_sdk.diff import NodeDiff

    from infrahub.services.adapters.cache import InfrahubCache

SCHEMA_CHANGE = re.compile(r"^Schema[A-Z]")


def has_data_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there are node or schema changes within the branch."""
    return any(entry["branch"] == branch for entry in diff_summary)


def has_node_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there is at least one node object that has been modified in the branch"""
    return any(entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"]) for entry in diff_summary)


def get_modified_kinds(diff_summary: list[NodeDiff], branch: str) -> list[str]:
    """Return a list of non schema kinds that have been modified on the branch"""
    return list(
        {
            entry["kind"]
            for entry in diff_summary
            if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
        }
    )


def get_modified_node_ids(diff_summary: list[NodeDiff], branch: str) -> list[str]:
    """Return a list of non schema nodes that have been modified on the branch"""
    return [
        entry["id"] for entry in diff_summary if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
    ]


async def set_diff_summary_cache(pipeline_id: UUID, diff_summary: list[NodeDiff], cache: InfrahubCache) -> None:
    serialized = json.dumps(diff_summary)
    await cache.set(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
        value=serialized,
        expires=KVTTL.TWO_HOURS,
    )


async def get_diff_summary_cache(pipeline_id: UUID, cache: InfrahubCache) -> list[NodeDiff]:
    summary_payload = await cache.get(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
    )

    if not summary_payload:
        raise ResourceNotFoundError(message=f"Diff summary for pipeline {pipeline_id} was not found in the cache")

    return cast(list["NodeDiff"], json.loads(summary_payload))
