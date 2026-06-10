"""Shared plumbing for the data-slice fixtures (see package docstring)."""

from __future__ import annotations

import os

import pytest
from constants import ADMIN_API_TOKEN
from infrahub_sdk import Config, InfrahubClient


@pytest.fixture(scope="session")
def data_client(infrahub_address: str) -> InfrahubClient:
    """Admin async client dedicated to loading the dataset.

    Separate from ``infrahub_client`` so load-time tuning never leaks into
    test-time API usage. Loads run CONCURRENTLY (the SDK default of 5,
    overridable via INFRAHUB_E2E_LOAD_CONCURRENCY): the two write races that
    historically forced max_concurrent_execution=1 are fixed at their sources —
    symmetric cardinality-one pairs save sequentially inside one batch task
    (see data/sites.py), and the backend retries creates on the transient
    read anomaly hit when concurrent creates reference the same peer node
    (see retry_db_transaction(name="object_create")). Determinism is
    unaffected: every pool allocation is a sequential await and batches only
    carry independent saves; the parity dump (data/parity.py) is the gate for
    any loader change.
    """
    return InfrahubClient(
        config=Config(
            address=infrahub_address,
            api_token=ADMIN_API_TOKEN,
            max_concurrent_execution=int(os.environ.get("INFRAHUB_E2E_LOAD_CONCURRENCY") or "5"),
        )
    )
