"""Registry for Python transform-based computed attributes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.schema import AttributeSchema  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from infrahub.core.schema import NodeSchema

# Reads of these computed/derived fields cannot be mapped back to a precise set of
# backing schema elements, so an attribute that reads them must be recomputed on any
# schema change.
IMPRECISE_READ_FIELDS = frozenset({"display_label", "hfid"})


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

    ``depends_on_everything`` is set when the read set cannot be mapped precisely
    (an unanalyzable query, or a read of a derived field such as the display label).
    """

    read_kinds: frozenset[str] = frozenset()
    read_fields: dict[str, frozenset[str]] = field(default_factory=dict)
    depends_on_everything: bool = False

    @classmethod
    def imprecise(cls) -> TransformReadSet:
        return cls(depends_on_everything=True)

    @classmethod
    def from_read_fields(cls, read_fields_by_kind: Mapping[str, Iterable[str]]) -> TransformReadSet:
        """Build the read set from a kind to read-field-names mapping.

        The set is marked imprecise when a read cannot be mapped to concrete backing
        elements: a read of a derived field (such as the display label), or a read
        kind that contributes no mappable field at all. The latter covers a query
        that selects only a value with no concrete schema element behind it (such as
        a human-friendly id), which would otherwise look like a precise read of
        nothing and be skipped on every change.
        """
        read_fields: dict[str, frozenset[str]] = {}
        for kind, names in read_fields_by_kind.items():
            fields = frozenset(names)
            if not fields or fields & IMPRECISE_READ_FIELDS:
                return cls.imprecise()
            read_fields[kind] = fields

        return cls(read_kinds=frozenset(read_fields), read_fields=read_fields)


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
