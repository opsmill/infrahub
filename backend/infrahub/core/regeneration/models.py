from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Any, Protocol, assert_never

if TYPE_CHECKING:
    from infrahub.core.constants import RelationshipDirection

type FilterLiteral = str | int | bool | tuple[str | int | bool, ...]


@dataclass(frozen=True, slots=True)
class ExcludedChange:
    """A changed field of one node that no read of the query can see, so it selects no target."""

    node_id: str
    field_name: str


@dataclass(frozen=True, slots=True)
class PeerFilters:
    """The filters a relationship read applies to its peers, keyed as the peer query takes them.

    Each key starts with ``relationship_name``, and list values are stored as tuples.
    """

    relationship_name: str
    filters: tuple[tuple[str, FilterLiteral], ...]

    @property
    def filtered_fields(self) -> frozenset[str]:
        """The peer fields the filters test; ``id`` and ``ids`` test none, as an id never changes."""
        names = (key.removeprefix(f"{self.relationship_name}__") for key, _ in self.filters)
        return frozenset(name.split("__", maxsplit=1)[0] for name in names if "__" in name)

    def as_query_filters(self) -> dict[str, Any]:
        """The filters in the shape the peer query takes them."""
        return {key: list(value) if isinstance(value, tuple) else value for key, value in self.filters}


@dataclass(frozen=True, slots=True)
class RelationshipHop:
    """One relationship hop, expressed from the owner object that carries the relationship.

    ``node_kind`` owns ``relationship_identifier``; ``relationship_direction`` is that relationship's
    direction on the owner. ``peer_filters`` are the filters of the read the hop comes from; None means
    every peer is read.
    """

    node_kind: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection
    peer_filters: PeerFilters | None = None


@dataclass(frozen=True, slots=True)
class RelationshipRead:
    """One read of a relationship in a query.

    ``peer_filters`` is None when the read has no filter or its filters are unknown.
    """

    owner_kind: str
    relationship_name: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection
    peer_kinds: frozenset[str]
    peer_filters: PeerFilters | None

    @property
    def hop(self) -> RelationshipHop:
        """The read as a hop from its owner."""
        return RelationshipHop(
            node_kind=self.owner_kind,
            relationship_identifier=self.relationship_identifier,
            relationship_direction=self.relationship_direction,
            peer_filters=self.peer_filters,
        )


@dataclass(frozen=True, slots=True)
class ReachedPath:
    """The relationship chain a query follows from a root object down to a related kind.

    An empty chain stands for a read at the root itself, so a changed node maps to its own member.
    """

    hops: tuple[RelationshipHop, ...]


class WideningReason(StrEnum):
    """Why a change could not be traced back to specific targets."""

    NON_UNIQUE_TARGETS = "non_unique_targets"
    RELATIONSHIP_REACHED_CHANGE = "relationship_reached_change"
    UNSCOPABLE_DERIVED_READ = "unscopable_derived_read"


@dataclass(frozen=True, kw_only=True, slots=True)
class Widening:
    """The reason narrowing was abandoned, with the changed kinds it applies to when there are any."""

    reason: WideningReason
    kinds: tuple[str, ...] = ()

    @property
    def detail(self) -> str:
        """The clause explaining the widening to the task log."""
        match self.reason:
            case WideningReason.NON_UNIQUE_TARGETS:
                return "the query does not guarantee unique targets"
            case WideningReason.RELATIONSHIP_REACHED_CHANGE:
                return (
                    f"the query reads {', '.join(self.kinds)} through a relationship, "
                    "and a change there cannot be traced back to specific targets"
                )
            case WideningReason.UNSCOPABLE_DERIVED_READ:
                return (
                    "the query reads a human_friendly_id or display_label whose value "
                    "cannot be traced back to specific targets"
                )
            case _ as unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class TargetSelection:
    """The targets to process, and why narrowing had to be abandoned to arrive at them, if it was.

    ``ids`` is always the authoritative, complete list, so a caller needs nothing else to act.
    ``widening`` explains only how that list was reached -- it carries no meaning of its own and
    exists so a caller can report the lost precision without re-deriving it.
    """

    ids: list[str]
    widening: Widening | None = None


class RegenerationReason(StrEnum):
    """The machine-comparable cause a definition was selected, or its closure could not be trusted."""

    QUERY_CHANGED = "query_changed"
    DEFINITION_CHANGED = "definition_changed"
    FILE_IN_CLOSURE = "file_in_closure"
    MISSING_FINGERPRINT = "missing_fingerprint"
    DEPENDENCIES_NULL = "dependencies_null"
    DEPENDENCIES_INCOMPLETE = "dependencies_incomplete"


@dataclass(frozen=True, kw_only=True, slots=True)
class RegenerationTrigger:
    """A regeneration cause paired with the human-readable line explaining it.

    ``code`` is the machine-comparable reason; ``detail`` is the sentence emitted to the
    task log. Pairing them keeps the classification and its explanation together so the
    caller can log the detail without re-deriving why the trigger fired.
    """

    code: RegenerationReason
    detail: str


@dataclass(frozen=True, kw_only=True, slots=True)
class PredicateOutcome:
    """The verdict of a regeneration predicate plus the trigger explaining it.

    ``matched`` drives the selection gate; ``trigger`` carries the reason code and the
    human-readable line the gate emits to the task log when the predicate fires. Keeping the
    explanation on the verdict lets the predicate stay a pure function - it is computed where
    the triggering field/file is known - while logging is the caller's responsibility.
    """

    matched: bool
    trigger: RegenerationTrigger | None = None

    @property
    def reason(self) -> str | None:
        """The human-readable line to log, or None when the predicate did not fire."""
        return self.trigger.detail if self.trigger is not None else None


class RegenerationDefinition(Protocol):
    """The fields and diagnostic nouns the regeneration predicates read off a definition.

    Both the artifact-definition and generator-definition pipeline models satisfy this
    structurally, so the same predicates evaluate either kind without branching on type.
    ``source_noun`` / ``instance_noun`` supply the kind-correct wording for the reason strings.
    """

    definition_id: str
    definition_name: str
    query_id: str
    query_name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None

    @property
    def source_noun(self) -> str: ...

    @property
    def instance_noun(self) -> str: ...


class DefinitionSelect(IntFlag):
    NONE = 0
    MODIFIED_KINDS = 1
    FILE_CHANGES = 2
    QUERY_CHANGED = 4
    DEFINITION_CHANGED = 8
    BRANCH_ARTIFACTS = 16

    @staticmethod
    def add_flag(current: DefinitionSelect, flag: DefinitionSelect, condition: bool) -> DefinitionSelect:
        if condition:
            return current | flag
        return current

    @property
    def log_line(self) -> str:
        change_types = []
        if DefinitionSelect.MODIFIED_KINDS in self:
            change_types.append("data changes within relevant object kinds")

        if DefinitionSelect.QUERY_CHANGED in self:
            change_types.append("changes to the GraphQL query")

        if DefinitionSelect.DEFINITION_CHANGED in self:
            change_types.append("changes to the definition")

        if DefinitionSelect.FILE_CHANGES in self:
            change_types.append("file changes affecting the transform's dependencies")

        if DefinitionSelect.BRANCH_ARTIFACTS in self:
            change_types.append("artifacts rendered on the branch")

        if self:
            return f"Requesting generation due to {' and '.join(change_types)}"

        return "Doesn't require changes due to no relevant modified kinds or file changes in Git"
