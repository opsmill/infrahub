"""Env-gated parity-dump entry point (not a regression test).

Skipped unless INFRAHUB_E2E_PARITY is set; see data/parity.py for the workflow.
Implemented as a pytest "test" so it reuses the whole harness for free: the
testcontainers stack bring-up, the dual external/local mode and the data
fixtures themselves.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from data.parity import build_parity_dump

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync

# mode -> the session fixture that loads the dataset that way.
MODES = {
    "monolith": "infrastructure_data",  # infrahubctl run models/infrastructure_edge.py
    "fixtures": "infrastructure_data_sdk",  # the data/ package slices
}


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_E2E_PARITY"),
    reason="parity dump tool; set INFRAHUB_E2E_PARITY=monolith|fixtures to produce a dump",
)
class TestParityDump:
    def test_dump_dataset(self, request: pytest.FixtureRequest, infrahub_client: InfrahubClientSync) -> None:
        mode = os.environ["INFRAHUB_E2E_PARITY"]
        if mode not in MODES:
            raise pytest.UsageError(f"INFRAHUB_E2E_PARITY must be one of {sorted(MODES)}, got {mode!r}")

        request.getfixturevalue(MODES[mode])

        dump = build_parity_dump(infrahub_client)
        out_path = Path(os.environ.get("INFRAHUB_E2E_PARITY_OUT") or f"parity-{mode}.json")
        out_path.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        assert dump["counts"], "empty dump — was the dataset loaded?"
