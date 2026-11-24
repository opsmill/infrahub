from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSyncResult

NOT_CREATED = "TestingCounter.counter on branch-1: the scope does not resolve"
NOT_CHANGED = "TestingTicket.ticket: Numbers are still being allocated from the pool tickets; retry the change."


@dataclass
class RefusalCase:
    name: str
    refused_pools: list[str]
    refused_changes: list[str]
    expected: str | None


REFUSAL_CASES = [
    RefusalCase(name="nothing-refused", refused_pools=[], refused_changes=[], expected=None),
    RefusalCase(
        name="pools-not-created",
        refused_pools=[NOT_CREATED, NOT_CREATED],
        refused_changes=[],
        expected=f"Number pools not created: {NOT_CREATED}; {NOT_CREATED}",
    ),
    RefusalCase(
        name="changes-not-applied",
        refused_pools=[],
        refused_changes=[NOT_CHANGED],
        expected=f"Number pool changes not applied: {NOT_CHANGED}",
    ),
    RefusalCase(
        name="both",
        refused_pools=[NOT_CREATED],
        refused_changes=[NOT_CHANGED],
        expected=f"Number pools not created: {NOT_CREATED}\nNumber pool changes not applied: {NOT_CHANGED}",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSAL_CASES])
def test_refusal_message_names_every_refused_pool_and_change(case: RefusalCase) -> None:
    result = SchemaNumberPoolSyncResult(
        updated_branches=set(), refused_pools=case.refused_pools, refused_changes=case.refused_changes
    )

    assert result.refusal_message() == case.expected
