from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

from infrahub_sdk.diff import diff_tree_node_to_node_diff

from infrahub.core.regeneration.changes_since import DiffChangeTimes
from infrahub.exceptions import ResourceNotFoundError
from infrahub.git.repository import get_initialized_repo
from infrahub.message_bus.types import KVTTL
from infrahub.workers.dependencies import get_cache

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.message_bus.types import ProposedChangeRepository
    from infrahub.services.adapters.cache import InfrahubCache

SCHEMA_CHANGE = re.compile(r"^Schema[A-Z]")

# The fields of the summary query of the SDK, plus the times and peers that tell when a change was made.
DIFF_SUMMARY_WITH_CHANGE_TIMES = """
query GetDiffSummaryWithChangeTimes($branch_name: String!) {
    DiffTree(branch: $branch_name) {
        from_time
        to_time
        nodes {
            uuid
            kind
            status
            label
            last_changed_at
            num_added
            num_updated
            num_removed
            attributes {
                name
                status
                last_changed_at
                num_added
                num_updated
                num_removed
                properties {
                    last_changed_at
                }
            }
            relationships {
                name
                status
                cardinality
                last_changed_at
                num_added
                num_updated
                num_removed
                elements {
                    status
                    peer_id
                    last_changed_at
                    num_added
                    num_updated
                    num_removed
                }
            }
        }
    }
}
"""


@dataclass(frozen=True, kw_only=True, slots=True)
class RepositoryFileDiff:
    """File-level diff for a single repository between two commits."""

    files_changed: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)


class RepositoryFileDiffer(Protocol):
    """Computes the file diff for a repository between two commits.

    Implementations resolve the worktree for the given repository kind and return the files that
    differ between the source and destination commits.
    """

    async def calculate_diff(
        self,
        *,
        repository_id: str,
        repository_name: str,
        repository_kind: str,
        infrahub_branch_name: str,
        source_commit: str,
        destination_commit: str,
    ) -> RepositoryFileDiff: ...


class GitRepositoryFileDiffer:
    """RepositoryFileDiffer backed by the on-disk git worktree.

    The repository kind selects which repository class loads the worktree; the two commits are the
    tracked Git branch tips for a managed repository or the per-branch pinned commits for a
    read-only repository, already resolved per Infrahub branch by the gather queries.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def calculate_diff(
        self,
        *,
        repository_id: str,
        repository_name: str,
        repository_kind: str,
        infrahub_branch_name: str,
        source_commit: str,
        destination_commit: str,
    ) -> RepositoryFileDiff:
        git_repo = await get_initialized_repo(
            client=self._client,
            repository_id=repository_id,
            name=repository_name,
            repository_kind=repository_kind,
            infrahub_branch_name=infrahub_branch_name,
        )
        files_changed, files_added, files_removed = await git_repo.calculate_diff_between_commits(
            first_commit=destination_commit, second_commit=source_commit
        )
        return RepositoryFileDiff(files_changed=files_changed, files_added=files_added, files_removed=files_removed)


class RepositoryFileDiffPopulator:
    """Populates the per-repository file diff on a set of proposed-change repositories."""

    def __init__(self, differ: RepositoryFileDiffer) -> None:
        self._differ = differ

    async def populate(self, repositories: list[ProposedChangeRepository]) -> None:
        """Populate files_added/changed/removed for every linked repository with a non-empty commit diff.

        The diff is computed per repository and per branch pair for both managed and read-only
        repositories, independent of the source branch's sync_with_git flag. A repository whose source
        and destination commits match has no file changes and is left untouched.
        """
        for repo in repositories:
            if not repo.has_file_diff:
                continue
            diff = await self._differ.calculate_diff(
                repository_id=repo.repository_id,
                repository_name=repo.repository_name,
                repository_kind=repo.kind,
                infrahub_branch_name=repo.source_branch,
                source_commit=repo.source_commit,
                destination_commit=repo.destination_commit,
            )
            repo.files_changed = diff.files_changed
            repo.files_added = diff.files_added
            repo.files_removed = diff.files_removed


def has_data_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there are node or schema changes within the branch."""
    return any(entry["branch"] == branch for entry in diff_summary)


