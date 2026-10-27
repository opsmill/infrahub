"""The full export writes every value of the user-defined elements and nothing else."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.constants import SchemaExportMode
from infrahub.core.models import UpdateValidationErrorType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.export.exporter import SchemaExporter, build_base_schema_branch, build_schema_exporter

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

RULE_SCHEMAS = Path(__file__).parent / "schemas"


def _processed(root: SchemaRoot) -> SchemaBranch:
    schema_branch = build_base_schema_branch()
    schema_branch.load_schema(schema=root)
    schema_branch.process()
    return schema_branch


def _export(exporter: SchemaExporter, schema_branch: SchemaBranch, mode: SchemaExportMode) -> dict[str, Any]:
    return exporter.export(schema_branch=schema_branch, namespaces=None, mode=mode).model_dump(
        mode="json", exclude_unset=True
    )


@pytest.fixture(scope="module")
def exporter() -> SchemaExporter:
    return build_schema_exporter(infrahub_version="1.13.0")


def test_full_export_writes_derived_values(exporter: SchemaExporter) -> None:
    root = SchemaRoot(**yaml.safe_load((RULE_SCHEMAS / "derived_values.yml").read_text()))

    router = next(
        node
        for node in _export(exporter=exporter, schema_branch=_processed(root=root), mode=SchemaExportMode.FULL)["nodes"]
        if node["name"] == "Router"
    )

    assert router["label"] == "Router"
    assert router["human_friendly_id"] == ["hostname__value"]
    assert router["include_in_menu"] is True
    assert [
        (attribute["name"], attribute["label"], attribute["optional"], attribute["branch"], attribute["order_weight"])
        for attribute in router["attributes"]
    ] == [
        ("hostname", "Hostname", False, "aware", 1000),
        ("role", "Role", True, "aware", 3000),
        ("serial_number", "Serial", True, "aware", 5000),
        ("asn", "Asn", True, "agnostic", 7000),
    ]
    assert [
        (relationship["name"], relationship["identifier"], relationship["on_delete"], relationship["max_count"])
        for relationship in router["relationships"]
    ] == [
        ("site", "derivedrouter__derivedsite", "no-action", 1),
        ("uplinks", "router_uplink_sites", "cascade", 0),
    ]


def test_full_export_still_leaves_out_generated_and_core_elements(exporter: SchemaExporter) -> None:
    root = SchemaRoot(**yaml.safe_load((RULE_SCHEMAS / "generated_elements.yml").read_text()))

    exported = _export(exporter=exporter, schema_branch=_processed(root=root), mode=SchemaExportMode.FULL)

    assert [node["name"] for node in exported["nodes"]] == ["Collector", "Probe"]
    collector = exported["nodes"][0]
    assert [relationship["name"] for relationship in collector["relationships"]] == ["watched_groups"]
    assert {"id", "state"} & set(collector) == set()
    assert [attribute["name"] for attribute in exported["nodes"][1]["attributes"]] == ["name", "location"]


def _router(asn_branch: str | None) -> SchemaRoot:
    asn: dict[str, Any] = {"name": "asn", "kind": "Number", "optional": True}
    if asn_branch:
        asn["branch"] = asn_branch
    return SchemaRoot(
        nodes=[
            {
                "name": "Router",
                "namespace": "Derived",
                "attributes": [{"name": "hostname", "kind": "Text", "unique": True}, asn],
            }
        ]
    )


def _load_errors(target: SchemaBranch, payload: dict[str, Any]) -> list[tuple[UpdateValidationErrorType, str]]:
    candidate = target.duplicate()
    candidate.load_schema(schema=SchemaLoadAPI.model_validate(payload).internal_schema)
    candidate.process()
    result = target.validate_update(other=candidate, diff=target.diff(other=candidate))
    return [(error.error, f"{error.path.schema_kind}.{error.path.field_name}") for error in result.errors]


def test_full_export_of_a_setting_infrahub_cannot_update_is_refused_where_it_differs(exporter: SchemaExporter) -> None:
    # The load refuses to create this state in one instance, so source and target are separate schemas.
    source = _processed(root=_router(asn_branch=None))
    target = _processed(root=_router(asn_branch="agnostic"))

    full = _export(exporter=exporter, schema_branch=source, mode=SchemaExportMode.FULL)
    brief = _export(exporter=exporter, schema_branch=source, mode=SchemaExportMode.BRIEF)

    assert _load_errors(target=target, payload=full) == [(UpdateValidationErrorType.NOT_SUPPORTED, "DerivedRouter.asn")]
    assert _load_errors(target=target, payload=brief) == []
