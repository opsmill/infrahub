from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003  (pydantic needs it at runtime to read the JSON form)
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.graphql.cost.constants import NO_STATISTICS_REASON

if TYPE_CHECKING:
    from collections.abc import Mapping


class EstimateMode(StrEnum):
    """How the top-level nodes of an estimate were obtained; also the `estimate_mode` of the cost details."""

    COUNTED_FIRST_STEP = "counted_first_step"
    STATISTICS_ONLY = "statistics_only"


class EstimateSource(StrEnum):
    """Where the figures of one field come from; also the `source` of a field in the cost details."""

    COUNTED = "counted"
    STATISTICS = "statistics"


class EstimateReason(StrEnum):
    """Why a field has no estimate; also the `reason` of a field in the cost details."""

    NO_STATISTICS = NO_STATISTICS_REASON


@dataclass(frozen=True, slots=True)
class CostFigures:
    nodes: int
    resolver_calls: int
    database_rows: int

    def __post_init__(self) -> None:
        if min(self.nodes, self.resolver_calls, self.database_rows) < 0:
            raise ValueError(
                "Cost figures cannot be negative: "
                f"nodes={self.nodes}, resolver_calls={self.resolver_calls}, database_rows={self.database_rows}"
            )


@dataclass(frozen=True, slots=True)
class HistogramBucket:
    lower: int
    upper: int
    node_count: int
    """Nodes whose peer count is between `lower` and `upper`, both included."""

    max: int
    """Largest peer count among the nodes of this bucket."""


@dataclass(frozen=True, slots=True)
class TopNode:
    node_id: str
    peers: int


@dataclass(frozen=True, slots=True)
class RelationshipSideStatistics:
    identifier: str
    direction: RelationshipDirection
    """Direction of the edges, seen from a node of the kind that holds these statistics."""

    nodes_with_peers: int
    total_peers: int
    peers_by_kind: dict[str, int]
    """Total peers for each concrete peer kind."""

    histogram: tuple[HistogramBucket, ...]
    """Non-empty buckets only, in increasing order."""

    top_nodes: tuple[TopNode, ...]
    """Nodes with the most peers, in decreasing order of peers."""


@dataclass(frozen=True, slots=True)
class KindStatistics:
    kind: str
    label_count: int
    """Nodes carrying the kind label, deleted nodes and nodes of other branches included."""

    active_count: int
    """Nodes active on the default branch."""

    relationships: tuple[RelationshipSideStatistics, ...]

    def side(self, identifier: str, direction: RelationshipDirection) -> RelationshipSideStatistics | None:
        for relationship in self.relationships:
            if relationship.identifier == identifier and relationship.direction == direction:
                return relationship
        return None

    def to_json(self) -> str:
        return _KIND_STATISTICS_ADAPTER.dump_json(self).decode()

    @classmethod
    def from_json(cls, value: str | bytes) -> KindStatistics:
        return _KIND_STATISTICS_ADAPTER.validate_json(value)


@dataclass(frozen=True, slots=True)
class StatisticsPointer:
    version: int
    branch: str
    computed_at: datetime
    """Time the refresh started reading the branch."""

    schema_hash: str
    kinds: tuple[str, ...]
    """Concrete kinds that have an entry in this version."""

    def to_json(self) -> str:
        return _STATISTICS_POINTER_ADAPTER.dump_json(self).decode()

    @classmethod
    def from_json(cls, value: str | bytes) -> StatisticsPointer:
        return _STATISTICS_POINTER_ADAPTER.validate_json(value)


@dataclass(frozen=True, slots=True)
class StatisticsSnapshot:
    pointer: StatisticsPointer
    kinds: Mapping[str, KindStatistics]
    """Kinds whose entry was loaded, which can be fewer than the kinds of the pointer."""

    def side(self, identifier: str, direction: RelationshipDirection, kind: str) -> RelationshipSideStatistics | None:
        kind_statistics = self.kinds.get(kind)
        if kind_statistics is None:
            return None
        return kind_statistics.side(identifier=identifier, direction=direction)


_KIND_STATISTICS_ADAPTER = TypeAdapter(KindStatistics)
_STATISTICS_POINTER_ADAPTER = TypeAdapter(StatisticsPointer)


@dataclass(frozen=True, slots=True)
class RelationshipRef:
    identifier: str
    direction: RelationshipDirection
    name: str
    """Name of the relationship field on the parent's schema."""

    hierarchical: bool
    """True for the ancestors and descendants fields, which have no statistics."""


