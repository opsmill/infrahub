from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from infrahub.core.constants import RelationshipDirection


@dataclass(frozen=True, slots=True)
class RelationshipHop:
    """One relationship step, expressed from the owner object that carries the relationship.

    ``node_kind`` owns ``relationship_identifier``; ``relationship_direction`` is that relationship's
    direction on the owner.
    """

    node_kind: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection


@dataclass(frozen=True, slots=True)
class ReachedPath:
    """The relationship chain a query follows from a root object down to a related kind."""

    hops: tuple[RelationshipHop, ...]


@dataclass(frozen=True, slots=True)
class TargetSelection:
    """The targets to process, and whether narrowing had to be abandoned to arrive at them.

    ``ids`` is always the authoritative, complete list, so a caller needs nothing else to act.
    ``widened`` explains only how that list was reached -- it carries no meaning of its own and
    exists so a caller can report the lost precision without re-deriving it.
    """

    ids: list[str]
    widened: bool


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
    query_models: list[str]
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

        if self:
            return f"Requesting generation due to {' and '.join(change_types)}"

        return "Doesn't require changes due to no relevant modified kinds or file changes in Git"
