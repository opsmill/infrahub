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

from infrahub.core.merge.recompute_coalescing import (
    CREATED,
    DELETED,
    PYTHON_ATTRIBUTE,
    AffectedTarget,
    CoalescedRecompute,
    ReaderLookup,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.merge.recompute_coalescing import MergeChange
    from infrahub.core.schema.schema_branch_computed import TransformReadSet
    from infrahub.core.timestamp import Timestamp

log = get_logger()

_SELF_FILTER = "ids"


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
        self,
        *,
        coalesced: CoalescedRecompute,
        changes: Sequence[MergeChange],
        branch: str,
        deleted_at: Timestamp | None,
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


def selects_change(change: MergeChange, read_set: TransformReadSet) -> bool:
    """Whether one changed node can affect the value of an attribute with this read set.

    A kind the query reaches but reads no field from is a kind-level dependency: its
    instances appearing or disappearing changes the result set, but editing a field on one
    cannot, because no field of it is read. A kind with read fields is selected only when a
    changed field is one of them, which is what the per-node automations already do.
    """
    if change.kind not in read_set.read_kinds:
        return False
    if change.action in (CREATED, DELETED):
        return True
    if not change.changed_fields:
        # An update that reports no field may have touched anything the query reads.
        return True
    return bool(change.changed_fields & read_set.read_fields.get(change.kind, frozenset()))


class NarrowingPythonTargetResolver:
    """Narrows each Python target to the nodes the per-node path would have refreshed.

    Widens a single attribute-and-kind pair to its whole kind whenever the narrowing cannot
    be trusted, and never lets an error escape: the caller's guard would otherwise turn one
    failed lookup into a skipped recompute for every family.
    """

    def __init__(self, read_field_index: ReadFieldIndex, subscriber_lookup: SubscriberLookup) -> None:
        self.read_field_index = read_field_index
        self.subscriber_lookup = subscriber_lookup

    async def resolve(
        self,
        *,
        coalesced: CoalescedRecompute,
        changes: Sequence[MergeChange],
        branch: str,
        deleted_at: Timestamp | None,
    ) -> CoalescedRecompute:
        python_targets = [target for target in coalesced.targets if is_python(target)]
        if not python_targets:
            return coalesced

        try:
            index = await self.read_field_index.for_branch(branch=branch)
        except Exception as exc:
            widened = [widen(target, reason=f"read-field index unavailable: {exc!r}") for target in python_targets]
            return replace_python_targets(coalesced, widened)

        resolved: list[AffectedTarget] = []
        for target in python_targets:
            resolved_target = await self._resolve_one(
                target=target, changes=changes, index=index, branch=branch, deleted_at=deleted_at
            )
            if resolved_target is not None:
                resolved.append(resolved_target)
        return replace_python_targets(coalesced, resolved)

    async def _resolve_one(
        self,
        *,
        target: AffectedTarget,
        changes: Sequence[MergeChange],
        index: dict[tuple[str, str], TransformReadSet],
        branch: str,
        deleted_at: Timestamp | None,
    ) -> AffectedTarget | None:
        key = (target.target_kind, target.attribute_name or "")
        read_set = index.get(key)
        if read_set is None:
            return widen(target, reason="no read set for the attribute")
        if read_set.depends_on_everything:
            return widen(target, reason="read set is imprecise")

        selected = [change for change in changes if selects_change(change, read_set)]
        if not selected:
            return None

        # A node that holds the attribute is a target in its own right, which is the only way a
        # created node is reached: it subscribes to no query group until its transform first runs.
        # A deleted one is not, and every selected node is still a source, because a transform can
        # read other nodes of the kind it belongs to.
        owner_ids = {
            change.node_id for change in selected if change.kind == target.target_kind and change.action != DELETED
        }
        source_ids = frozenset(change.node_id for change in selected)

        if source_ids:
            try:
                readers = await self.subscriber_lookup.readers_of(node_ids=source_ids, branch=branch, at=deleted_at)
            except Exception as exc:
                return widen(target, reason=f"subscriber lookup failed: {exc!r}")
            owner_ids |= set(readers.get(target.target_kind, frozenset()))

        if not owner_ids:
            return None
        lookup = ReaderLookup(
            source_kind=target.target_kind,
            filter_key=_SELF_FILTER,
            source_node_ids=frozenset(owner_ids),
        )
        return replace(target, reader_lookups=frozenset({lookup}), whole_kind=False)
