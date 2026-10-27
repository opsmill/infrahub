from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final

from infrahub_sdk.schema.generated.write import (
    AttributeSchemaBaseWrite,
    DropdownChoiceWrite,
    GenericSchemaWrite,
    NodeSchemaWrite,
    RelationshipSchemaWrite,
)
from pydantic_core import PydanticUndefined

from infrahub.core.constants import RelationshipCardinality, RelationshipDeleteBehavior, RelationshipKind
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import SchemaExportError
from infrahub.utils import format_label

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from infrahub.core.schema.schema_branch import SchemaBranch

    from .document import ElementData, ExportDocument
    from .serializer import SchemaExportSerializer

COPYABLE_NODE_PROPERTIES: Final = frozenset(
    {
        "human_friendly_id",
        "display_label",
        "display_labels",
        "default_filter",
        "menu_placement",
        "uniqueness_constraints",
        "icon",
        "order_by",
    }
)
"""Node properties that processing copies from the first generic in `inherit_from` that sets them."""

_SIMULATED_FIELDS: Final[dict[str, frozenset[str]]] = {
    "generics": frozenset({"human_friendly_id", "uniqueness_constraints", "display_label"}),
    "nodes": frozenset({"human_friendly_id", "uniqueness_constraints", "display_label"}),
    "attributes": frozenset({"branch", "order_weight"}),
    "relationships": frozenset({"branch", "order_weight"}),
    "choices": frozenset({"color"}),
}
"""Fields that processing fills in from other elements or from order; processing the candidate decides them."""


@dataclass(frozen=True)
class _Item:
    owner: ElementData
    """The node or generic the item belongs to, or the item itself at element level."""

    data: ElementData


def _label(item: _Item) -> object:
    return format_label(item.data["name"])


def _attribute_optional(item: _Item) -> object:
    return item.data.get("default_value") is not None or item.data.get("deprecation") is not None


def _cardinality_one(item: _Item) -> bool:
    return item.data.get("cardinality", RelationshipCardinality.MANY.value) == RelationshipCardinality.ONE.value


def _relationship_min_count(item: _Item) -> object:
    return 1 if _cardinality_one(item=item) and not item.data.get("optional", True) else 0


def _relationship_max_count(item: _Item) -> object:
    return 1 if _cardinality_one(item=item) else 0


def _relationship_identifier(item: _Item) -> object:
    return "__".join(sorted([_element_key(element=item.owner), item.data["peer"]])).lower()


def _relationship_on_delete(item: _Item) -> object:
    if item.data.get("kind") == RelationshipKind.COMPONENT.value:
        return RelationshipDeleteBehavior.CASCADE.value
    return RelationshipDeleteBehavior.NO_ACTION.value


_PREDICTED_FIELDS: Final[dict[str, dict[str, Callable[[_Item], object]]]] = {
    "generics": {"label": _label},
    "nodes": {"label": _label},
    "attributes": {"label": _label, "optional": _attribute_optional},
    "relationships": {
        "label": _label,
        "min_count": _relationship_min_count,
        "max_count": _relationship_max_count,
        "identifier": _relationship_identifier,
        "on_delete": _relationship_on_delete,
    },
    "choices": {"label": _label},
}
"""Fields whose derived value depends only on their own element; they are left out only when it matches.

A value that processing would derive differently can change what the schema means, such as a relationship
becoming optional, and the candidate would then fail validation instead of showing a difference.
"""

_STORED_DEFAULTS: Final[dict[str, dict[str, object]]] = {
    # An instance stores an unset `include_in_menu` as `true`.
    "generics": {"include_in_menu": True},
    "nodes": {"include_in_menu": True},
    "choices": {"description": ""},
}
"""Values an instance gives a field that a schema file leaves out, where they differ from the write default."""

_WRITE_MODELS: Final[dict[str, type[BaseModel]]] = {
    "generics": GenericSchemaWrite,
    "nodes": NodeSchemaWrite,
    "attributes": AttributeSchemaBaseWrite,
    "relationships": RelationshipSchemaWrite,
    "choices": DropdownChoiceWrite,
}
_KEYED_LISTS: Final = frozenset({"attributes", "relationships", "choices"})
_IDENTITY_FIELDS: Final[dict[str, frozenset[str]]] = {
    "generics": frozenset({"name", "namespace"}),
    "nodes": frozenset({"name", "namespace"}),
    "attributes": frozenset({"name", "kind"}),
    "relationships": frozenset({"name", "peer"}),
    "choices": frozenset({"name"}),
}

