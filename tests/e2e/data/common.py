"""Shared plumbing for the data-slice fixtures (see package docstring)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING

import pytest
from constants import ADMIN_API_TOKEN
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode

log = logging.getLogger("infrahub.e2e.data")

# Signatures of a backend transient read anomaly: when concurrent creates
# reference the same peer node (many interfaces -> one VLAN/device), the
# non-locking reads inside the create can transiently miss the peer while its
# relationship chain is being rewritten. It surfaces either as a peer
# resolution failure ("Unable to find the node <id> in the database") or as a
# relationship row dropped from the create read-back (a bare KeyError on the
# '<relationship_identifier>::<peer_uuid>' key). Both raise inside the create
# transaction, which rolls back, so retrying the save is safe. Retrying here
# is a stopgap until the backend handles the anomaly itself.
_TRANSIENT_CREATE_PATTERNS = (
    re.compile(r"Unable to find the node"),
    re.compile(r"'[a-z0-9_]+__[a-z0-9_]+::[0-9a-f-]{36}'"),
)
_SAVE_ATTEMPTS = 4


def _is_transient_create_anomaly(exc: GraphQLError) -> bool:
    message = str(exc)
    return any(pattern.search(message) for pattern in _TRANSIENT_CREATE_PATTERNS)


async def save_with_retry(obj: InfrahubNode, allow_upsert: bool = False) -> InfrahubNode:
    """Save a node, retrying the known transient create anomalies (see above)."""
    for attempt in range(1, _SAVE_ATTEMPTS + 1):
        try:
            await obj.save(allow_upsert=allow_upsert)
        except GraphQLError as exc:
            if attempt == _SAVE_ATTEMPTS or not _is_transient_create_anomaly(exc):
                raise
            log.warning(
                "transient create anomaly on %s %s (attempt %d/%d), retrying: %s",
                obj.get_kind(),
                obj.id,
                attempt,
                _SAVE_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(0.2 * attempt)
        else:
            return obj
    raise AssertionError("unreachable")


@pytest.fixture(scope="session")
def data_client(infrahub_address: str) -> InfrahubClient:
    """Admin async client dedicated to loading the dataset.

    Separate from ``infrahub_client`` so load-time tuning never leaks into
    test-time API usage. Loads run CONCURRENTLY (the SDK default of 5,
    overridable via INFRAHUB_E2E_LOAD_CONCURRENCY): symmetric cardinality-one
    pairs save sequentially inside one batch task (see data/sites.py), and
    batched saves go through ``save_with_retry`` to absorb the backend's
    transient read anomaly on concurrent creates sharing a peer node.
    Determinism is unaffected: every pool allocation is a sequential await and
    batches only carry independent saves; the parity dump (data/parity.py) is
    the gate for any loader change.
    """
    return InfrahubClient(
        config=Config(
            address=infrahub_address,
            api_token=ADMIN_API_TOKEN,
            max_concurrent_execution=int(os.environ.get("INFRAHUB_E2E_LOAD_CONCURRENCY") or "5"),
        )
    )
