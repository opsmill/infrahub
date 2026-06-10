"""Shared plumbing for the data-slice fixtures (see package docstring)."""

from __future__ import annotations

import pytest
from constants import ADMIN_API_TOKEN
from infrahub_sdk import Config, InfrahubClientSync


@pytest.fixture(scope="session")
def data_client(infrahub_address: str) -> InfrahubClientSync:
    """Admin sync client dedicated to loading the dataset.

    Separate from ``infrahub_client`` so the load-time constraints do not leak
    into test-time API usage: data loads against the load-balanced
    multi-replica server must run with ``max_concurrent_execution=1`` —
    higher concurrency races writers against replicas that have not seen the
    write yet and fails with read-after-write errors ("Unable to find the
    node <id> in the database"), exactly why the script-based loader exported
    INFRAHUB_MAX_CONCURRENT_EXECUTION=1 for its infrahubctl subprocess.
    """
    return InfrahubClientSync(
        config=Config(
            address=infrahub_address,
            api_token=ADMIN_API_TOKEN,
            max_concurrent_execution=1,
        )
    )
