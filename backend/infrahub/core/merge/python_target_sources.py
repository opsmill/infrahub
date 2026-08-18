"""Database-backed sources for the Python target narrowing.

Separate from the narrowing itself so the decision logic stays testable without a database,
and so the modules that touch the client and the graph are the only ones importing them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.computed_attribute.gather import gather_python_transform_attributes
from infrahub.core.merge.python_target_resolution import (
    DroppingPythonTargetResolver,
    NarrowingPythonTargetResolver,
)
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.events.limits import get_submission_chunk_size
from infrahub.log import get_logger
from infrahub.utilities.chunks import chunked

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.merge.python_target_resolution import PythonTargetResolver
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

log = get_logger()

LOOKUP_TIMEOUT_SECONDS = 30
"""Bound on one subscriber lookup.

The merge path holds the global merge lock while this runs, so a lookup that hangs must fail
fast and widen rather than block every other merge on the instance.
"""


class DatabaseReadFieldIndex:
    """Derives, per branch, the kinds and fields each Python computed attribute's query reads.

    Cached against the schema hash rather than left uncached or cached on the branch alone. The
    hash changes whenever the schema does, so a rebuild cannot be served a stale index, which was
    the reason for deriving it every time. The cache lives on the instance, which is built once per
    merge or rebase, so what it saves is the repeat derivation at each level of a recompute chain.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self._cache: dict[tuple[str, str], dict[tuple[str, str], TransformReadSet]] = {}

    async def for_branch(self, *, branch: str) -> dict[tuple[str, str], TransformReadSet]:
        schema_hash = registry.schema.get_schema_branch(name=branch).get_hash()
        cached = self._cache.get((branch, schema_hash))
        if cached is not None:
            return cached

        attributes = await gather_python_transform_attributes(db=self.db, branch_name=branch)
        index: dict[tuple[str, str], TransformReadSet] = {}
        for attribute in attributes:
            key = (attribute.computed_attribute.kind, attribute.computed_attribute.attribute.name)
            index[key] = TransformReadSet.from_read_fields(
                {kind: access.fields for kind, access in attribute.query_analyzer.query_report.requested_read.items()}
            )
        self._cache = {(branch, schema_hash): index}
        return index


class ClientSubscriberLookup:
    """Resolves which nodes read a set of changed nodes, through the query subscriber groups.

    Chunked at the submission size already in use, so the number of round trips follows the
    change set divided by that bound rather than the changed-node count.
    """

    def __init__(self, client: InfrahubClient, lookup_timeout: int) -> None:
        self.client = client
        self.lookup_timeout = lookup_timeout

    async def readers_of(
        self, *, node_ids: frozenset[str], branch: str, at: Timestamp | None
    ) -> dict[str, frozenset[str]]:
        if not node_ids:
            return {}
        readers: dict[str, set[str]] = {}
        chunk_size = get_submission_chunk_size()
        for chunk in chunked(sorted(node_ids), chunk_size):
            refs = await fetch_subscriber_refs(
                client=self.client,
                node_ids=list(chunk),
                branch=branch,
                at=at,
                request_timeout=self.lookup_timeout,
            )
            for ref in refs:
                readers.setdefault(ref.kind, set()).add(ref.id)
        return {kind: frozenset(ids) for kind, ids in readers.items()}


def build_python_target_resolver(
    *, db: InfrahubDatabase, client: InfrahubClient, enabled: bool, lookup_timeout: int = LOOKUP_TIMEOUT_SECONDS
) -> PythonTargetResolver:
    """Pick the resolver the coalesced pass runs with.

    ``enabled`` comes from the feature switch. Turning it off selects the resolver that drops
    the family, which is what restores the per-node behaviour without any other code path
    having to know the switch exists.
    """
    if not enabled:
        return DroppingPythonTargetResolver()
    return NarrowingPythonTargetResolver(
        read_field_index=DatabaseReadFieldIndex(db=db),
        subscriber_lookup=ClientSubscriberLookup(client=client, lookup_timeout=lookup_timeout),
    )
