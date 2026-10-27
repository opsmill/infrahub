"""The brief export leaves out what processing gives back and keeps what a schema owner wrote."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from infrahub.core.constants import SchemaExportMode
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.export.exporter import SchemaExporter, build_base_schema_branch, build_schema_exporter

RULE_SCHEMAS = Path(__file__).parent / "schemas"


def _brief_export(exporter: SchemaExporter, schema_file: str, namespaces: list[str] | None = None) -> dict[str, Any]:
    schema_branch = build_base_schema_branch()
    schema_branch.load_schema(schema=SchemaRoot(**yaml.safe_load((RULE_SCHEMAS / schema_file).read_text())))
    schema_branch.process()
    return exporter.export(schema_branch=schema_branch, namespaces=namespaces, mode=SchemaExportMode.BRIEF).model_dump(
        mode="json", exclude_unset=True
    )


@pytest.fixture(scope="module")
def exporter() -> SchemaExporter:
    return build_schema_exporter(infrahub_version="1.13.0")


@dataclass
class BriefExportCase:
    name: str
    schema_file: str
    expected: dict[str, Any]


BRIEF_EXPORT_CASES = [
    BriefExportCase(
        name="properties-copied-from-a-generic-stay-on-the-node",
        schema_file="inherited_properties.yml",
        expected={
            "version": "1.0",
            "infrahub_version": "1.13.0",
            "generics": [
                {
                    "name": "Interface",
                    "namespace": "Network",
                    "default_filter": "name__value",
                    "human_friendly_id": ["device__name__value", "name__value"],
                    "display_label": "{{ device__name__value }} {{ name__value }}",
                    "icon": "mdi:ethernet",
                    "order_by": ["name__value"],
                    "attributes": [
                        {"name": "name", "kind": "Text"},
                        {"name": "description", "kind": "Text", "optional": True},
                    ],
                    "relationships": [
                        {
                            "name": "device",
                            "peer": "NetworkDevice",
                            "kind": "Attribute",
                            "cardinality": "one",
                            "optional": False,
                        }
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Network",
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                },
                {
                    "name": "PhysicalInterface",
                    "namespace": "Network",
                    "human_friendly_id": ["device__name__value", "name__value"],
                    "display_label": "{{ device__name__value }} {{ name__value }}",
                    "icon": "mdi:ethernet",
                    "order_by": ["name__value"],
                    "uniqueness_constraints": [["device", "name__value"]],
                    "attributes": [{"name": "speed", "kind": "Number"}],
                    "inherit_from": ["NetworkInterface"],
                },
                {
                    "name": "VirtualInterface",
                    "namespace": "Network",
                    "human_friendly_id": ["device__name__value", "name__value"],
                    "display_label": "{{ device__name__value }} {{ name__value }}",
                    "icon": "mdi:lan",
                    "order_by": ["description__value"],
                    "uniqueness_constraints": [["device", "name__value"]],
                    "inherit_from": ["NetworkInterface"],
                },
            ],
        },
    ),
    BriefExportCase(
        name="derived-values-are-left-out-unless-they-differ",
        schema_file="derived_values.yml",
        expected={
            "version": "1.0",
            "infrahub_version": "1.13.0",
            "generics": [],
            "nodes": [
                {
                    "name": "Router",
                    "namespace": "Derived",
                    "attributes": [
                        {"name": "hostname", "kind": "Text", "unique": True},
                        {"name": "role", "kind": "Text", "order_weight": 3000, "default_value": "edge"},
                        {
                            "name": "serial_number",
                            "kind": "Text",
                            "label": "Serial",
                            "optional": True,
                            "order_weight": 5000,
                        },
                        {"name": "asn", "kind": "Number", "optional": True, "branch": "agnostic", "order_weight": 7000},
                    ],
                    "relationships": [
                        {
                            "name": "site",
                            "peer": "DerivedSite",
                            "kind": "Attribute",
                            "cardinality": "one",
                            "optional": False,
                        },
                        {
                            "name": "uplinks",
                            "peer": "DerivedSite",
                            "label": "Uplink sites",
                            "identifier": "router_uplink_sites",
                            "on_delete": "cascade",
                        },
                    ],
                },
                {
                    "name": "Site",
                    "namespace": "Derived",
                    "label": "Physical site",
                    "uniqueness_constraints": [["name__value", "code__value"]],
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "code", "kind": "Text"},
                    ],
                    "relationships": [
                        {"name": "routers", "peer": "DerivedRouter", "kind": "Component"},
                        {"name": "uplink_routers", "peer": "DerivedRouter", "identifier": "router_uplink_sites"},
                    ],
                },
            ],
        },
    ),
    BriefExportCase(
        name="validation-settings-only-under-parameters",
        schema_file="attribute_settings.yml",
        expected={
            "version": "1.0",
            "infrahub_version": "1.13.0",
            "generics": [],
            "nodes": [
                {
                    "name": "Circuit",
                    "namespace": "Settings",
                    "default_filter": "circuit_id__value",
                    "display_labels": ["circuit_id__value"],
                    "attributes": [
                        {
                            "name": "circuit_id",
                            "kind": "Text",
                            "unique": True,
                            "parameters": {"regex": "^[A-Z]{3}-[0-9]+$", "min_length": 5, "max_length": 20},
                        },
                        {"name": "comment", "kind": "TextArea", "optional": True, "parameters": {"max_length": 500}},
                        {
                            "name": "status",
                            "kind": "Dropdown",
                            "choices": [
                                {"name": "planned"},
                                {"name": "decommissioned", "description": "No longer in service", "label": "Retired"},
                                {"name": "active", "color": "#7fbf7f"},
                            ],
                            "optional": True,
                        },
                        {
                            "name": "vlan_id",
                            "kind": "NumberPool",
                            "read_only": True,
                            "parameters": {
                                "ranges": [{"start": 100, "end": 199}, {"start": 300, "end": 399, "weight": 2}]
                            },
                        },
                    ],
                }
            ],
        },
    ),
    BriefExportCase(
        name="generated-relationships-and-core-extensions-are-left-out",
        schema_file="generated_elements.yml",
        expected={
            "version": "1.0",
            "infrahub_version": "1.13.0",
            "generics": [],
            "nodes": [
                {
                    "name": "Collector",
                    "namespace": "Generated",
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                    "relationships": [{"name": "watched_groups", "peer": "CoreStandardGroup", "kind": "Group"}],
                    "generate_template": True,
                },
                {
                    "name": "Probe",
                    "namespace": "Generated",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "location", "kind": "Text", "optional": True},
                    ],
                },
            ],
        },
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in BRIEF_EXPORT_CASES])
def test_brief_export(exporter: SchemaExporter, case: BriefExportCase) -> None:
    assert _brief_export(exporter=exporter, schema_file=case.schema_file) == case.expected


def test_namespace_selection_exports_only_the_selected_namespaces(exporter: SchemaExporter) -> None:
    exported = _brief_export(exporter=exporter, schema_file="derived_values.yml", namespaces=["Missing"])

    assert exported == {"version": "1.0", "infrahub_version": "1.13.0", "generics": [], "nodes": []}
