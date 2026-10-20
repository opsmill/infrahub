from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

_SHARED_ATTRIBUTE_NAMES = frozenset({"commit", "sync_status", "internal_status"})


@dataclass(frozen=True)
class RepositoryKindPolicy:
    """Everything the cross-branch status read decides from the repository's concrete kind."""

    kind: str
    """Concrete repository kind the policy applies to."""

    sync_with_git_filter: bool | None
    """Value the branch list is filtered on; None means every branch is in scope."""

    attribute_names: frozenset[str]
    """Attribute names this kind can report."""

    permission_name: str
    """Name of the object permission guarding the kind, within the Core namespace."""


REPOSITORY_KIND_POLICIES: Mapping[str, RepositoryKindPolicy] = MappingProxyType(
    {
        InfrahubKind.REPOSITORY: RepositoryKindPolicy(
            kind=InfrahubKind.REPOSITORY,
            sync_with_git_filter=True,
            attribute_names=_SHARED_ATTRIBUTE_NAMES,
            permission_name="Repository",
        ),
        InfrahubKind.READONLYREPOSITORY: RepositoryKindPolicy(
            kind=InfrahubKind.READONLYREPOSITORY,
            sync_with_git_filter=None,
            attribute_names=_SHARED_ATTRIBUTE_NAMES | {"ref"},
            permission_name="ReadOnlyRepository",
        ),
    }
)


def policy_for_kind(kind: str) -> RepositoryKindPolicy:
    """Return the policy for a concrete repository kind.

    Args:
        kind: Concrete kind of the resolved repository node.

    Returns:
        The policy for that kind.

    Raises:
        ValidationError: If the kind has no policy, which would otherwise yield a partial row set.

    """
    policy = REPOSITORY_KIND_POLICIES.get(kind)
    if policy is None:
        raise ValidationError(
            input_value=f"Repository kind '{kind}' is not supported by the repository branch status query"
        )
    return policy
