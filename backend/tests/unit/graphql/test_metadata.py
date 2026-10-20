from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import MetadataOptions
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.metadata import build_metadata_query_options
from tests.helpers.schema import CARD, POWER_SLOT, SLOT, TICKET

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

GENERIC_KIND = SLOT.kind
"""A generic declaring a Text `name`, whose one implementer adds the Number `slot_number`."""


def slot_schema_branch() -> SchemaBranch:
    power_slot = deepcopy(POWER_SLOT)
    power_slot.attributes.append(AttributeSchema(name="slot_number", kind="Number", optional=True))
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(generics=[SLOT], nodes=[power_slot, CARD]))
    schema_branch.process()
    return schema_branch


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
        name="source_on_a_field_a_node_schema_does_not_declare_reads_the_source_only",
        node_fields={"slot_number": {"value": None, "source": {"id": None}}},
        schema=TICKET,
        expected=MetadataOptions.SOURCE,
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


@dataclass(frozen=True)
class GenericSelectionCase:
    name: str
    field_name: str
    with_schema_branch: bool
    expected: MetadataOptions


GENERIC_SELECTION_CASES = [
    GenericSelectionCase(
        name="a_number_an_implementer_adds_reads_the_tracking_pool",
        field_name="slot_number",
        with_schema_branch=True,
        expected=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    ),
    GenericSelectionCase(
        name="a_text_the_generic_declares_reads_the_source_only",
        field_name="name",
        with_schema_branch=True,
        expected=MetadataOptions.SOURCE,
    ),
    GenericSelectionCase(
        name="a_field_no_implementer_declares_reads_the_source_only",
        field_name="rack_position",
        with_schema_branch=True,
        expected=MetadataOptions.SOURCE,
    ),
    GenericSelectionCase(
        name="an_undeclared_field_without_the_schema_branch_reads_the_tracking_pool",
        field_name="rack_position",
        with_schema_branch=False,
        expected=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in GENERIC_SELECTION_CASES])
def test_a_source_selection_on_a_generic_looks_the_field_up_on_its_implementers(case: GenericSelectionCase) -> None:
    schema_branch = slot_schema_branch()
    generic = schema_branch.get(name=GENERIC_KIND, duplicate=False)

    options = build_metadata_query_options(
        node_fields={case.field_name: {"value": None, "source": {"id": None}}},
        schema=generic,
        schema_branch=schema_branch if case.with_schema_branch else None,
    )

    assert options.attribute_level == case.expected
