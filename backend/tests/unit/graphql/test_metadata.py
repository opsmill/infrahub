from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import MetadataOptions
from infrahub.core.schema import MainSchemaTypes
from infrahub.graphql.metadata import build_metadata_query_options
from tests.helpers.schema import TICKET


@dataclass(frozen=True)
class SourceSelectionCase:
    name: str
    node_fields: dict[str, Any]
    schema: MainSchemaTypes | None
    expected: MetadataOptions


SOURCE_SELECTION_CASES = [
    SourceSelectionCase(
        name="source_on_a_number_attribute_reads_the_tracking_pool",
        node_fields={"ticket_id": {"value": None, "source": {"id": None}}},
        schema=TICKET,
        expected=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    ),
    SourceSelectionCase(
        name="source_on_a_text_attribute_reads_the_source_only",
        node_fields={"title": {"value": None, "source": {"id": None}}},
        schema=TICKET,
        expected=MetadataOptions.SOURCE,
    ),
    SourceSelectionCase(
        name="owner_on_a_number_attribute_does_not_read_the_pool",
        node_fields={"ticket_id": {"value": None, "owner": {"id": None}}},
        schema=TICKET,
        expected=MetadataOptions.OWNER,
    ),
    SourceSelectionCase(
        name="source_without_a_schema_reads_the_tracking_pool",
        node_fields={"title": {"value": None, "source": {"id": None}}},
        schema=None,
        expected=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    ),
    SourceSelectionCase(
        name="a_value_alone_reads_no_metadata",
        node_fields={"ticket_id": {"value": None}},
        schema=TICKET,
        expected=MetadataOptions.NONE,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SOURCE_SELECTION_CASES])
def test_a_source_selection_on_a_pool_tracked_attribute_asks_for_its_tracking_pool(case: SourceSelectionCase) -> None:
    options = build_metadata_query_options(node_fields=case.node_fields, schema=case.schema)

    assert options.attribute_level == case.expected
