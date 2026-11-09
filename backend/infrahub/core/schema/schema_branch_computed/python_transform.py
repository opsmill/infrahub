"""Registry for Python transform-based computed attributes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.schema import AttributeSchema  # noqa: TC001
from infrahub.core.schema.derived_path import ScopedToReadingKind

if TYPE_CHECKING:
    from collections.abc import Container, Iterable, Mapping

    from infrahub.core.schema import MainSchemaTypes, NodeSchema
    from infrahub.core.schema.derived_path import DerivedPathResolver

# Reads of these computed/derived fields cannot be mapped back to a precise set of backing
# schema elements, so any change to the kind read through them can move the value: editing a
# display_label template moves every label with no data change.
# Data-change triggers do filter on them by name. Schema names, not the GraphQL spelling.
IMPRECISE_READ_FIELDS = frozenset({"display_label", "human_friendly_id"})


def derived_read_is_scopable(
    *, path_resolver: DerivedPathResolver, node_schema: MainSchemaTypes, field_name: str
) -> bool:
    """Whether a derived read on a kind can be held against that kind alone.

    A derived path that crosses a relationship reads a peer's attribute, so a schema change to
    the peer moves the value while nothing on this kind changes. Only a definition built from
    this kind's own attributes keeps every input under this kind, where the changed-element set
    reports it. Anything else, including a kind with no definition to inspect, has to stay
    conservative and recompute on any schema change.
    """
    paths = node_schema.get_derived_field_paths(field_name)
    if not paths:
        return False

    return all(
        isinstance(path_resolver.resolve(reading_schema=node_schema, path=path), ScopedToReadingKind) for path in paths
    )


@dataclass
class PythonDefinition:
    kind: str
    attribute: AttributeSchema

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"


@dataclass(frozen=True)
class TransformReadSet:
    """The schema elements a transform's GraphQL query reads.

    ``depends_on_everything`` is set when nothing about the query could be mapped.
    ``imprecise_kinds`` holds the kinds read through a derived field, where any change to the
    kind can move the value because the fields behind it cannot be named.
    """

    read_kinds: frozenset[str] = frozenset()
    read_fields: dict[str, frozenset[str]] = field(default_factory=dict)
    imprecise_kinds: frozenset[str] = frozenset()
    depends_on_everything: bool = False

    @classmethod
    def imprecise(cls) -> TransformReadSet:
        return cls(depends_on_everything=True)

    @classmethod
    def from_read_fields(
        cls,
        read_fields_by_kind: Mapping[str, Iterable[str]],
        *,
        scopable_derived_kinds: Container[str] = frozenset(),
    ) -> TransformReadSet:
        """Build the read set from a kind to read-field-names mapping.

        A kind read through a derived field is imprecise on its own, not for the whole set:
        collapsing the whole set throws away every other kind's field list, which leaves the
        consumer no way to reject a change to a kind it reads one named field of.

        Holding the imprecision against one kind is only sound when that kind's derived
        definition reads its own attributes, so ``scopable_derived_kinds`` names the kinds a
        caller has checked. A derived read on any other kind still collapses the whole set,
        because a path that crosses a relationship moves the value from a peer this read set
        cannot name. The default names none of them, which keeps a caller without schema
        knowledge on the conservative behaviour.

        A kind the query reaches but reads no field from stays in ``read_kinds`` and is left
        out of ``read_fields``: adding or removing that kind still triggers, a field change
        on it does not. Traversing a relationship to a generic reports every member kind,
        including the ones the query reads nothing from.
        """
        read_kinds: set[str] = set()
        read_fields: dict[str, frozenset[str]] = {}
        imprecise_kinds: set[str] = set()
        for kind, names in read_fields_by_kind.items():
            fields = frozenset(names)
            read_kinds.add(kind)
            if fields & IMPRECISE_READ_FIELDS:
                if kind not in scopable_derived_kinds:
                    return cls.imprecise()
                imprecise_kinds.add(kind)
                continue
            if fields:
                read_fields[kind] = fields

        return cls(
            read_kinds=frozenset(read_kinds),
            read_fields=read_fields,
            imprecise_kinds=frozenset(imprecise_kinds),
        )


class PythonTransformRegistry:
    """Tracks which node kinds have Python transform-based computed attributes."""

    def __init__(self, transform_attribute_map: dict[str, list[AttributeSchema]] | None = None) -> None:
        self._map: dict[str, list[AttributeSchema]] = transform_attribute_map or {}

    def duplicate(self) -> PythonTransformRegistry:
        return self.__class__(transform_attribute_map=deepcopy(self._map))

    def add_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        if node.kind not in self._map:
            self._map[node.kind] = []
        self._map[node.kind].append(attribute)

    def get_kinds(self) -> list[str]:
        """Return kinds that have Python attributes defined."""
        return list(self._map.keys())

    def get_attributes_per_node(self) -> dict[str, list[AttributeSchema]]:
        return self._map

    @property
    def attributes_by_transform(self) -> dict[str, list[PythonDefinition]]:
        computed_attributes: dict[str, list[PythonDefinition]] = {}
        for kind, attributes in self._map.items():
            for attribute in attributes:
                if attribute.computed_attribute and attribute.computed_attribute.transform:
                    if attribute.computed_attribute.transform not in computed_attributes:
                        computed_attributes[attribute.computed_attribute.transform] = []

                    computed_attributes[attribute.computed_attribute.transform].append(
                        PythonDefinition(kind=kind, attribute=attribute)
                    )

        return computed_attributes
