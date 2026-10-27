"""An exported schema loads into an empty instance and gives the same user-defined schema.

Existing fixtures cover these rules: `CAR_SCHEMA` (unique attributes, cardinality one and many),
`DEVICE_SCHEMA` (generics, object templates), `LOCATION_SCHEMA` (hierarchy) and `SNOW_TICKET_SCHEMA`
(NumberPool `start_range` and `end_range`). The files in `schemas/` cover the rules no fixture has.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
import yaml

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.constants import SchemaExportMode
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.export.exporter import SchemaExporter, build_base_schema_branch, build_schema_exporter
from infrahub.utils import get_models_dir
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA, LOCATION_SCHEMA, SNOW_TICKET_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

RULE_SCHEMAS = Path(__file__).parent / "schemas"
MODELS_BASE = sorted((get_models_dir() / "base").glob("*.yml"))


def _load_files(paths: list[Path]) -> list[SchemaRoot]:
    return [SchemaRoot(**yaml.safe_load(path.read_text())) for path in paths]


def _processed(roots: list[SchemaRoot]) -> SchemaBranch:
    schema_branch = build_base_schema_branch()
    for root in roots:
        schema_branch.load_schema(schema=deepcopy(root))
    schema_branch.process()
    return schema_branch


def _dump(exporter: SchemaExporter, schema_branch: SchemaBranch, mode: SchemaExportMode) -> dict[str, Any]:
    return exporter.export(schema_branch=schema_branch, namespaces=None, mode=mode).model_dump(
        mode="json", exclude_unset=True
    )


@pytest.fixture(scope="module")
def exporter() -> SchemaExporter:
    return build_schema_exporter(infrahub_version="1.13.0")


def assert_round_trip(exporter: SchemaExporter, roots: list[SchemaRoot], mode: SchemaExportMode) -> None:
    source = _processed(roots=roots)
    payload = _dump(exporter=exporter, schema_branch=source, mode=mode)

    loaded = SchemaLoadAPI.model_validate(payload)
    assert loaded.contract_warnings == []
    target = _processed(roots=[loaded.internal_schema])

    assert _dump(exporter=exporter, schema_branch=target, mode=SchemaExportMode.FULL) == _dump(
        exporter=exporter, schema_branch=source, mode=SchemaExportMode.FULL
    )
    assert _dump(exporter=exporter, schema_branch=target, mode=mode) == payload
    # Warnings are reported per element, so a deprecated field may warn on more elements but never on a new field.
    source_warnings = {warning.message for root in roots for warning in root.gather_warnings()}
    assert {warning.message for warning in loaded.internal_schema.gather_warnings()} <= source_warnings


@dataclass
class RoundTripCase:
    name: str
    roots: list[SchemaRoot]


RULE_CASES = [
    RoundTripCase(name="cars-people-tags", roots=[CAR_SCHEMA]),
    RoundTripCase(name="devices-with-templates", roots=[DEVICE_SCHEMA]),
    RoundTripCase(name="hierarchical-locations", roots=[LOCATION_SCHEMA]),
    RoundTripCase(name="number-pool-shorthand", roots=[SNOW_TICKET_SCHEMA]),
    *[RoundTripCase(name=path.stem, roots=_load_files(paths=[path])) for path in sorted(RULE_SCHEMAS.glob("*.yml"))],
]


@pytest.mark.parametrize("mode", [SchemaExportMode.BRIEF, SchemaExportMode.FULL])
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RULE_CASES])
def test_rule_schema_round_trip(exporter: SchemaExporter, case: RoundTripCase, mode: SchemaExportMode) -> None:
    assert_round_trip(exporter=exporter, roots=case.roots, mode=mode)


class _ModelsRoundTrip:
    """One class per model set, so the slow round trips spread over the test workers."""

    FILES: ClassVar[list[Path]]

    @pytest.mark.parametrize("mode", [SchemaExportMode.BRIEF, SchemaExportMode.FULL])
    def test_round_trip(self, exporter: SchemaExporter, mode: SchemaExportMode) -> None:
        assert_round_trip(exporter=exporter, roots=_load_files(paths=self.FILES), mode=mode)


# `extension_power.yml` declares nodes in the restricted `Template` namespace and `extension_rack.yml` needs
# `InfraSite`, which no base schema defines: neither loads through the API, so neither is exported.
EXAMPLES = get_models_dir() / "examples"


class TestModelsBase(_ModelsRoundTrip):
    FILES = MODELS_BASE


class TestExampleContract(_ModelsRoundTrip):
    FILES = [*MODELS_BASE, EXAMPLES / "extension_contract.yml"]


class TestExamplePeeringManager(_ModelsRoundTrip):
    FILES = [*MODELS_BASE, EXAMPLES / "extension_peering_manager.yml"]


class TestExampleIpamKindOverride(_ModelsRoundTrip):
    FILES = [*MODELS_BASE, EXAMPLES / "ipam_kind_override.yml"]


class TestExampleSecurity(_ModelsRoundTrip):
    FILES = [*MODELS_BASE, EXAMPLES / "security" / "infrastructure_security.yml"]


class TestExampleIpFabric(_ModelsRoundTrip):
    FILES = [EXAMPLES / "ipfabric" / "ipfabric.yml"]


class TestExampleNautobotV1(_ModelsRoundTrip):
    FILES = [EXAMPLES / "nautobot" / "nautobot-v1.yml"]


class TestExampleNautobotV2(_ModelsRoundTrip):
    FILES = [EXAMPLES / "nautobot" / "nautobot-v2.yml"]


class TestExampleNetbox(_ModelsRoundTrip):
    FILES = [EXAMPLES / "netbox" / "netbox.yml"]


class TestExampleSlurpit(_ModelsRoundTrip):
    FILES = [EXAMPLES / "slurpit" / "slurpit.yml"]


def test_selected_namespace_derives_from_the_namespaces_it_references(exporter: SchemaExporter) -> None:
    root = SchemaRoot(
        nodes=[
            {"name": "Rack", "namespace": "Dcim", "branch": "local", "attributes": [{"name": "name", "kind": "Text"}]},
            {
                "name": "Switch",
                "namespace": "Network",
                "attributes": [{"name": "name", "kind": "Text"}],
                "relationships": [{"name": "rack", "peer": "DcimRack", "cardinality": "one", "optional": True}],
            },
        ]
    )
    source = _processed(roots=[root])
    assert source.get_node(name="NetworkSwitch").get_relationship(name="rack").branch == "local"

    exported = exporter.export(schema_branch=source, namespaces=["Network"], mode=SchemaExportMode.BRIEF)

    assert exported.model_dump(mode="json", exclude_unset=True)["nodes"] == [
        {
            "name": "Switch",
            "namespace": "Network",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [{"name": "rack", "peer": "DcimRack", "cardinality": "one"}],
        }
    ]
