"""Scope computed-attribute recompute to the schema elements that actually changed.

A schema update reports a set of changed elements (added/removed object types and,
per kind, the attribute/relationship names that changed). Each computed attribute
declares the schema elements its value reads (its dependency set). Recompute is
needed for an attribute only when its dependency set intersects the changed-element
set, when its own definition changed, or when its dependencies cannot be determined
precisely (the conservative "depends on everything" case).

The decision is pure: it reads only the structures passed in and performs no
database or network access, so it is unit-testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema.schema_branch_computed.python_transform import IMPRECISE_READ_FIELDS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.schema.schema_branch_computed import ComputedAttributeTriggerNode, TransformReadSet
    from infrahub.events.schema_action import ChangedElementsPayload


@dataclass(frozen=True)
class ChangedElementSet:
    """The schema elements a single schema update added, removed, or changed.

    Carries every element the diff reports as changed; there is no value-affecting
    or cosmetic filtering, so a label or description edit on a read element still
    counts as a change.
    """

    added_kinds: frozenset[str] = frozenset()
    removed_kinds: frozenset[str] = frozenset()
    changed_fields: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: ChangedElementsPayload) -> ChangedElementSet:
        return cls(
            added_kinds=frozenset(payload.added_kinds),
            removed_kinds=frozenset(payload.removed_kinds),
            changed_fields={kind: frozenset(fields) for kind, fields in payload.changed_fields.items()},
        )


@dataclass(frozen=True)
class ComputedAttributeRef:
    """Identity of a computed attribute, used for reporting and as a recompute key."""

    branch: str
    kind: str
    attribute_name: str
    computed_kind: ComputedAttributeKind


@dataclass(frozen=True)
class DependencySet:
    """The schema elements a single computed attribute's value reads.

    ``read_kinds`` and ``read_fields`` cover the owner kind and any related kinds
    reached through relationships at whatever depth the value expresses. The owner
    kind plus the attribute's own name are always part of the set so an edit to the
    attribute's own definition triggers recompute. ``depends_on_everything`` marks
    the conservative case where the read set cannot be determined precisely.
    """

    owner_kind: str
    attribute_name: str
    kind: ComputedAttributeKind
    read_kinds: frozenset[str] = frozenset()
    read_fields: Mapping[str, frozenset[str]] = field(default_factory=dict)
    depends_on_everything: bool = False


@dataclass(frozen=True)
class SkippedAttribute:
    """A computed attribute deliberately excluded from recompute, with the reason."""

    ref: ComputedAttributeRef
    reason: str


@dataclass(frozen=True)
class RecomputeScopingReport:
    """The outcome of scoping one schema change for one branch.

    ``selected`` and ``skipped`` are disjoint and together cover every candidate.
    ``fallback_full_recompute`` is ``True`` only when the change set was unavailable
    for the whole path; a per-attribute ``depends_on_everything`` does not set it.
    """

    selected: list[ComputedAttributeRef]
    skipped: list[SkippedAttribute]
    fallback_full_recompute: bool


class ComputedAttributeDependencyDeriver(Protocol):
    """Derive the dependency set for one kind of computed attribute."""

    def derive(
        self,
        *,
        computed_attribute: ComputedAttributeRef,
    ) -> DependencySet: ...


class RecomputeScoper:
    """Select the computed attributes that must be recomputed for a schema change.

    A per-kind deriver supplies each candidate's dependency set; the scoper
    intersects that set with the changed elements to decide selection.
    """

    def __init__(
        self,
        *,
        derivers: Mapping[ComputedAttributeKind, ComputedAttributeDependencyDeriver],
    ) -> None:
        self._derivers = derivers

    def scope(
        self,
        *,
        candidate_attributes: Sequence[ComputedAttributeRef],
        changed_elements: ChangedElementSet | None,
    ) -> RecomputeScopingReport:
        if changed_elements is None:
            return RecomputeScopingReport(
                selected=list(candidate_attributes),
                skipped=[],
                fallback_full_recompute=True,
            )

        affected_kinds = changed_elements.added_kinds | changed_elements.removed_kinds

        selected: list[ComputedAttributeRef] = []
        skipped: list[SkippedAttribute] = []

        for candidate in candidate_attributes:
            dependencies = self._derivers[candidate.computed_kind].derive(
                computed_attribute=candidate,
            )

            if dependencies.depends_on_everything:
                selected.append(candidate)
                continue

            if dependencies.read_kinds & affected_kinds:
                selected.append(candidate)
                continue

            if self._reads_changed_field(dependencies=dependencies, changed_elements=changed_elements):
                selected.append(candidate)
                continue

            if candidate.attribute_name in changed_elements.changed_fields.get(candidate.kind, frozenset()):
                selected.append(candidate)
                continue

            skipped.append(SkippedAttribute(ref=candidate, reason="no dependency on changed elements"))

        return RecomputeScopingReport(
            selected=selected,
            skipped=skipped,
            fallback_full_recompute=False,
        )

    @staticmethod
    def _reads_changed_field(
        *,
        dependencies: DependencySet,
        changed_elements: ChangedElementSet,
    ) -> bool:
        for kind, read_names in dependencies.read_fields.items():
            changed_names = changed_elements.changed_fields.get(kind)
            if changed_names and read_names & changed_names:
                return True
        return False


class PythonTransformDependencyDeriver:
    """Derive dependency sets for transform-based computed attributes.

    The read set of a transform comes from its GraphQL query, which is database
    data; it is pre-computed once per branch and injected so that derivation here
    is a pure lookup with no database access. An attribute whose read set is unknown
    (no entry) or imprecise is marked to always recompute.
    """

    def __init__(self, *, read_sets: Mapping[tuple[str, str, str], TransformReadSet]) -> None:
        self._read_sets = read_sets

    def derive(
        self,
        *,
        computed_attribute: ComputedAttributeRef,
    ) -> DependencySet:
        owner_kind = computed_attribute.kind
        attribute_name = computed_attribute.attribute_name
        own_field = {owner_kind: frozenset({attribute_name})}

        read_set = self._read_sets.get((computed_attribute.branch, owner_kind, attribute_name))
        if read_set is None or read_set.depends_on_everything:
            return DependencySet(
                owner_kind=owner_kind,
                attribute_name=attribute_name,
                kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                read_kinds=frozenset({owner_kind}),
                read_fields=own_field,
                depends_on_everything=True,
            )

        read_fields: dict[str, frozenset[str]] = {
            kind: frozenset(fields) for kind, fields in read_set.read_fields.items()
        }
        read_fields[owner_kind] = read_fields.get(owner_kind, frozenset()) | frozenset({attribute_name})

        return DependencySet(
            owner_kind=owner_kind,
            attribute_name=attribute_name,
            kind=ComputedAttributeKind.TRANSFORM_PYTHON,
            read_kinds=read_set.read_kinds | frozenset({owner_kind}),
            read_fields=read_fields,
            depends_on_everything=False,
        )


class Jinja2DependencyDeriver:
    """Derive dependency sets for Jinja2 template-based computed attributes.

    The read set comes from the Jinja2 dependency graph, indexed by owner attribute
    and supplied at construction so derivation is a pure lookup. It covers the fields
    the template reads on the owner kind plus the peer kinds and attributes reached
    through relationships, at the depth the graph expresses. An attribute that reads a
    derived field (such as a display label) or whose read set cannot be located is
    marked to always recompute.
    """

    def __init__(self, *, trigger_nodes: Mapping[tuple[str, str], list[ComputedAttributeTriggerNode]]) -> None:
        self._trigger_nodes = trigger_nodes

    def derive(
        self,
        *,
        computed_attribute: ComputedAttributeRef,
    ) -> DependencySet:
        owner_kind = computed_attribute.kind
        attribute_name = computed_attribute.attribute_name
        own_field = {owner_kind: frozenset({attribute_name})}

        trigger_nodes = self._trigger_nodes.get((owner_kind, attribute_name))
        if trigger_nodes is None:
            return DependencySet(
                owner_kind=owner_kind,
                attribute_name=attribute_name,
                kind=ComputedAttributeKind.JINJA2,
                read_kinds=frozenset({owner_kind}),
                read_fields=own_field,
                depends_on_everything=True,
            )

        read_kinds: set[str] = {owner_kind}
        read_fields: dict[str, frozenset[str]] = {}
        for trigger in trigger_nodes:
            fields = frozenset(trigger.attributes) | frozenset(trigger.relationships)
            if fields & IMPRECISE_READ_FIELDS:
                return DependencySet(
                    owner_kind=owner_kind,
                    attribute_name=attribute_name,
                    kind=ComputedAttributeKind.JINJA2,
                    read_kinds=frozenset({owner_kind}),
                    read_fields=own_field,
                    depends_on_everything=True,
                )
            read_kinds.add(trigger.kind)
            if fields:
                read_fields[trigger.kind] = read_fields.get(trigger.kind, frozenset()) | fields

        read_fields[owner_kind] = read_fields.get(owner_kind, frozenset()) | frozenset({attribute_name})

        return DependencySet(
            owner_kind=owner_kind,
            attribute_name=attribute_name,
            kind=ComputedAttributeKind.JINJA2,
            read_kinds=frozenset(read_kinds),
            read_fields=read_fields,
            depends_on_everything=False,
        )
