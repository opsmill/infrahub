"""Narrowing of the Python targets of a coalesced recompute.

The builder emits Python targets unfiltered, because the data needed to narrow them lives in
the database rather than the schema: which fields a transform's query reads, and which nodes
read a changed node. This module supplies that data and applies the narrowing.

The narrowing is not an optimisation. The per-node automations it replaces already filter on
the transform's read fields, so a coalesced pass that skipped the filter would recompute more
nodes than the path it replaces.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from infrahub.core.merge.recompute_coalescing import PYTHON_ATTRIBUTE, AffectedTarget, CoalescedRecompute
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch_computed import TransformReadSet
    from infrahub.core.timestamp import Timestamp

log = get_logger()


class ReadFieldIndex(Protocol):
    """The kinds and fields each Python computed attribute's query reads.

    Derived from the stored query text, so it needs a database pass. Injected rather than
    built in place, which is what lets the narrowing be exercised without one.
    """

    async def for_branch(self, *, branch: str) -> dict[tuple[str, str], TransformReadSet]: ...


class SubscriberLookup(Protocol):
    """Which nodes read the given nodes, through the query subscriber groups.

    Runtime data with no schema representation. One call covers a whole set of source ids;
    a call per node is the defect this feature exists to remove.
    """

    async def readers_of(
        self, *, node_ids: frozenset[str], branch: str, at: Timestamp | None
    ) -> dict[str, frozenset[str]]: ...


class PythonTargetResolver(Protocol):
    """Narrows the Python targets of a coalesced recompute, or widens them on doubt.

    Implementations must never raise. The caller runs inside a guard that swallows
    exceptions, so an escaping error would drop the recompute of every family rather than
    just this one.
    """

    async def resolve(
        self, *, coalesced: CoalescedRecompute, branch: str, deleted_at: Timestamp | None
    ) -> CoalescedRecompute: ...


def widen(target: AffectedTarget, *, reason: str) -> AffectedTarget:
    """Fall back to recomputing every node of the target's kind, and say why.

    Bounded to the one attribute-and-kind pair: a transform whose readers cannot be found
    never widens a different attribute, and never escalates to the whole branch.
    """
    log.debug(
        "COALESCED_PYTHON widening to whole kind: "
        f"kind={target.target_kind} attribute={target.attribute_name} reason={reason}"
    )
    return replace(target, precise=False, whole_kind=True, reader_lookups=frozenset())


def is_python(target: AffectedTarget) -> bool:
    return target.family == PYTHON_ATTRIBUTE


def replace_python_targets(coalesced: CoalescedRecompute, resolved: list[AffectedTarget]) -> CoalescedRecompute:
    """Swap the Python targets for their resolved form, leaving the other families untouched.

    The three schema-derived families must come through unchanged; only the Python ones are
    reshaped here.
    """
    others = [target for target in coalesced.targets if not is_python(target)]
    return CoalescedRecompute(branch=coalesced.branch, targets=frozenset(others + resolved))
