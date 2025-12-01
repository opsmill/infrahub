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
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.graphql.models import OrderModel

from .. import config
from .models import RepositoryBranchInfo, RepositoryData


async def get_repositories_commit_per_branch(
    db: InfrahubDatabase,
    kind: str = InfrahubKind.GENERICREPOSITORY,
) -> dict[str, RepositoryData]:
    """Get a list of all repositories and their commit on each branches.

    This method is similar to 'get_list_repositories' method in the Python SDK.

    NOTE: At some point, we should refactor this function to use a single Database query instead of one per branch
    """

    repositories: dict[str, RepositoryData] = {}

    for branch in list(registry.branch.values()):
        repos: list[CoreRepository | CoreReadOnlyRepository] = await NodeManager.query(
            db=db,
            branch=branch,
            fields={"id": None, "name": None, "commit": None, "internal_status": None, "location": None, "ref": None},
            schema=kind,
            order=OrderModel(disable=True),
        )

        for repository in repos:
            repo_name = repository.name.value
            if repo_name not in repositories:
                repositories[repo_name] = RepositoryData(
                    repository_id=repository.get_id(),
                    repository_name=repo_name,
                    repository=repository,
                    branches={},
                )

            repositories[repo_name].branches[branch.name] = repository.commit.value
            repositories[repo_name].branch_info[branch.name] = RepositoryBranchInfo(
                internal_status=repository.internal_status.value
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
