from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Argument, Boolean, Field, Int, String

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.repository_branch_status.reader import RepositoryBranchAttributesReader
from infrahub.graphql.types.enums import InfrahubBranchStatus
from infrahub.graphql.types.metadata import MetadataOrderInput
from infrahub.graphql.types.repository_branch_status import InfrahubRepositoryBranchStatusType

from .resolver import RepositoryBranchStatusResolver

if TYPE_CHECKING:
    from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
    from infrahub.database import InfrahubDatabase

_DESCRIPTION = (
    "Status of one repository as seen from every relevant branch, one row per branch. "
    "Resolved entirely from the graph; never contacts a task worker. "
    "Requires view permission on the repository's kind covering both the default and non-default "
    "branches (ALLOW_ALL, or ALLOW_DEFAULT plus ALLOW_OTHER)."
)


def build_attribute_source(db: InfrahubDatabase) -> RepositoryBranchAttributesSource:
    """Build the source the resolver reads the repository's per-branch attribute values from.

    Args:
        db: Database connection the source reads through.

    Returns:
        The attribute source.

    """
    return RepositoryBranchAttributesReader(
        db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME
    )


InfrahubRepositoryBranchStatus = Field(
    InfrahubRepositoryBranchStatusType,
    required=True,
    id=String(required=True, description="Repository id (uuid) or name"),
    limit=Int(default_value=40),
    offset=Int(default_value=0),
    name__value=String(description="Branch name filter; exact unless partial_match is true"),
    partial_match=Boolean(default_value=False),
    status__value=Argument(
        InfrahubBranchStatus,
        description="Branch status filter; MERGED and DELETING branches are never returned",
    ),
    order=Argument(
        MetadataOrderInput,
        description="Ordering by branch node metadata; default is default branch first, then name ascending",
    ),
    sync_status__value=String(description="Keep rows whose resolved sync_status value equals this value (server-side)"),
    internal_status__value=String(
        description="Keep rows whose resolved internal_status value equals this value (server-side)"
    ),
    own_values_only=Boolean(
        default_value=False,
        description=(
            "Keep only branches holding their own commit value (imported on this branch), "
            "independent of the selected fields"
        ),
    ),
    resolver=RepositoryBranchStatusResolver(build_source=build_attribute_source),
    description=_DESCRIPTION,
)