@dataclass(frozen=True, slots=True)
class CostTreeField:
    path: str
    """Response keys from the top-level field joined by '/', without edges, node and list indexes."""

    kind: str
    concrete_kinds: tuple[str, ...]
    """The kind itself, or the concrete kinds behind a generic."""

    parent_kinds: tuple[str, ...]
    """Concrete kinds of the parent nodes the field is selected on, narrowed by the inline fragments around it.

    Empty for a top-level field.
    """

    relationship: RelationshipRef | None
    """None for a top-level field."""

    cardinality: RelationshipCardinality
    selected_attribute_count: int
    selected_cardinality_one_count: int
    selects_count: bool
    selects_nodes: bool
    """False for a field of cardinality many that selects only its count, which reads no node."""

    id_only: bool
    """A cardinality-one field that selects only the id of its peer, which reads nothing."""

    max_matching_nodes: int | None
    """For a top-level field, the most nodes its filters can match: the number of IDs given, or one when the
    filters pin a single node; None when the filters set no such bound, and for every other field."""

    arguments: dict[str, Any]
    """Coerced argument values of the field."""

    children: tuple[CostTreeField, ...]

    def __post_init__(self) -> None:
        if self.relationship is None and self.cardinality != RelationshipCardinality.MANY:
            raise ValueError(f"The top-level field '{self.path}' must have cardinality many")
        if self.relationship is None and self.parent_kinds:
            raise ValueError(f"The top-level field '{self.path}' has no parent kinds")
        if self.relationship is not None and self.max_matching_nodes is not None:
            raise ValueError(f"Only a top-level field can bound its matching nodes: '{self.path}'")
        if self.selects_count and self.cardinality != RelationshipCardinality.MANY:
            raise ValueError(f"Only a field of cardinality many can select count: '{self.path}'")
        if not self.selects_nodes and (self.cardinality != RelationshipCardinality.MANY or self.children):
            raise ValueError(f"Only a field of cardinality many without children can skip its nodes: '{self.path}'")
        if self.id_only and self.cardinality != RelationshipCardinality.ONE:
            raise ValueError(f"Only a field of cardinality one can select only its id: '{self.path}'")


@dataclass(frozen=True, slots=True)
class FieldDescription:
    """Schema element behind one field of a query."""

    kind: str
    relationship_identifier: str | None
    """None for a top-level field."""

    cardinality: RelationshipCardinality


@dataclass(frozen=True, slots=True)
class FieldEstimate:
    field: FieldDescription
    expected: CostFigures | None
    worst_case: CostFigures | None
    source: EstimateSource | None
    worst_case_is_bound: bool
    """True only when the statistics describe the branch and time the query reads."""

    reason: EstimateReason | None

    def __post_init__(self) -> None:
        estimated_values = (self.expected, self.worst_case, self.source)
        if self.reason is not None:
            if any(value is not None for value in estimated_values) or self.worst_case_is_bound:
                raise ValueError("An estimate with a reason has no figures, no source and no bound")
        elif any(value is None for value in estimated_values):
            raise ValueError("An estimate without a reason has expected figures, worst-case figures and a source")


@dataclass(frozen=True, slots=True)
class QueryEstimate:
    mode: EstimateMode
    statistics: StatisticsPointer | None
    """None when no statistics exist yet."""

    estimates: Mapping[str, FieldEstimate]
    """Estimate of each field by path, in the order of the estimation tree."""


@dataclass(frozen=True, slots=True)
class FirstStepKindCount:
    kind: str
    node_count: int
    """Nodes of this concrete kind that the top-level field returns, after its filters, offset and limit."""

    node_ids: tuple[str, ...]
    """IDs of those nodes, at most the query size limit of them."""

    def __post_init__(self) -> None:
        if self.node_count < 0 or len(self.node_ids) > self.node_count:
            raise ValueError(
                f"{self.kind} has {len(self.node_ids)} node IDs for a count of {self.node_count}, "
                "the count must be at least the number of IDs"
            )


@dataclass(frozen=True, slots=True)
class FirstStepTopLevelCount:
    kinds: tuple[FirstStepKindCount, ...]
    """One entry for each concrete kind of the field that has nodes."""

    exceeds_size_limit: bool
    """The field returns more nodes than the query size limit, so no field under it is counted."""


@dataclass(frozen=True, slots=True)
class FirstStepPeerCount:
    peer_kind: str
    paths: int
    """Pairs of a top-level node and one of its peers of this concrete kind, read with the filters of the field
    but without its offset and limit."""

    distinct_peers: int
    max_parents: int
    """Largest number of top-level nodes that reach one peer of this kind."""

    def __post_init__(self) -> None:
        if not 0 <= self.max_parents <= self.paths or not 0 <= self.distinct_peers <= self.paths:
            raise ValueError(
                f"Inconsistent peer counts for {self.peer_kind}: paths={self.paths}, "
                f"distinct_peers={self.distinct_peers}, max_parents={self.max_parents}"
            )


@dataclass(frozen=True, slots=True)
class FirstStepCounts:
    """Counts read on the branch and at the time of the request, for the first step of a query.

    The first step is the top-level fields and the relationship fields directly under them. Everything
    below it is estimated from the statistics.
    """

    top_level: Mapping[str, FirstStepTopLevelCount]
    """Counts of each top-level field, by path."""

    relationships: Mapping[str, tuple[FirstStepPeerCount, ...]]
    """Counts of each relationship field directly under a counted top-level field, by path, one entry for each
    concrete peer kind. Only the top-level nodes of the parent kinds of the field are counted, and a field under
    a top-level field that exceeds the size limit has no entry."""

    label_counts: Mapping[str, int]
    """Current label count of each kind in the query, read by the same queries."""