Path = tuple[str, ...]


class _Absent:
    pass


ABSENT: Final = _Absent()


@dataclass
class _Reduction:
    """The values tried for one field, from the shortest export to the stored value."""

    steps: list[Any]
    simulated: bool
    """Processing the candidate decides the value, instead of a default or a rule on the element alone."""
    position: int = 0

    @property
    def value(self) -> Any:
        return self.steps[self.position]

    def restore(self) -> bool:
        if self.position == len(self.steps) - 1:
            return False
        self.position += 1
        return True

    def restore_fully(self) -> bool:
        restored = self.position != len(self.steps) - 1
        self.position = len(self.steps) - 1
        return restored


class BriefSchemaMinimizer:
    """Leave out of an export every value that processing the export gives back.

    Derived values depend on order and on each other (dropdown colours, a human-friendly ID taken from the first
    unique attribute, order weights), so each candidate is processed and the values that come out different are
    written back until nothing differs.
    """

    def __init__(self, serializer: SchemaExportSerializer, base_branch_factory: Callable[[], SchemaBranch]) -> None:
        self.serializer = serializer
        self.base_branch_factory = base_branch_factory

    def minimize(
        self, full: ExportDocument, context: ExportDocument, copied_properties: dict[str, frozenset[str]]
    ) -> ExportDocument:
        """Return the shortest export that processes into `full`.

        Args:
            context: The other user namespaces, which the exported ones may reference.
            copied_properties: Per node kind, the properties a generic in its `inherit_from` sets; they stay.

        Raises:
            SchemaExportError: When a value differs after processing and cannot be written back.

        """
        reductions = self._plan(full=full, copied_properties=copied_properties)
        while True:
            candidate = self._apply(full=full, reductions=reductions)
            try:
                processed = self._process(candidate=candidate, context=context, namespaces=full.namespaces)
            except SchemaExportError:
                # A wrongly derived value can make the candidate invalid; the other reductions keep its meaning.
                restored = [reduction.restore_fully() for reduction in reductions.values() if reduction.simulated]
                if not any(restored):
                    raise
                continue
            differences = _compare_documents(expected=full, actual=processed)
            if not differences:
                return candidate
            for path in _independent(differences=differences):
                reduction = reductions.get(path)
                if reduction is None or not reduction.restore():
                    raise SchemaExportError(message=f"{'.'.join(path)} differs after the export is loaded")

    def _process(self, candidate: ExportDocument, context: ExportDocument, namespaces: list[str]) -> ExportDocument:
        schema_branch = self.base_branch_factory()
        try:
            schema_branch.load_schema(
                schema=SchemaRoot.model_validate(
                    {
                        "version": "1.0",
                        "generics": context.generics + candidate.generics,
                        "nodes": context.nodes + candidate.nodes,
                    }
                )
            )
            schema_branch.process()
        except ValueError as exc:
            raise SchemaExportError(message=f"the export does not load: {exc}") from exc
        return self.serializer.serialize(schema_branch=schema_branch, namespaces=namespaces)

    def _plan(self, full: ExportDocument, copied_properties: dict[str, frozenset[str]]) -> dict[Path, _Reduction]:
        reductions: dict[Path, _Reduction] = {}
        for section, elements in full.sections().items():
            for element in elements:
                key = _element_key(element=element)
                kept = copied_properties.get(key, frozenset()) if section == "nodes" else frozenset()
                for name, value in element.items():
                    if name in kept:
                        continue
                    if name in _KEYED_LISTS:
                        self._plan_items(
                            reductions=reductions, path=(section, key, name), section=name, owner=element, items=value
                        )
                    if name == "uniqueness_constraints":
                        reductions[section, key, name] = _uniqueness_reduction(element=element, constraints=value)
                    elif _is_derivable(section=section, name=name, value=value, owner=element, item=element):
                        reductions[section, key, name] = _Reduction(
                            steps=[ABSENT, value], simulated=name in _SIMULATED_FIELDS[section]
                        )
        return reductions

    def _plan_items(
        self,
        reductions: dict[Path, _Reduction],
        path: Path,
        section: str,
        owner: ElementData,
        items: list[ElementData],
    ) -> None:
        for item in items:
            item_path = (*path, item["name"])
            for name, value in item.items():
                if name in _KEYED_LISTS:
                    self._plan_items(
                        reductions=reductions, path=(*item_path, name), section=name, owner=owner, items=value
                    )
                if _is_derivable(section=section, name=name, value=value, owner=owner, item=item):
                    reductions[*item_path, name] = _Reduction(
                        steps=[ABSENT, value], simulated=name in _SIMULATED_FIELDS[section]
                    )

    def _apply(self, full: ExportDocument, reductions: dict[Path, _Reduction]) -> ExportDocument:
        candidate = copy.deepcopy(full)
        sections = candidate.sections()
        for path, reduction in reductions.items():
            section, key, *rest = path
            target = next(element for element in sections[section] if _element_key(element=element) == key)
            *item_steps, field_name = rest
            for list_name, item_name in zip(item_steps[::2], item_steps[1::2], strict=True):
                target = next(item for item in target[list_name] if item["name"] == item_name)
            if reduction.value is ABSENT:
                del target[field_name]
            else:
                target[field_name] = copy.deepcopy(reduction.value)
        return candidate


