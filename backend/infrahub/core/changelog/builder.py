from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager

from .diff import DiffChangelogCollector
from .enrichment import NodeLabelLoader, node_label_loader
from .hfid_resolver import ChangelogHfidResolver
from .peer_labels import PeerLabelResolver
from .reciprocal import ReciprocalRelationshipBuilder
from .relationship_getter import RelationshipChangelogGetter
from .secondary_merger import SecondaryChangelogMerger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase

    from .diff import MigrationTracker


def build_node_label_loader(db: InfrahubDatabase, branch: Branch) -> NodeLabelLoader:
    """Build a label loader that reads node labels from the same database and branch."""
    return node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many)


def build_diff_changelog_collector(
    diff: EnrichedDiffRoot, db: InfrahubDatabase, branch: Branch, migration_tracker: MigrationTracker | None = None
) -> DiffChangelogCollector:
    """Build a changelog collector whose HFID resolver reads from the same database and branch."""
    label_loader = build_node_label_loader(db=db, branch=branch)
    return DiffChangelogCollector(
        diff=diff,
        db=db,
        branch=branch,
        hfid_resolver=ChangelogHfidResolver(label_loader=label_loader),
        migration_tracker=migration_tracker,
    )


def build_relationship_changelog_getter(db: InfrahubDatabase, branch: Branch) -> RelationshipChangelogGetter:
    """Build a relationship changelog getter whose peer labels are read from the same database and branch."""
    label_loader = build_node_label_loader(db=db, branch=branch)
    return RelationshipChangelogGetter(
        db=db,
        branch=branch,
        peer_label_resolver=PeerLabelResolver(label_loader=label_loader),
        reciprocal_builder=ReciprocalRelationshipBuilder(),
        merger=SecondaryChangelogMerger(),
    )
