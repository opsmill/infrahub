from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager

from .diff import DiffChangelogCollector
from .enrichment import node_label_loader
from .models import RelationshipChangelogGetter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase

    from .diff import MigrationTracker


def build_diff_changelog_collector(
    diff: EnrichedDiffRoot, db: InfrahubDatabase, branch: Branch, migration_tracker: MigrationTracker | None = None
) -> DiffChangelogCollector:
    """Build a changelog collector whose label loader reads from the same database and branch."""
    return DiffChangelogCollector(
        diff=diff,
        db=db,
        branch=branch,
        label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
        migration_tracker=migration_tracker,
    )


def build_relationship_changelog_getter(db: InfrahubDatabase, branch: Branch) -> RelationshipChangelogGetter:
    """Build a relationship changelog getter whose label loader reads from the same database and branch."""
    return RelationshipChangelogGetter(
        db=db, branch=branch, label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many)
    )
