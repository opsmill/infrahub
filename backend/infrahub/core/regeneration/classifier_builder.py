from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .derived_dependencies import DerivedFieldDependencyResolver
from .impact_classifier import QueryImpactClassifier
from .models import ReachedPath

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.analyzer import ObjectAccess

    from .derived_dependencies import DerivedFieldDependencies


class AnalyzedQuery(Protocol):
    """The read surface an analyzed GraphQL query exposes for impact classification.

    ``requested_read`` maps each read kind to the attributes and relationships the query reads off
    it; ``traversed_kinds`` are the kinds reached through a relationship, including any also read at
    a root, so the overlap stays visible; ``relationship_reached_paths_by_kind`` the chains back from
    each to a root. ``only_has_unique_targets`` is true when the query pins one object per root.
    """

    @property
    def requested_read(self) -> Mapping[str, ObjectAccess]: ...

    @property
    def only_has_unique_targets(self) -> bool: ...

    @property
    def traversed_kinds(self) -> set[str]: ...

    @property
    def relationship_reached_paths_by_kind(self) -> dict[str, tuple[ReachedPath, ...]]: ...


class QueryClassifierBuilder:
    """Build a query's impact classifier from its analyzed read surface, on one branch."""

    def __init__(self, *, query_branch: str, schema_branch: SchemaBranch) -> None:
        self._query_branch = query_branch
        self._dependency_resolver = DerivedFieldDependencyResolver(schema_branch=schema_branch)

    def build(self, query_report: AnalyzedQuery) -> QueryImpactClassifier:
        readable_fields_by_kind = {kind: access.fields for kind, access in query_report.requested_read.items()}
        dependencies = self._dependency_resolver.resolve(readable_fields_by_kind)
        return self.build_query_classifier(
            only_has_unique_targets=query_report.only_has_unique_targets,
            readable_fields_by_kind=readable_fields_by_kind,
            traversed_kinds=query_report.traversed_kinds,
            reached_paths_by_kind=query_report.relationship_reached_paths_by_kind,
            dependencies=dependencies,
        )

    def build_query_classifier(
        self,
        *,
        only_has_unique_targets: bool,
        readable_fields_by_kind: Mapping[str, set[str]],
        traversed_kinds: set[str],
        reached_paths_by_kind: Mapping[str, tuple[ReachedPath, ...]],
        dependencies: DerivedFieldDependencies,
    ) -> QueryImpactClassifier:
        """Build the query's impact classifier, folding derived-field peer dependencies into its inputs.

        A peer the query does not otherwise read becomes a traversed kind with its backing field and the
        chain back to the reading member, so a change to it narrows precisely. When the query already
        reaches that peer in a way that cannot itself be narrowed, the derived chain alone would miss those
        readers, so the whole query widens to every target instead. A peer whose reading kind is itself
        relationship-reached carries a chain that stops at the reading kind, so it is extended with that kind's
        chains back to the root.
        """
        merged_readable = {kind: set(fields) for kind, fields in readable_fields_by_kind.items()}
        merged_traversed = set(traversed_kinds)
        merged_reached = dict(reached_paths_by_kind)
        widen = dependencies.widen
        for peer in dependencies.peers:
            already_traversed = peer.kind in traversed_kinds
            read_at_root = peer.kind in readable_fields_by_kind and not already_traversed
            if read_at_root or (already_traversed and peer.kind not in reached_paths_by_kind):
                # The query already reaches this peer with no chain that narrows -- read at a root, or
                # traversed without a resolvable path -- so the derived chain alone would miss readers.
                widen = True
                continue
            if peer.reading_kind in traversed_kinds:
                # The reading kind is itself relationship-reached, so the peer chain stops at it; carry
                # it on through each of the reading kind's chains to reach the root members.
                reading_paths = reached_paths_by_kind.get(peer.reading_kind)
                if not reading_paths:
                    # The reading kind is reached but its own chain to the root is unknown, so the peer
                    # cannot be mapped to a member either.
                    widen = True
                    continue
                peer_paths = tuple(
                    ReachedPath(hops=peer.path.hops + reading_path.hops) for reading_path in reading_paths
                )
            else:
                # The reading kind is a root, so the peer chain already lands on the reading member.
                peer_paths = (peer.path,)
            merged_traversed.add(peer.kind)
            merged_readable.setdefault(peer.kind, set()).add(peer.field_name)
            merged_reached[peer.kind] = merged_reached.get(peer.kind, ()) + peer_paths

        return QueryImpactClassifier(
            query_branch=self._query_branch,
            only_has_unique_targets=only_has_unique_targets,
            traversed_kinds=merged_traversed,
            readable_fields_by_kind=merged_readable,
            reached_paths_by_kind=merged_reached,
            depends_on_everything=widen,
        )
