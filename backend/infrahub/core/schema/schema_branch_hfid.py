from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.schema import SchemaAttributePath


@dataclass
class HFIDDefinition:
    hfid: list[str]
    attributes: set[str] = field(default_factory=set)
    relationships: set[str] = field(default_factory=set)
    filter_key: str = "ids"

    @property
    def fields(self) -> list[str]:
        return sorted(list(self.attributes) + list(self.relationships))

    @property
    def has_related_components(self) -> bool:
        """Indicate if the associated template use variables from relationships"""
        return len(self.relationships) > 0

    def get_hash(self) -> str:
        return hashlib.md5("::".join(self.hfid).encode(), usedforsecurity=False).hexdigest()


@dataclass
class RelationshipIdentifier:
    kind: str
    hfid: list[str]
    filter_key: str

    def __hash__(self) -> int:
        return hash(f"{self.kind}::{'::'.join(self.hfid)}::{self.filter_key}")


@dataclass
class RelationshipTriggers:
    attributes: dict[str, set[RelationshipIdentifier]] = field(default_factory=dict)


class HFIDs:
    def __init__(
        self,
        node_level_hfids: dict[str, HFIDDefinition] | None = None,
        relationship_triggers: dict[str, RelationshipTriggers] | None = None,
    ) -> None:
        self._node_level_hfids: dict[str, HFIDDefinition] = node_level_hfids or {}
        self._relationship_triggers: dict[str, RelationshipTriggers] = relationship_triggers or {}

    def duplicate(self) -> HFIDs:
        return self.__class__(
            node_level_hfids=deepcopy(self._node_level_hfids),
            relationship_triggers=deepcopy(self._relationship_triggers),
        )

    def register_hfid_schema_path(self, kind: str, schema_path: SchemaAttributePath, hfid: list[str]) -> None:
        """Register HFID using the schema path of each impacted schema path in use."""
        if kind not in self._node_level_hfids:
            self._node_level_hfids[kind] = HFIDDefinition(hfid=hfid)
        if schema_path.is_type_attribute:
            self._node_level_hfids[kind].attributes.add(schema_path.active_attribute_schema.name)
        elif schema_path.is_type_relationship and schema_path.related_schema:
            self._node_level_hfids[kind].relationships.add(schema_path.active_relationship_schema.name)
            if schema_path.related_schema.kind not in self._relationship_triggers:
                self._relationship_triggers[schema_path.related_schema.kind] = RelationshipTriggers()
            if (
                schema_path.active_attribute_schema.name
                not in self._relationship_triggers[schema_path.related_schema.kind].attributes
            ):
                self._relationship_triggers[schema_path.related_schema.kind].attributes[
                    schema_path.active_attribute_schema.name
                ] = set()
            self._relationship_triggers[schema_path.related_schema.kind].attributes[
                schema_path.active_attribute_schema.name
            ].add(
                RelationshipIdentifier(
                    kind=kind, filter_key=f"{schema_path.active_relationship_schema.name}__ids", hfid=hfid
                )
            )

    def targets_node(self, kind: str) -> bool:
        """Indicates if there is a human_friendly_id defined for the targeted node"""
        return kind in self._node_level_hfids

    def get_template_node(self, kind: str) -> HFIDDefinition:
        """Return node kinds together with their template definitions."""
        return self._node_level_hfids[kind]

    def get_template_nodes(self) -> dict[str, HFIDDefinition]:
        """Return node kinds together with their template definitions."""
        return self._node_level_hfids

    def get_related_trigger_nodes(self) -> dict[str, RelationshipTriggers]:
        """Return node kinds that other nodes use within their templates for display_labels."""
        return self._relationship_triggers
