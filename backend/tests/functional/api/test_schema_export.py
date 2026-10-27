"""The schema export served by the API loads back through the API.

A class cannot empty its database part-way, so the round trip into an empty instance uses two classes linked by
the export built in memory from the same files: the first checks that the endpoint returns it, the second loads it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import yaml

from infrahub import __version__
from infrahub.core.constants import SchemaExportMode
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.export.exporter import build_base_schema_branch, build_schema_exporter
from infrahub.utils import get_models_dir
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

MODELS_BASE = sorted((get_models_dir() / "base").glob("*.yml"))


def _base_schemas() -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text()) for path in MODELS_BASE]


def _in_memory_export(schemas: list[dict[str, Any]], mode: SchemaExportMode) -> dict[str, Any]:
    schema_branch = build_base_schema_branch()
    for schema in schemas:
        schema_branch.load_schema(schema=SchemaRoot(**schema))
    schema_branch.process()
    exporter = build_schema_exporter(infrahub_version=__version__)
    return exporter.export(schema_branch=schema_branch, namespaces=None, mode=mode).model_dump(
        mode="json", exclude_unset=True
    )


def _attribute_label(kind: str, attribute: str) -> str | None:
    schema = registry.schema.get_schema_branch(name=registry.default_branch).get(name=kind, duplicate=False)
    return schema.get_attribute(name=attribute).label


class _SchemaExportApp(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        pass


class TestSchemaExportFromLoadedSchema(_SchemaExportApp):
    async def test_endpoint_returns_the_export_of_the_loaded_files(
        self, initial_dataset: None, client: InfrahubClient
    ) -> None:
        response = await client.schema.load(schemas=_base_schemas())
        assert response.errors == {}

        for mode in (SchemaExportMode.BRIEF, SchemaExportMode.FULL):
            exported = await client.schema.export(mode=mode.value)
            assert exported.model_dump(mode="json", exclude_unset=True) == _in_memory_export(
                schemas=_base_schemas(), mode=mode
            )


class TestSchemaExportIntoEmptyInstance(_SchemaExportApp):
    @pytest.mark.parametrize("mode", [SchemaExportMode.BRIEF, SchemaExportMode.FULL])
    async def test_export_loads_without_warning_and_exports_again_identically(
        self, initial_dataset: None, client: InfrahubClient, mode: SchemaExportMode
    ) -> None:
        exported = _in_memory_export(schemas=_base_schemas(), mode=mode)

        response = await client.schema.load(schemas=[exported])

        assert response.errors == {}
        # The base schemas use deprecated fields themselves; the export may only repeat those warnings.
        source_warnings = {
            warning.message for schema in _base_schemas() for warning in SchemaRoot(**schema).gather_warnings()
        }
        assert {warning.message for warning in response.warnings} <= source_warnings
        assert (await client.schema.export(mode=mode.value)).model_dump(mode="json", exclude_unset=True) == exported


ROUTER_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Router",
            "namespace": "Existing",
            "attributes": [{"name": "hostname", "kind": "Text", "unique": True}],
        }
    ],
}


class TestSchemaExportExistingInstance(_SchemaExportApp):
    async def test_full_export_overwrites_a_label_that_brief_leaves(
        self, initial_dataset: None, client: InfrahubClient
    ) -> None:
        await client.schema.load(schemas=[ROUTER_SCHEMA])
        brief = (await client.schema.export(namespaces=["Existing"], mode="brief")).model_dump(
            mode="json", exclude_unset=True
        )
        full = (await client.schema.export(namespaces=["Existing"], mode="full")).model_dump(
            mode="json", exclude_unset=True
        )
        relabelled = {
            **ROUTER_SCHEMA,
            "nodes": [
                {
                    **ROUTER_SCHEMA["nodes"][0],
                    "attributes": [{"name": "hostname", "kind": "Text", "unique": True, "label": "Host name"}],
                }
            ],
        }
        await client.schema.load(schemas=[relabelled])
        assert _attribute_label(kind="ExistingRouter", attribute="hostname") == "Host name"

        await client.schema.load(schemas=[brief])
        assert _attribute_label(kind="ExistingRouter", attribute="hostname") == "Host name"

        await client.schema.load(schemas=[full])
        assert _attribute_label(kind="ExistingRouter", attribute="hostname") == "Hostname"


NETWORK_DCIM_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Rack",
            "namespace": "Dcim",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        },
        {
            "name": "Switch",
            "namespace": "Network",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [{"name": "rack", "peer": "DcimRack", "cardinality": "one", "optional": True}],
        },
    ],
}


class TestSchemaExportNamespaces(_SchemaExportApp):
    async def test_selected_namespace_is_exported_alone_and_loads_next_to_the_other(
        self, initial_dataset: None, client: InfrahubClient
    ) -> None:
        await client.schema.load(schemas=[NETWORK_DCIM_SCHEMA])

        exported = (await client.schema.export(namespaces=["Network"])).model_dump(mode="json", exclude_unset=True)

        assert exported == {
            "version": "1.0",
            "infrahub_version": __version__,
            "generics": [],
            "nodes": [
                {
                    "name": "Switch",
                    "namespace": "Network",
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                    "relationships": [{"name": "rack", "peer": "DcimRack", "cardinality": "one"}],
                }
            ],
        }
        response = await client.schema.load(schemas=[exported])
        assert response.errors == {}
        assert response.warnings == []