def _is_derivable(section: str, name: str, value: Any, owner: ElementData, item: ElementData) -> bool:
    if name in _IDENTITY_FIELDS[section]:
        return False
    if name in _SIMULATED_FIELDS[section]:
        return True
    predictor = _PREDICTED_FIELDS[section].get(name)
    if predictor is not None:
        return value == predictor(_Item(owner=owner, data=item))
    if name in _STORED_DEFAULTS.get(section, {}):
        return value == _STORED_DEFAULTS[section][name]
    return value == _write_default(model=_WRITE_MODELS[section], name=name)


def _write_default(model: type[BaseModel], name: str) -> Any:
    info = model.model_fields.get(name)
    if info is None:
        return ABSENT
    default = info.get_default(call_default_factory=True)
    if default is PydanticUndefined:
        return ABSENT
    if isinstance(default, Enum):
        return default.value
    return default


_DEPENDENCIES: Final[dict[str, frozenset[str]]] = {"uniqueness_constraints": frozenset({"human_friendly_id"})}
"""Fields that processing derives from other fields of the same element."""


def _independent(differences: list[Path]) -> list[Path]:
    """Drop the differences that may disappear once the field they derive from is written back."""
    differing = set(differences)
    return [
        path
        for path in differences
        if not any((*path[:-1], source) in differing for source in _DEPENDENCIES.get(path[-1], frozenset()))
    ]


def _uniqueness_reduction(element: ElementData, constraints: list[list[str]]) -> _Reduction:
    # A unique attribute brings its own single-attribute constraint back on load.
    from_unique = [[f"{attribute['name']}__value"] for attribute in element["attributes"] if attribute.get("unique")]
    declared = [constraint for constraint in constraints if constraint not in from_unique]
    steps: list[Any] = [ABSENT]
    if declared and declared != constraints:
        steps.append(declared)
    steps.append(constraints)
    return _Reduction(steps=steps, simulated=True)


def _element_key(element: ElementData) -> str:
    return f"{element['namespace']}{element['name']}"


def _compare_documents(expected: ExportDocument, actual: ExportDocument) -> list[Path]:
    differences: list[Path] = []
    actual_sections = actual.sections()
    for section, elements in expected.sections().items():
        expected_by_key = {_element_key(element=element): element for element in elements}
        actual_by_key = {_element_key(element=element): element for element in actual_sections[section]}
        for key in sorted(expected_by_key.keys() | actual_by_key.keys()):
            if key not in expected_by_key or key not in actual_by_key:
                differences.append((section, key))
                continue
            differences.extend(
                _compare_items(expected=expected_by_key[key], actual=actual_by_key[key], path=(section, key))
            )
    return differences


def _compare_items(expected: ElementData, actual: ElementData, path: Path) -> list[Path]:
    differences: list[Path] = []
    for name in sorted(expected.keys() | actual.keys()):
        expected_value = expected.get(name, ABSENT)
        actual_value = actual.get(name, ABSENT)
        if name in _KEYED_LISTS and isinstance(expected_value, list) and isinstance(actual_value, list):
            expected_by_name = {item["name"]: item for item in expected_value}
            actual_by_name = {item["name"]: item for item in actual_value}
            for item_name in sorted(expected_by_name.keys() | actual_by_name.keys()):
                if item_name not in expected_by_name or item_name not in actual_by_name:
                    differences.append((*path, name, item_name))
                    continue
                differences.extend(
                    _compare_items(
                        expected=expected_by_name[item_name],
                        actual=actual_by_name[item_name],
                        path=(*path, name, item_name),
                    )
                )
        elif expected_value != actual_value:
            differences.append((*path, name))
    return differences
