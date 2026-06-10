"""Env-gated parity-dump entry points (not regression tests).

Skipped unless INFRAHUB_E2E_PARITY is set; see data/parity.py for the workflow.
Implemented as pytest "tests" so they reuse the whole harness for free: the
testcontainers stack bring-up, the dual external/local mode and the data
fixtures themselves. One gated test per mode (direct fixture dependencies —
async fixtures cannot be resolved lazily via request.getfixturevalue).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from data.parity import build_parity_dump

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

_MODE = os.environ.get("INFRAHUB_E2E_PARITY") or ""
_SKIP_REASON = "parity dump tool; set INFRAHUB_E2E_PARITY=monolith|fixtures to produce a dump"


async def _dump(client: InfrahubClient, mode: str) -> None:
    dump = await build_parity_dump(client)
    out_path = Path(os.environ.get("INFRAHUB_E2E_PARITY_OUT") or f"parity-{mode}.json")
    out_path.write_text(  # noqa: ASYNC240  (one-shot dump tool; a blocking write is fine here)
        json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert dump["counts"], "empty dump — was the dataset loaded?"


@pytest.mark.skipif(_MODE != "monolith", reason=_SKIP_REASON)
async def test_dump_dataset_monolith(infrastructure_data_monolith: None, infrahub_client: InfrahubClient) -> None:
    """Dump a stack loaded by `infrahubctl run models/infrastructure_edge.py`."""
    await _dump(infrahub_client, "monolith")


@pytest.mark.skipif(_MODE != "fixtures", reason=_SKIP_REASON)
async def test_dump_dataset_fixtures(infrastructure_data: None, infrahub_client: InfrahubClient) -> None:
    """Dump a stack loaded by the tests/e2e/data/ SDK slices."""
    await _dump(infrahub_client, "fixtures")
