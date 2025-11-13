from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.schema import SchemaAttributePath


@dataclass
class TemplateLabel:
    template: str
    attributes: set[str] = field(default_factory=set)
    relationships: set[str] = field(default_factory=set)
    relationship_fields: dict[str, set[str]] = field(default_factory=dict)
    filter_key: str = "ids"

    @property
    def fields(self) -> list[str]:
        return sorted(list(self.attributes) + list(self.relationships))

    @property
    def has_related_components(self) -> bool:
        """Indicate if the associated template use variables from relationships"""
        return len(self.relationships) > 0

    def get_hash(self) -> str:
        return hashlib.md5(self.template.encode(), usedforsecurity=False).hexdigest()


@dataclass
class RelationshipIdentifier:
    kind: str
    filter_key: str
    template: str

    def __hash__(self) -> int:
        return hash(f"{self.kind}::{self.filter_key}::{self.template}")


@dataclass
class RelationshipTriggers:
    attributes: dict[str, set[RelationshipIdentifier]] = field(default_factory=dict)


class DisplayLabels:
    def __init__(
        self,
        template_based_display_labels: dict[str, TemplateLabel] | None = None,
        template_relationship_triggers: dict[str, RelationshipTriggers] | None = None,
    ) -> None:
        self._template_based_display_labels: dict[str, TemplateLabel] = template_based_display_labels or {}
        self._template_relationship_triggers: dict[str, RelationshipTriggers] = template_relationship_triggers or {}

    def duplicate(self) -> DisplayLabels:
        """Clone the current object."""
        return self.__class__(
            template_based_display_labels=deepcopy(self._template_based_display_labels),
            template_relationship_triggers=deepcopy(self._template_relationship_triggers),
        )

    def register_attribute_based_display_label(self, kind: str, attribute_name: str) -> None:
        """Register nodes where the display label consists of a single defined attribute name."""
        self._template_based_display_labels[kind] = TemplateLabel(
            template=f"{{{{ {attribute_name}__value }}}}", attributes={attribute_name}
        )

    def register_template_schema_path(self, kind: str, schema_path: SchemaAttributePath, template: str) -> None:
        """Register Jinja2 template based display labels using the schema path of each impacted variable in the node."""

        if kind not in self._template_based_display_labels:
            self._template_based_display_labels[kind] = TemplateLabel(template=template)

        if schema_path.is_type_attribute:
            self._template_based_display_labels[kind].attributes.add(schema_path.active_attribute_schema.name)
        elif schema_path.is_type_relationship and schema_path.related_schema:
            self._template_based_display_labels[kind].relationships.add(schema_path.active_relationship_schema.name)
            if (
                schema_path.active_relationship_schema.name
                not in self._template_based_display_labels[kind].relationship_fields
            ):
                self._template_based_display_labels[kind].relationship_fields[
                    schema_path.active_relationship_schema.name
                ] = set()
            self._template_based_display_labels[kind].relationship_fields[
                schema_path.active_relationship_schema.name
            ].add(schema_path.active_attribute_schema.name)

            if schema_path.related_schema.kind not in self._template_relationship_triggers:
                self._template_relationship_triggers[schema_path.related_schema.kind] = RelationshipTriggers()
            if (
                schema_path.active_attribute_schema.name
                not in self._template_relationship_triggers[schema_path.related_schema.kind].attributes
            ):
                self._template_relationship_triggers[schema_path.related_schema.kind].attributes[
                    schema_path.active_attribute_schema.name
                ] = set()
            self._template_relationship_triggers[schema_path.related_schema.kind].attributes[
                schema_path.active_attribute_schema.name
            ].add(
                RelationshipIdentifier(
                    kind=kind, filter_key=f"{schema_path.active_relationship_schema.name}__ids", template=template
                )
            )

    def targets_node(self, kind: str) -> bool:
        """Indicates if there is a display_label defined for the targeted node"""
        return kind in self._template_based_display_labels

    def get_template_node(self, kind: str) -> TemplateLabel:
        """Return node kinds together with their template definitions."""
        return self._template_based_display_labels[kind]

    def get_template_nodes(self) -> dict[str, TemplateLabel]:
        """Return node kinds together with their template definitions."""
        return self._template_based_display_labels

    def get_related_trigger_nodes(self) -> dict[str, RelationshipTriggers]:
        """Return node kinds that other nodes use within their templates for display_labels."""
        return self._template_relationship_triggers

    def get_related_template(self, related_kind: str, target_kind: str) -> TemplateLabel:
        relationship_trigger = self._template_relationship_triggers[related_kind]
        for applicable_kinds in relationship_trigger.attributes.values():
            for relationship_identifier in applicable_kinds:
                if target_kind == relationship_identifier.kind:
                    template_label = self.get_template_node(kind=target_kind)
                    template_label.filter_key = relationship_identifier.filter_key
                    return template_label

        raise ValueError(
            f"Unable to find registered template for {target_kind} registered on related node {related_kind}"
        )
