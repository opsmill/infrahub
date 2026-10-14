from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.repository_branch_status.reader import RepositoryBranchAttributesReader

if TYPE_CHECKING:
    from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
    from infrahub.database import InfrahubDatabase


def build_repository_branch_attributes_source(db: InfrahubDatabase) -> RepositoryBranchAttributesSource:
    """Build the source a caller reads a repository's per-branch attribute values from.

    Args:
        db: Database connection the source reads through.

    Returns:
        The attribute source.

    """
    return RepositoryBranchAttributesReader(
        db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME
    )
