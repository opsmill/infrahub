from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


def _full_internal_dump() -> dict[str, Any]:
    """A full internal SchemaRoot dump, carrying read-only/internal fields (ids, state, ...)."""
    return SchemaRoot(version="1.0", generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST]).model_dump()


@dataclass
class LoadContractCase:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    accepted: bool = True
    use_full_dump: bool = False


LOAD_CONTRACT_CASES = [
    LoadContractCase(name="full-internal-dump-tolerated", use_full_dump=True, accepted=True),
    LoadContractCase(
        name="minimal-write-payload",
        payload={
            "version": "1.0",
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "Text"}]}],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="forbidden-field-on-extension-rejected",
        payload={"version": "1.0", "extensions": {"nodes": [{"kind": "BuiltinTag", "namespace": "Forbidden"}]}},
        accepted=False,
    ),
    LoadContractCase(
        name="unknown-field-on-node-rejected",
        payload={"version": "1.0", "nodes": [{"namespace": "Test", "name": "Widget", "not_a_field": 1}]},
        accepted=False,
    ),
    LoadContractCase(
        name="out-of-range-attribute-name-rejected",
        payload={
            "version": "1.0",
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "ab", "kind": "Text"}]}],
        },
        accepted=False,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in LOAD_CONTRACT_CASES])
def test_schema_load_contract(case: LoadContractCase) -> None:
    payload = _full_internal_dump() if case.use_full_dump else case.payload
    if case.accepted:
        loaded = SchemaLoadAPI.model_validate(payload)
        # the internal schema is built from the projected write payload
        assert loaded.internal_schema is not None
    else:
        with pytest.raises(ValueError, match="validation error for SchemaLoadAPI"):
            SchemaLoadAPI.model_validate(payload)
