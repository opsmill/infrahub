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
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.merge.recompute_coalescing import MergeChange
    from infrahub.core.schema.schema_branch_computed import TransformReadSet

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
        "COALESCED_PYTHON widened to whole kind",
        kind=target.target_kind,
        attribute=target.attribute_name,
        reason=reason,
    )
    return replace(target, precise=False, whole_kind=True, reader_lookups=frozenset())


def _node_count(target: AffectedTarget) -> int:
    return len({node_id for lookup in target.reader_lookups for node_id in lookup.source_node_ids})


def just_before(moment: Timestamp) -> Timestamp:
    """The largest representable instant before ``moment``.

    A merge or rebase closes a deleted node's edges at its own timestamp, and a query at that
    same timestamp no longer sees them, so the readers have to be resolved one step earlier.
    One microsecond is enough and cannot skip a real change: the timestamp is stamped under the
    merge lock with writes already blocked, so nothing can land in the gap.
    """
    return Timestamp(moment.get_obj().subtract(microseconds=1))


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


class DroppingPythonTargetResolver:
    """Removes every Python target, leaving the per-node automations as the only path.

    What the feature switch selects when it is turned off. Dropping the targets here rather
    than skipping the resolution step keeps the rule that a target never reaches submission
    without ids.
    """

    async def resolve(
        self,
        *,
        coalesced: CoalescedRecompute,
        changes: Sequence[MergeChange],  # noqa: ARG002  part of the protocol
        branch: str,  # noqa: ARG002  part of the protocol
        deleted_at: Timestamp | None,  # noqa: ARG002  part of the protocol
    ) -> CoalescedRecompute:
        return replace_python_targets(coalesced, [])


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
        self._log_selection(resolved=resolved, considered=len(python_targets), branch=branch)
        return replace_python_targets(coalesced, resolved)

    @staticmethod
    def _log_selection(*, resolved: list[AffectedTarget], considered: int, branch: str) -> None:
        """Say what the pass chose, so a merge that recomputed too much can be read from the logs.

        A whole-kind target has no node count to report; it is named as such instead.
        """
        selected = [
            f"{target.target_kind}.{target.attribute_name}="
            + ("whole-kind" if target.whole_kind else str(_node_count(target)))
            for target in sorted(resolved, key=lambda item: (item.target_kind, item.attribute_name or ""))
        ]
        log.info(
            "COALESCED_PYTHON selected targets",
            branch=branch,
            considered=considered,
            selected=len(resolved),
            widened=sum(1 for target in resolved if target.whole_kind),
            targets=selected,
        )

    async def _readers_of(
        self,
        *,
        live_ids: frozenset[str],
        gone_ids: frozenset[str],
        branch: str,
        deleted_at: Timestamp | None,
    ) -> dict[str, frozenset[str]]:
        """Who reads the changed nodes, taking the deleted ones at a point before they went.

        A deleted node's membership records are already closed, so a current-time lookup finds
        nothing for it. Resolving the whole set at the earlier time instead would hide a
        membership the merge itself created, which is its own under-recompute, so the two halves
        are looked up separately and unioned.
        """
        readers: dict[str, set[str]] = {}
        lookups = [(live_ids, None), (gone_ids, deleted_at)]
        for node_ids, at in lookups:
            if not node_ids:
                continue
            found = await self.subscriber_lookup.readers_of(node_ids=node_ids, branch=branch, at=at)
            for kind, ids in found.items():
                readers.setdefault(kind, set()).update(ids)
        return {kind: frozenset(ids) for kind, ids in readers.items()}

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
        if read_set is None or read_set.depends_on_everything:
            return widen(target, reason="read set is imprecise" if read_set else "no read set for the attribute")

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
        live_ids = frozenset(change.node_id for change in selected if change.action != DELETED)
        gone_ids = frozenset(change.node_id for change in selected if change.action == DELETED)

        if gone_ids and deleted_at is None:
            return widen(target, reason="a deleted node has no point in time to resolve its readers at")

        if live_ids or gone_ids:
            try:
                readers = await self._readers_of(
                    live_ids=live_ids, gone_ids=gone_ids, branch=branch, deleted_at=deleted_at
                )
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
