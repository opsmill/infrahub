import itertools
import re
from collections import defaultdict
from typing import Any

from infrahub_sdk import InfrahubClient
from infrahub_sdk.node import RelationshipManager
from infrahub_sdk.protocols import (
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreGroup,
    CoreReadOnlyRepository,
    CoreRepository,
)
from infrahub_sdk.types import Order

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.order import OrderModel
from infrahub.core.repository_branch_status.factory import build_repository_branch_attributes_source
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.log import get_logger

from .. import config
from .constants import REPOSITORY_BRANCH_READ_CHUNK_SIZE
from .models import RepositoryBranchInfo, RepositoryData

log = get_logger("infrahub.git")


async def get_repositories_commit_per_branch(
    db: InfrahubDatabase,
    kind: str = InfrahubKind.GENERICREPOSITORY,
) -> dict[str, RepositoryData]:
    """Get a list of all repositories and their commit on each branch.

    The repository nodes come from one read on the default branch, so every field read off a node
    carries the default branch's value. `commit` and `internal_status` are additionally resolved per
    branch, in fixed-size chunks of branch names, so the read costs a small fixed number of queries
    for the nodes plus one per chunk rather than one per branch. Every query resolves at the same
    point in time, so a write landing mid-read cannot leave one branch of a repository reporting the
    old commit and another the new one. The global branch is never a key of the result.

    Args:
        db: Database connection instance.
        kind: Repository kind to read; the generic covers both repository kinds.

    Returns:
        One entry per repository, keyed by repository name.

    """
    reader = build_repository_branch_attributes_source(db=db)
    at = Timestamp()

    repos: list[CoreRepository | CoreReadOnlyRepository] = await NodeManager.query(
        db=db,
        branch=registry.default_branch,
        at=at,
        fields={
            "id": None,
            "name": None,
            "commit": None,
            "internal_status": None,
            "location": None,
            "ref": None,
            "default_branch": None,
        },
        schema=kind,
        order=OrderModel(disable=True),
    )

    repositories: dict[str, RepositoryData] = {
        repository.name.value: RepositoryData(
            repository_id=repository.get_id(),
            repository_name=repository.name.value,
            repository=repository,
            branches={},
        )
        for repository in repos
    }
    if not repositories:
        return repositories

    repository_ids = [repository_data.repository_id for repository_data in repositories.values()]
    branch_names = [name for name in registry.branch if name != GLOBAL_BRANCH_NAME]

    branches_without_internal_status: dict[str, list[str]] = defaultdict(list)

    for chunk in itertools.batched(branch_names, REPOSITORY_BRANCH_READ_CHUNK_SIZE):
        attributes = await reader.read(
            repository_ids=repository_ids,
            branch_names=chunk,
            attribute_names=("commit", "internal_status"),
            at=at,
        )
        for repository_name, repository_data in repositories.items():
            for branch_name in chunk:
                commit = attributes.get(
                    repository_id=repository_data.repository_id,
                    branch_name=branch_name,
                    attribute_name="commit",
                )
                repository_data.branches[branch_name] = commit.value if commit is not None else None

                internal_status = attributes.get(
                    repository_id=repository_data.repository_id,
                    branch_name=branch_name,
                    attribute_name="internal_status",
                )
                internal_status_value = internal_status.value if internal_status is not None else None
                if internal_status_value is None:
                    internal_status_value = RepositoryInternalStatus.INACTIVE.value
                    branches_without_internal_status[repository_name].append(branch_name)
                repository_data.branch_info[branch_name] = RepositoryBranchInfo(internal_status=internal_status_value)

    for repository_name, unresolved_branches in branches_without_internal_status.items():
        log.warning(
            "No internal status resolved for the repository on some branches, using the fallback",
            repository=repository_name,
            branches=unresolved_branches,
            fallback_internal_status=RepositoryInternalStatus.INACTIVE.value,
        )

    return repositories


def _collect_parameter_first_segments(params: Any) -> set[str]:
    segments: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            segment = value.split("__", 1)[0]
            if segment:
                segments.add(segment)
        elif isinstance(value, dict):
            for nested in value.values():
                _walk(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                _walk(nested)

    _walk(params)
    return segments


async def _prefetch_group_member_nodes(
    client: InfrahubClient,
    members: RelationshipManager,
    branch: str,
    required_fields: set[str],
) -> None:
    ids_per_kind: dict[str, set[str]] = defaultdict(set)
    for peer in members.peers:
        if peer.id and peer.typename:
            ids_per_kind[peer.typename].add(peer.id)

    if not ids_per_kind:
        return

    batch = await client.create_batch()

    for kind, ids in ids_per_kind.items():
        schema = await client.schema.get(kind=kind, branch=branch)

        # FIXME: https://github.com/opsmill/infrahub-sdk-python/pull/205
        valid_fields = set(schema.attribute_names) | set(schema.relationship_names)
        keep_relationships = set(schema.relationship_names) & required_fields
        cleaned_fields = valid_fields - required_fields

        kwargs: dict[str, Any] = {
            "kind": kind,
            "ids": list(ids),
            "branch": branch,
            "exclude": list(cleaned_fields),
            "populate_store": True,
            "order": Order(disable=True),
        }

        if keep_relationships:
            kwargs["include"] = list(keep_relationships)

        batch.add(task=client.filters, **kwargs)

    async for _ in batch.execute():
        pass


async def _fetch_definition_targets(
    client: InfrahubClient,
    branch: str,
    group_id: str,
    parameters: Any,
) -> CoreGroup:
    group = await client.get(
        kind=CoreGroup,
        id=group_id,
        branch=branch,
        include=["members"],
    )

    parameter_fields = _collect_parameter_first_segments(parameters)
    await _prefetch_group_member_nodes(
        client=client,
        members=group.members,
        branch=branch,
        required_fields=parameter_fields,
    )

    return group


async def fetch_artifact_definition_targets(
    client: InfrahubClient,
    branch: str,
    definition: CoreArtifactDefinition,
) -> CoreGroup:
    return await _fetch_definition_targets(
        client=client, branch=branch, group_id=definition.targets.id, parameters=definition.parameters.value
    )


async def fetch_check_definition_targets(
    client: InfrahubClient,
    branch: str,
    definition: CoreCheckDefinition,
) -> CoreGroup:
    return await _fetch_definition_targets(
        client=client, branch=branch, group_id=definition.targets.id, parameters=definition.parameters.value
    )


async def fetch_proposed_change_generator_definition_targets(
    client: InfrahubClient,
    branch: str,
    definition: ProposedChangeGeneratorDefinition,
) -> CoreGroup:
    return await _fetch_definition_targets(
        client=client, branch=branch, group_id=definition.group_id, parameters=definition.parameters
    )


def branch_name_in_import_sync_branches(branch_short_name: str) -> bool:
    for branch_filter in config.SETTINGS.git.import_sync_branch_names:
        if re.fullmatch(branch_filter, branch_short_name) or branch_filter == branch_short_name:
            return True
    return False