def has_node_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there is at least one node object that has been modified in the branch."""
    return any(entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"]) for entry in diff_summary)


def get_modified_kinds(diff_summary: list[NodeDiff], branch: str) -> list[str]:
    """Return a list of non schema kinds that have been modified on the branch."""
    return list(
        {
            entry["kind"]
            for entry in diff_summary
            if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
        }
    )


async def read_diff_summary(client: InfrahubClient, branch: str) -> tuple[list[NodeDiff], DiffChangeTimes | None]:
    """Read the stored diff of a branch as a diff summary, with the times of its changes.

    The times are None when the branch has no stored diff.
    """
    response = await client.execute_graphql(
        query=DIFF_SUMMARY_WITH_CHANGE_TIMES,
        branch_name=branch,
        variables={"branch_name": branch},
        operation_name="GetDiffSummaryWithChangeTimes",
    )
    diff_tree = response["DiffTree"]
    if diff_tree is None or "nodes" not in diff_tree:
        return [], None
    diff_summary = [diff_tree_node_to_node_diff(node_dict=node, branch_name=branch) for node in diff_tree["nodes"]]
    return diff_summary, parse_diff_change_times(diff_tree=diff_tree)


def parse_diff_change_times(diff_tree: dict[str, Any]) -> DiffChangeTimes:
    """Collect the last change time of each node, field and relationship peer of a diff tree response.

    A node listed more than once keeps the latest time of each field. An attribute takes the latest
    time among itself and its properties, since its own time is the one it was added or removed at,
    not the one its value changed at. A relationship takes the latest time among itself and its peers,
    since the response can leave the relationship's own time empty.
    """
    nodes: dict[str, datetime] = {}
    fields: dict[str, dict[str, datetime]] = {}
    peers: dict[str, dict[str, dict[str, datetime]]] = {}
    for node in diff_tree["nodes"]:
        node_id = str(node["uuid"])
        node_time = _latest(nodes.get(node_id), _parse_time(node.get("last_changed_at")))
        if node_time is not None:
            nodes[node_id] = node_time
        for attribute in node.get("attributes", []):
            attribute_time = _parse_time(attribute.get("last_changed_at"))
            for attribute_property in attribute.get("properties") or []:
                attribute_time = _latest(attribute_time, _parse_time(attribute_property.get("last_changed_at")))
            _keep_latest(times=fields.setdefault(node_id, {}), key=str(attribute["name"]), changed_at=attribute_time)
        for relationship in node.get("relationships", []):
            relationship_name = str(relationship["name"])
            relationship_time = _parse_time(relationship.get("last_changed_at"))
            for element in relationship.get("elements", []):
                element_time = _parse_time(element.get("last_changed_at"))
                relationship_time = _latest(relationship_time, element_time)
                _keep_latest(
                    times=peers.setdefault(node_id, {}).setdefault(relationship_name, {}),
                    key=str(element["peer_id"]),
                    changed_at=element_time,
                )
            _keep_latest(times=fields.setdefault(node_id, {}), key=relationship_name, changed_at=relationship_time)
    return DiffChangeTimes(
        from_time=datetime.fromisoformat(diff_tree["from_time"]),
        to_time=datetime.fromisoformat(diff_tree["to_time"]),
        nodes=nodes,
        fields=fields,
        peers=peers,
    )


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _latest(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None or second is None:
        return first or second
    return max(first, second)


def _keep_latest(*, times: dict[str, datetime], key: str, changed_at: datetime | None) -> None:
    latest = _latest(times.get(key), changed_at)
    if latest is not None:
        times[key] = latest


async def set_diff_summary_cache(pipeline_id: UUID, diff_summary: list[NodeDiff], cache: InfrahubCache) -> None:
    serialized = json.dumps(diff_summary)
    await cache.set(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
        value=serialized,
        expires=KVTTL.TWO_HOURS,
    )


async def get_diff_summary_cache(pipeline_id: UUID) -> list[NodeDiff]:
    cache = await get_cache()
    summary_payload = await cache.get(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
    )

    if not summary_payload:
        raise ResourceNotFoundError(message=f"Diff summary for pipeline {pipeline_id} was not found in the cache")

    return cast("list[NodeDiff]", json.loads(summary_payload))


def _diff_change_times_key(pipeline_id: UUID) -> str:
    return f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_change_times"


async def set_diff_change_times_cache(pipeline_id: UUID, change_times: DiffChangeTimes, cache: InfrahubCache) -> None:
    await cache.set(
        key=_diff_change_times_key(pipeline_id=pipeline_id),
        value=change_times.model_dump_json(),
        expires=KVTTL.TWO_HOURS,
    )


async def get_diff_change_times_cache(pipeline_id: UUID, cache: InfrahubCache) -> DiffChangeTimes | None:
    """Return the change times stored for a pipeline run, or None when the run stored none."""
    payload = await cache.get(key=_diff_change_times_key(pipeline_id=pipeline_id))
    if not payload:
        return None
    return DiffChangeTimes.model_validate_json(payload)
