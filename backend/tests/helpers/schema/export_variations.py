"""Test schemas for the schema export, each in a namespace of its own so that they also load together."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

SCHEMA_FILE_VERSION = "1.0"


@dataclass(frozen=True)
class VariationSchema:
    name: str
    schema: dict[str, Any]
    """A schema file as a schema owner writes it, never changed by a test."""

    def payload(self) -> dict[str, Any]:
        """Return a copy of the schema file that the caller can load or change."""
        return copy.deepcopy(self.schema)


INHERITED_PROPERTIES = VariationSchema(
    name="inherited_properties",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "generics": [
            {
                "name": "Equipment",
                "namespace": "Pinned",
                "human_friendly_id": ["name__value"],
                "display_label": "name__value",
                "display_labels": ["name__value"],
                "default_filter": "name__value",
                "menu_placement": "PinnedRack",
                "uniqueness_constraints": [["name__value"]],
                "icon": "mdi:router",
                "order_by": ["name__value"],
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                "relationships": [
                    {"name": "rack", "peer": "PinnedRack", "cardinality": "one", "optional": True},
                ],
            }
        ],
        "nodes": [
            {
                "name": "Router",
                "namespace": "Pinned",
                "inherit_from": ["PinnedEquipment"],
                "attributes": [{"name": "model", "kind": "Text", "optional": True}],
            },
            {
                "name": "Rack",
                "namespace": "Pinned",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
        ],
    },
)
"""A generic that sets every property a node takes from its generic, and a node that takes them."""

INHERITED_HFID_WITH_UNIQUE_ATTRIBUTE = VariationSchema(
    name="inherited_hfid_with_unique_attribute",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "generics": [
            {
                "name": "Equipment",
                "namespace": "Merged",
                "human_friendly_id": ["name__value"],
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
        "nodes": [
            {
                "name": "Switch",
                "namespace": "Merged",
                "inherit_from": ["MergedEquipment"],
                "attributes": [{"name": "serial", "kind": "Text", "unique": True}],
            }
        ],
    },
)
"""A node whose own unique attribute adds a uniqueness constraint to the ones it takes from its generic."""

DERIVED_FROM_UNIQUE_ATTRIBUTE = VariationSchema(
    name="derived_from_unique_attribute",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Device",
                "namespace": "Derived",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
    },
)
"""A node with no generic whose human friendly ID and uniqueness constraints come from a unique attribute."""

IPAM_USER_NODE = VariationSchema(
    name="ipam_user_node",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Segment",
                "namespace": "Ipam",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
    },
)
"""A user node in the namespace where Infrahub also defines a kind of its own."""

DEPRECATED_VALIDATION_FIELDS = VariationSchema(
    name="deprecated_validation_fields",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Host",
                "namespace": "Legacy",
                "attributes": [
                    {
                        "name": "hostname",
                        "kind": "Text",
                        "unique": True,
                        "regex": "^[a-z0-9-]+$",
                        "min_length": 3,
                        "max_length": 32,
                    },
                    {
                        "name": "notes",
                        "kind": "TextArea",
                        "optional": True,
                        "regex": "^[^<>]*$",
                        "min_length": 1,
                        "max_length": 500,
                    },
                    {
                        "name": "aliases",
                        "kind": "List",
                        "optional": True,
                        "regex": "^[a-z0-9-]+$",
                        "min_length": 1,
                        "max_length": 10,
                    },
                ],
            }
        ],
    },
)
"""Validation settings written in their deprecated place at the top level of the attribute."""

NUMBER_POOL_RANGES = VariationSchema(
    name="number_pool_ranges",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Site",
                "namespace": "Pool",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
            {
                "name": "Circuit",
                "namespace": "Pool",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {
                        "name": "vlan_id",
                        "kind": "NumberPool",
                        "read_only": True,
                        "parameters": {"start_range": 100, "end_range": 200},
                    },
                    {
                        "name": "vni",
                        "kind": "NumberPool",
                        "read_only": True,
                        "parameters": {"start_range": 5000},
                    },
                    {
                        "name": "circuit_index",
                        "kind": "NumberPool",
                        "read_only": True,
                        "parameters": {
                            "ranges": [{"start": 1, "end": 50, "weight": 10}, {"start": 51, "end": 100}],
                            "allocation_scope": ["site"],
                        },
                    },
                ],
                "relationships": [
                    {"name": "site", "peer": "PoolSite", "cardinality": "one", "optional": False},
                ],
            },
        ],
    },
)
"""NumberPool attributes with the deprecated single range, with only its start, and with ranges."""

USER_NODE_EXTENSION = VariationSchema(
    name="user_node_extension",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Rack",
                "namespace": "Extended",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
            {
                "name": "Row",
                "namespace": "Extended",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "ExtendedRack",
                    "attributes": [{"name": "height", "kind": "Number", "optional": True}],
                    "relationships": [
                        {"name": "row", "peer": "ExtendedRow", "cardinality": "one", "optional": True},
                    ],
                }
            ]
        },
    },
)
"""An extension that adds an attribute and a relationship to a user node."""

RESTRICTED_NAMESPACE_EXTENSION = VariationSchema(
    name="restricted_namespace_extension",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Owner",
                "namespace": "Tagged",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "BuiltinTag",
                    "attributes": [{"name": "external_code", "kind": "Text", "optional": True}],
                    "relationships": [
                        {"name": "owner", "peer": "TaggedOwner", "cardinality": "one", "optional": True},
                    ],
                }
            ]
        },
    },
)
"""An extension to a kind Infrahub defines in a restricted namespace."""

BRANCH_OVERRIDE = VariationSchema(
    name="branch_override",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Region",
                "namespace": "Branching",
                "branch": "agnostic",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
            {
                "name": "Site",
                "namespace": "Branching",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "code", "kind": "Text", "optional": True, "branch": "agnostic"},
                ],
                "relationships": [
                    {
                        "name": "region",
                        "peer": "BranchingRegion",
                        "cardinality": "one",
                        "optional": True,
                        "branch": "agnostic",
                    },
                ],
            },
        ],
    },
)
"""An attribute and a relationship whose branch support differs from the one their node and peer give them."""

DEPRECATED_DISPLAY_FIELDS = VariationSchema(
    name="deprecated_display_fields",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "generics": [
            {
                "name": "Asset",
                "namespace": "Oldstyle",
                "description": "Equipment with an asset tag",
                "label": "Old style asset",
                "branch": "aware",
                "display_labels": ["name__value"],
                "default_filter": "name__value",
                "include_in_menu": False,
                "documentation": "https://example.com/assets",
                "restricted_namespaces": ["Oldstyle"],
                "generate_profile": False,
                "state": "present",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
        "nodes": [
            {
                "name": "Server",
                "namespace": "Oldstyle",
                "inherit_from": ["OldstyleAsset"],
                "generate_profile": False,
            },
            {
                "name": "Printer",
                "namespace": "Oldstyle",
                "display_labels": ["name__value"],
                "default_filter": "name__value",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            },
        ],
    },
)
"""A generic and a node that use the deprecated display_labels and default_filter."""

HIERARCHY = VariationSchema(
    name="hierarchy",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "generics": [
            {
                "name": "Location",
                "namespace": "Geo",
                "hierarchical": True,
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
        "nodes": [
            {
                "name": "Region",
                "namespace": "Geo",
                "inherit_from": ["GeoLocation"],
                "parent": "",
                "children": "GeoCity",
            },
            {
                "name": "City",
                "namespace": "Geo",
                "inherit_from": ["GeoLocation"],
                "parent": "GeoRegion",
                "children": "",
            },
        ],
    },
)
"""A hierarchical generic and the nodes of its hierarchy, which get generated parent and children relationships."""

PROFILE_AND_TEMPLATE = VariationSchema(
    name="profile_and_template",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Device",
                "namespace": "Templated",
                "generate_profile": True,
                "generate_template": True,
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            }
        ],
    },
)
"""A node that gets a generated profile and a generated object template."""

ATTRIBUTE_SETTINGS = VariationSchema(
    name="attribute_settings",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Item",
                "namespace": "Detail",
                "description": "Item with every attribute setting",
                "label": "Detail item",
                "branch": "aware",
                "human_friendly_id": ["name__value"],
                "display_label": "name__value",
                "include_in_menu": True,
                "menu_placement": "DetailItem",
                "icon": "mdi:cube",
                "order_by": ["name__value"],
                "uniqueness_constraints": [["name__value"]],
                "documentation": "https://example.com/items",
                "state": "present",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True, "label": "Name"},
                    {
                        "name": "code",
                        "kind": "Text",
                        "optional": True,
                        "order_weight": 1500,
                        "description": "Short code of the item",
                        "parameters": {"regex": "^[A-Z]+$", "min_length": 2, "max_length": 8},
                    },
                    {"name": "status", "kind": "Text", "optional": True, "default_value": "active"},
                    {"name": "size", "kind": "Text", "optional": True, "enum": ["small", "large"]},
                    {
                        "name": "legacy_code",
                        "kind": "Text",
                        "optional": True,
                        "deprecation": "Use code instead",
                        "display": "extra",
                        "allow_override": "none",
                        "state": "present",
                    },
                    {
                        "name": "summary",
                        "kind": "Text",
                        "read_only": True,
                        "computed_attribute": {"kind": "Jinja2", "jinja2_template": "{{ name__value }}"},
                    },
                    {
                        "name": "checksum",
                        "kind": "Text",
                        "read_only": True,
                        "optional": True,
                        "computed_attribute": {"kind": "TransformPython", "transform": "item_checksum"},
                    },
                    {
                        "name": "owner_note",
                        "kind": "Text",
                        "optional": True,
                        "computed_attribute": {"kind": "User"},
                    },
                    {
                        "name": "priority",
                        "kind": "Number",
                        "optional": True,
                        "parameters": {"min_value": 1, "max_value": 10, "excluded_values": "5,7-8"},
                    },
                    {
                        "name": "tags",
                        "kind": "List",
                        "optional": True,
                        "ordered": False,
                        "parameters": {"regex": "^[a-z]+$"},
                    },
                    {
                        "name": "category",
                        "kind": "Dropdown",
                        "optional": True,
                        "choices": [
                            {
                                "name": "small",
                                "label": "Small",
                                "description": "Fits in one rack unit",
                                "color": "#00ff00",
                                "state": "present",
                            },
                            {"name": "large"},
                        ],
                    },
                ],
            }
        ],
    },
)
"""Attributes that set each attribute setting, among them an explicit order weight and a label equal to the one
derived from the name."""

RELATIONSHIP_SETTINGS = VariationSchema(
    name="relationship_settings",
    schema={
        "version": SCHEMA_FILE_VERSION,
        "nodes": [
            {
                "name": "Device",
                "namespace": "Cabling",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                "relationships": [
                    {
                        "name": "ports",
                        "peer": "CablingPort",
                        "kind": "Component",
                        "cardinality": "many",
                        "optional": True,
                        "identifier": "cabling_device__ports",
                        "on_delete": "cascade",
                        "label": "Ports",
                        "description": "Ports of the device",
                        "order_weight": 2000,
                    },
                    {
                        "name": "lags",
                        "peer": "CablingLag",
                        "kind": "Component",
                        "cardinality": "many",
                        "optional": True,
                        "identifier": "cabling_device__lags",
                    },
                ],
            },
            {
                "name": "Port",
                "namespace": "Cabling",
                "attributes": [{"name": "name", "kind": "Text"}],
                "relationships": [
                    {
                        "name": "device",
                        "peer": "CablingDevice",
                        "kind": "Parent",
                        "cardinality": "one",
                        "optional": False,
                        "identifier": "cabling_device__ports",
                    },
                ],
            },
            {
                "name": "Lag",
                "namespace": "Cabling",
                "attributes": [{"name": "name", "kind": "Text"}],
                "relationships": [
                    {
                        "name": "device",
                        "peer": "CablingDevice",
                        "kind": "Parent",
                        "cardinality": "one",
                        "optional": False,
                        "identifier": "cabling_device__lags",
                    },
                    {
                        "name": "members",
                        "peer": "CablingPort",
                        "cardinality": "many",
                        "optional": True,
                        "common_parent": "device",
                        "common_relatives": ["device"],
                        "min_count": 0,
                        "max_count": 4,
                        "direction": "outbound",
                        "read_only": True,
                        "allow_override": "none",
                        "deprecation": "Use the member ports of the device",
                        "display": "extra",
                        "state": "present",
                    },
                ],
            },
        ],
    },
)
"""Relationships that set each relationship setting, among them a common parent and common relatives."""

VARIATION_SCHEMAS: tuple[VariationSchema, ...] = (
    INHERITED_PROPERTIES,
    INHERITED_HFID_WITH_UNIQUE_ATTRIBUTE,
    DERIVED_FROM_UNIQUE_ATTRIBUTE,
    IPAM_USER_NODE,
    DEPRECATED_VALIDATION_FIELDS,
    NUMBER_POOL_RANGES,
    USER_NODE_EXTENSION,
    RESTRICTED_NAMESPACE_EXTENSION,
    BRANCH_OVERRIDE,
    DEPRECATED_DISPLAY_FIELDS,
    HIERARCHY,
    PROFILE_AND_TEMPLATE,
    ATTRIBUTE_SETTINGS,
    RELATIONSHIP_SETTINGS,
)


def merge_variation_schemas(variations: Iterable[VariationSchema]) -> dict[str, Any]:
    """Return one schema file that holds the nodes, generics and extensions of every given variation schema."""
    merged: dict[str, Any] = {"version": SCHEMA_FILE_VERSION, "generics": [], "nodes": [], "extensions": {"nodes": []}}
    for variation in variations:
        payload = variation.payload()
        merged["generics"].extend(payload.get("generics", []))
        merged["nodes"].extend(payload.get("nodes", []))
        merged["extensions"]["nodes"].extend(payload.get("extensions", {}).get("nodes", []))
    return merged
