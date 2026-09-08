"""Temporary source of placeholder repository attribute values.

The values served here are fabricated from the branch name so that they stay stable across
requests, which lets the query around them be built and tested before the graph read exists.
A source that resolves the values from the graph will take over, and this module will be
deleted at that point.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from infrahub.core.constants import RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.query.repository import RepositoryBranchAttributeValue
from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
from infrahub.core.repository_branch_status.models import RepositoryBranchAttributes
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from infrahub.core.timestamp import Timestamp

log = get_logger()

PLACEHOLDER_UPDATED_AT = "2026-01-01T00:00:00.000000Z"

_SYNC_STATUS_VALUES = tuple(status.value for status in RepositorySyncStatus)
_REF_VALUE = "main"
_ATTRIBUTE_ID_SEED = "infrahub/repository-branch-status/placeholder"

log.warning(
    "infrahub.graphql.queries.repository_branch_status.stub is loaded: "
    "the repository attribute values it serves are placeholders, not read from the graph"
)


def fabricate_attribute_values(
    repository_id: str,
    branch_name: str,
    attribute_names: Collection[str],
    is_default_branch: bool,
) -> list[RepositoryBranchAttributeValue]:
    """Derive placeholder attribute values for one repository on one branch.

    Args:
        repository_id: UUID of the repository node.
        branch_name: Name of the branch to derive the values from.
        attribute_names: Names of the attributes to fabricate; unknown names are skipped.
        is_default_branch: Whether the branch is the default branch.

    Returns:
        One value per known requested attribute name, identical for identical arguments.

    """
    digest = _name_digest(name=branch_name)
    name_hash = int(digest, 16)
    internal_status = (
        RepositoryInternalStatus.ACTIVE.value if is_default_branch else RepositoryInternalStatus.INACTIVE.value
    )
    values: dict[str, str] = {
        "commit": digest,
        "sync_status": _SYNC_STATUS_VALUES[name_hash % len(_SYNC_STATUS_VALUES)],
        "internal_status": internal_status,
        "ref": _REF_VALUE,
    }
    own_value = is_default_branch or name_hash % 2 == 1

    return [
        RepositoryBranchAttributeValue(
            repository_id=repository_id,
            branch_name=branch_name,
            attribute_name=attribute_name,
            attribute_id=_attribute_id(
                repository_id=repository_id, branch_name=branch_name, attribute_name=attribute_name
            ),
            value=values[attribute_name],
            own_value=own_value,
            updated_at=PLACEHOLDER_UPDATED_AT,
        )
        for attribute_name in sorted(attribute_names)
        if attribute_name in values
    ]


class StubRepositoryBranchAttributesSource(RepositoryBranchAttributesSource):
    """Attribute source serving placeholder values instead of reading the graph."""

    def __init__(self, default_branch_name: str) -> None:
        self.default_branch_name = default_branch_name

    async def read(
        self,
        repository_ids: Sequence[str],
        branch_names: Sequence[str],
        attribute_names: Collection[str],
        at: Timestamp | None = None,  # noqa: ARG002
    ) -> RepositoryBranchAttributes:
        """Fabricate the requested attributes for each repository on each branch.

        Args:
            repository_ids: UUIDs of the repository nodes to serve.
            branch_names: Names of the branches to serve the attributes for.
            attribute_names: Names of the attributes to serve.
            at: Accepted for interface compatibility; placeholder values do not vary over time.

        Returns:
            A lookup holding one placeholder value per repository, branch and known attribute name.

        """
        log.debug(
            "Serving placeholder repository attribute values",
            repository_count=len(repository_ids),
            branch_count=len(branch_names),
            attribute_names=sorted(attribute_names),
        )
        values: list[RepositoryBranchAttributeValue] = []
        for repository_id in repository_ids:
            for branch_name in branch_names:
                values.extend(
                    fabricate_attribute_values(
                        repository_id=repository_id,
                        branch_name=branch_name,
                        attribute_names=attribute_names,
                        is_default_branch=branch_name == self.default_branch_name,
                    )
                )
        return RepositoryBranchAttributes.from_values(values=values)


def _name_digest(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8"), usedforsecurity=False).hexdigest()


def _attribute_id(repository_id: str, branch_name: str, attribute_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{_ATTRIBUTE_ID_SEED}/{repository_id}/{branch_name}/{attribute_name}"))
