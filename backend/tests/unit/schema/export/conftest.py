from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema.generated.write import GenericSchemaWrite, NodeSchemaWrite

from infrahub.core.schema import SchemaRoot
from infrahub.schema.export.exporter import (
    SchemaExporter,
    build_core_schema_baseline,
    normalize_element_for_comparison,
)
from infrahub.schema.export.models import SchemaExportDocument, SchemaExportMode

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

ROUND_TRIP_BRANCH_NAME = "main"

RoundTrip = Callable[[Mapping[str, Any], SchemaExportMode], SchemaExportDocument]


@pytest.fixture
def schema_exporter() -> SchemaExporter:
    return SchemaExporter(baseline_factory=build_core_schema_baseline)


@pytest.fixture(scope="session")
def core_schema_kinds() -> frozenset[str]:
    baseline = build_core_schema_baseline(ROUND_TRIP_BRANCH_NAME)
    return frozenset(baseline.nodes) | frozenset(baseline.generics)


def load_on_new_baseline(schema: Mapping[str, Any]) -> SchemaBranch:
    schema_branch = build_core_schema_baseline(ROUND_TRIP_BRANCH_NAME)
    schema_branch.load_schema(schema=SchemaRoot(**schema))
    schema_branch.process()
    return schema_branch


def user_defined_elements(schema_branch: SchemaBranch, core_kinds: frozenset[str]) -> dict[str, dict[str, Any]]:
    elements = {
        kind: normalize_element_for_comparison(
            schema_branch.get(name=kind, duplicate=False).model_dump(), write_model=NodeSchemaWrite
        )
        for kind in sorted(set(schema_branch.nodes) - core_kinds)
    }
    elements.update(
        {
            kind: normalize_element_for_comparison(
                schema_branch.get(name=kind, duplicate=False).model_dump(), write_model=GenericSchemaWrite
            )
            for kind in sorted(set(schema_branch.generics) - core_kinds)
        }
    )
    return elements


def document_without_infrahub_version(document: SchemaExportDocument) -> dict[str, Any]:
    return document.model_dump(exclude_unset=True, exclude={"infrahub_version"})


@pytest.fixture
def schema_round_trip(schema_exporter: SchemaExporter, core_schema_kinds: frozenset[str]) -> RoundTrip:
    """Export a test schema, load the export on an empty schema, and assert that both give the same schema.

    The returned function also asserts that exporting the loaded schema gives the same document again, and
    returns the first document.
    """

    def round_trip(schema: Mapping[str, Any], mode: SchemaExportMode) -> SchemaExportDocument:
        source = load_on_new_baseline(schema)
        document = schema_exporter.export(schema_branch=source, mode=mode, namespaces=None)

        target = load_on_new_baseline(document_without_infrahub_version(document))
        assert user_defined_elements(target, core_schema_kinds) == user_defined_elements(source, core_schema_kinds)

        second_document = schema_exporter.export(schema_branch=target, mode=mode, namespaces=None)
        assert document_without_infrahub_version(second_document) == document_without_infrahub_version(document)
        return document

    return round_trip
