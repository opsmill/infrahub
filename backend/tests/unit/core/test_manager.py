from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.schema import AttributeSchema
from tests.helpers.schema import TAG, TICKET

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema

TICKET_WITH_SEQUENCE = deepcopy(TICKET)
TICKET_WITH_SEQUENCE.attributes.append(AttributeSchema(name="sequence", kind="NumberPool", optional=True))


@dataclass(frozen=True)
class PoolTrackedNamesCase:
    name: str
    schemas: list[NodeSchema]
    fields: dict | None
    expected: frozenset[str]


POOL_TRACKED_NAMES_CASES = [
    PoolTrackedNamesCase(
        name="every_number_and_number_pool_attribute_when_no_fields_are_requested",
        schemas=[TICKET_WITH_SEQUENCE],
        fields=None,
        expected=frozenset({"ticket_id", "sequence"}),
    ),
    PoolTrackedNamesCase(
        name="only_the_requested_ones",
        schemas=[TICKET_WITH_SEQUENCE],
        fields={"title": None, "sequence": None},
        expected=frozenset({"sequence"}),
    ),
    PoolTrackedNamesCase(
        name="none_when_the_requested_fields_hold_no_number",
        schemas=[TICKET],
        fields={"title": None},
        expected=frozenset(),
    ),
    PoolTrackedNamesCase(
        name="none_for_a_schema_without_a_number",
        schemas=[TAG],
        fields=None,
        expected=frozenset(),
    ),
    PoolTrackedNamesCase(
        name="the_union_across_the_schemas_of_the_loaded_nodes",
        schemas=[TAG, TICKET],
        fields=None,
        expected=frozenset({"ticket_id"}),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in POOL_TRACKED_NAMES_CASES])
def test_the_tracking_pool_read_is_limited_to_the_attributes_a_pool_can_track(case: PoolTrackedNamesCase) -> None:
    assert NodeManager._pool_tracked_attribute_names(schemas=case.schemas, fields=case.fields) == case.expected
