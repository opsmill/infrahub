"""Derive the Python transform computed attributes a merge or rebase change set affects.

A Python transform computed attribute declares no dependency graph: what it reads is only known
from its GraphQL query, and which nodes read a given node is only known from the query groups those
nodes subscribed to when they last computed. Both are database facts, so they arrive through the two
source protocols below and the narrowing itself stays free of any database or client import.

Over-recompute is acceptable here, under-recompute is not: every signal that cannot be narrowed
safely widens to the whole target kind and is logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from infrahub.computed_attribute.scoping import (
    ComputedAttributeRef,
    PythonTransformDependencyDeriver,
    RecomputeScoper,
)
from infrahub.core.constants import ComputedAttributeKind
from infrahub.log import get_logger

from .recompute_coalescing import (
    CREATED,
    DELETED,
    PYTHON_COMPUTED_ATTRIBUTE,
    SELF_FILTER,
    UPDATED,
    AffectedTarget,
    ChangeSignature,
    ReaderLookup,
    group_ids_by_signature,
)

log = get_logger()

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.computed_attribute.scoping import ChangedElementSet
    from infrahub.core.query_group.subscribers import SubscriberRef
    from infrahub.core.schema.schema_branch_computed import TransformReadSet

    from .recompute_coalescing import MergeChange


@dataclass(frozen=True)
class PythonAttributeReadSet:
    """One Python transform computed attribute and the schema elements its query reads."""

    kind: str
    attribute_name: str
    read_set: TransformReadSet


class PythonReadSetSource(Protocol):
    """The read set of every Python transform computed attribute declared on a branch.

    An attribute whose query cannot be analyzed still has to be reported, with an imprecise read
    set, so that it widens instead of dropping out of the change set unnoticed.
    """

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]: ...


class PythonSubscriberSource(Protocol):
    """The nodes subscribed to a query group that holds any of ``node_ids`` as a member."""

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]: ...


@dataclass(frozen=True)
class _Selection:
    """Why one change signature selects one attribute, and how exactly.

    ``self_ids`` and ``reader_lookup`` are independent: a changed node can be both a target of
    its own and a source whose readers have to be resolved.
    """

    widen: bool
    self_ids: bool
    reader_lookup: bool
    precise: bool


@dataclass
class _Accumulator:
    kind: str
    attribute_name: str
    self_ids: set[str] = field(default_factory=set)
    source_ids: set[str] = field(default_factory=set)
    deleted_source_ids: set[str] = field(default_factory=set)
    precise: bool = True
    whole_kind: bool = False

    def add(self, *, selection: _Selection, node_ids: set[str], deleted: bool) -> None:
        if selection.widen:
            self.whole_kind = True
        else:
            if selection.self_ids:
                self.self_ids.update(node_ids)
            if selection.reader_lookup:
                sources = self.deleted_source_ids if deleted else self.source_ids
                sources.update(node_ids)
        if not selection.precise:
            self.precise = False

    @property
    def lookups(self) -> tuple[frozenset[str], ...]:
        """The id sets to resolve readers for, deleted nodes apart from live ones.

        A deleted node id empties the lookup it shares with live ids, which would drop the readers
        of the live changes with it.
        """
        return tuple(frozenset(ids) for ids in (self.source_ids, self.deleted_source_ids) if ids)


class PythonTargetResolver:
    """Map a merge or rebase change set to the Python computed attributes it affects.

    One instance serves one pass: the read-set index is fetched once per branch, and reader
    resolution is memoised on the set of changed ids it runs over, so attributes selected by the
    same changes share a single union query instead of one query per changed node. Keying the
    memo on the id set rather than sharing one union across every attribute is what keeps an
    attribute from inheriting the subscribers of changes that cannot affect it.
    """

    def __init__(
        self,
        *,
        read_set_source: PythonReadSetSource,
        subscriber_source: PythonSubscriberSource,
    ) -> None:
        self.read_set_source = read_set_source
        self.subscriber_source = subscriber_source
        self._read_sets: dict[str, list[PythonAttributeReadSet]] = {}
        self._subscriber_cache: dict[tuple[str, frozenset[str]], list[SubscriberRef]] = {}

    async def resolve(
        self,
        *,
        changes: Iterable[MergeChange],
        branch: str,
        schema_changed_elements: ChangedElementSet | None = None,
    ) -> list[AffectedTarget]:
        """Derive the affected Python computed attributes and the nodes to recompute for each.

        Changes are grouped by their (kind, action, changed fields) signature so the narrowing runs
        once per distinct shape. Targets are deduplicated per (kind, attribute) across the whole
        change set and returned in a deterministic order.

        A merge that changed the schema also drives the schema-scoped backfill, which refreshes the
        attributes it selects one whole kind at a time. Those pairs are dropped here, since keeping
        them would recompute the same nodes twice.
        """
        ids_by_signature = group_ids_by_signature(changes)

        read_sets = await self._load_read_sets(branch=branch)
        accumulators: dict[tuple[str, str], _Accumulator] = {}
        for signature, node_ids in ids_by_signature.items():
            for attribute in read_sets:
                selection = _select(signature=signature, attribute=attribute)
                if selection is None:
                    continue
                key = (attribute.kind, attribute.attribute_name)
                accumulator = accumulators.setdefault(
                    key, _Accumulator(kind=attribute.kind, attribute_name=attribute.attribute_name)
                )
                accumulator.add(selection=selection, node_ids=node_ids, deleted=signature.action == DELETED)

        covered = (
            _covered_by_schema_pass(read_sets=read_sets, branch=branch, changed_elements=schema_changed_elements)
            if schema_changed_elements is not None
            else set()
        )
        targets = [
            await self._build_target(accumulator=accumulators[key], branch=branch)
            for key in sorted(accumulators)
            if key not in covered
        ]
        selected = [target for target in targets if target is not None]
        _log_selection(branch=branch, selected=selected, covered=sorted(covered & set(accumulators)))
        return selected

    async def _build_target(self, *, accumulator: _Accumulator, branch: str) -> AffectedTarget | None:
        identity = f"{accumulator.kind}.{accumulator.attribute_name}"
        target_ids = set(accumulator.self_ids)
        whole_kind = accumulator.whole_kind
        if whole_kind:
            log.info("Widening the recompute of %s to its whole kind: the read set is undeterminable", identity)
        else:
            for node_ids in accumulator.lookups:
                try:
                    refs = await self._subscribers_for(branch=branch, node_ids=node_ids)
                except Exception:
                    log.exception("Widening the recompute of %s to its whole kind: the reader lookup failed", identity)
                    whole_kind = True
                    break
                target_ids.update(ref.id for ref in refs if ref.kind == accumulator.kind)

        if whole_kind:
            return AffectedTarget(
                family=PYTHON_COMPUTED_ATTRIBUTE,
                target_kind=accumulator.kind,
                attribute_name=accumulator.attribute_name,
                reads_across_relationship=False,
                reader_lookups=frozenset(),
                precise=False,
                whole_kind=True,
            )

        if not target_ids:
            return None

        return AffectedTarget(
            family=PYTHON_COMPUTED_ATTRIBUTE,
            target_kind=accumulator.kind,
            attribute_name=accumulator.attribute_name,
            reads_across_relationship=False,
            reader_lookups=frozenset(
                {
                    ReaderLookup(
                        source_kind=accumulator.kind,
                        filter_key=SELF_FILTER,
                        source_node_ids=frozenset(target_ids),
                    )
                }
            ),
            precise=accumulator.precise,
        )

    async def _load_read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        cached = self._read_sets.get(branch)
        if cached is None:
            cached = await self.read_set_source.read_sets(branch=branch)
            self._read_sets[branch] = cached
        return cached

    async def _subscribers_for(self, *, branch: str, node_ids: frozenset[str]) -> list[SubscriberRef]:
        cached = self._subscriber_cache.get((branch, node_ids))
        if cached is None:
            cached = await self.subscriber_source.subscribers(node_ids=sorted(node_ids), branch=branch)
            self._subscriber_cache[branch, node_ids] = cached
        return cached


def _covered_by_schema_pass(
    *, read_sets: list[PythonAttributeReadSet], branch: str, changed_elements: ChangedElementSet
) -> set[tuple[str, str]]:
    """The (kind, attribute) pairs the schema-scoped backfill refreshes for this schema change.

    The same scoping decision runs on both sides, so what one selects is exactly what the other can
    drop. A pair it does not select is left alone here: the diff-driven narrowing is the only thing
    that reaches it.

    An attribute whose read set could not be determined is never covered. The schema pass builds its
    candidates from the transforms it could gather, so a pair nothing could analyze is exactly the
    pair it never submits, and dropping it here would leave it stale.
    """
    determinable = [attribute for attribute in read_sets if not attribute.read_set.depends_on_everything]
    scoper = RecomputeScoper(
        derivers={
            ComputedAttributeKind.TRANSFORM_PYTHON: PythonTransformDependencyDeriver(
                read_sets={
                    (branch, attribute.kind, attribute.attribute_name): attribute.read_set for attribute in determinable
                }
            )
        }
    )
    report = scoper.scope(
        candidate_attributes=[
            ComputedAttributeRef(
                branch=branch,
                kind=attribute.kind,
                attribute_name=attribute.attribute_name,
                computed_kind=ComputedAttributeKind.TRANSFORM_PYTHON,
            )
            for attribute in determinable
        ],
        changed_elements=changed_elements,
    )
    return {(ref.kind, ref.attribute_name) for ref in report.selected}


def _log_selection(*, branch: str, selected: list[AffectedTarget], covered: list[tuple[str, str]]) -> None:
    """Report what the pass recomputes, so an operator can tell narrowing from widening.

    A change set that affects no Python attribute says nothing: on a deployment without any, this
    runs on every merge, every rebase and every chained level.
    """
    if not selected and not covered:
        return

    log.info(
        "Coalesced Python recompute on branch %s selected %s, and left %s to the schema pass",
        branch,
        [_target_summary(target) for target in selected] or "nothing",
        [f"{kind}.{attribute_name}" for kind, attribute_name in covered] or "nothing",
    )


def _target_summary(target: AffectedTarget) -> str:
    if target.whole_kind:
        return f"{target.target_kind}.{target.attribute_name}=whole-kind"
    node_count = sum(len(lookup.source_node_ids) for lookup in target.reader_lookups)
    return f"{target.target_kind}.{target.attribute_name}={node_count} node(s)"


def _select(*, signature: ChangeSignature, attribute: PythonAttributeReadSet) -> _Selection | None:
    """Decide whether one change signature affects one attribute, or return None when it cannot.

    Raises:
        ValueError: on a change action the narrowing has no rule for, since guessing one would risk
            leaving a value stale.

    """
    if signature.action == CREATED:
        # A created node subscribes to no query group yet, so it can only be its own target.
        return (
            _Selection(widen=False, self_ids=True, reader_lookup=False, precise=True)
            if attribute.kind == signature.kind
            else None
        )

    if signature.action not in {UPDATED, DELETED}:
        raise ValueError(f"Unknown change action: {signature.action!r}")

    return _select_reader(signature=signature, read_set=attribute.read_set, target_kind=attribute.kind)


def _select_reader(*, signature: ChangeSignature, read_set: TransformReadSet, target_kind: str) -> _Selection | None:
    """Decide whether an update or a deletion of ``signature.kind`` moves what the query reads.

    The field filter is dropped for one kind at a time, never for the whole read set: a query that
    reads a derived field of one kind still rejects an unread field of another. Collapsing the set
    would leave a chained level selecting nodes the change cannot affect.

    An updated node of the target kind is also a target of its own, not only a source to resolve
    readers for. The reverse lookup finds it only through the query group it subscribed to on its
    last successful compute, so a node that never computed would stay stale.
    """
    if read_set.depends_on_everything:
        return _Selection(widen=True, self_ids=False, reader_lookup=False, precise=False)

    if signature.kind not in read_set.read_kinds:
        return None

    if signature.action == DELETED:
        # Every field the query read is gone with the node, so dropping the field filter is exact.
        return _Selection(widen=False, self_ids=False, reader_lookup=True, precise=True)

    self_ids = signature.kind == target_kind

    if not signature.changed_fields or signature.kind in read_set.imprecise_kinds:
        # Nothing to filter on, or a derived read whose backing fields cannot be named.
        return _Selection(widen=False, self_ids=self_ids, reader_lookup=True, precise=False)

    if signature.changed_fields & read_set.read_fields.get(signature.kind, frozenset()):
        return _Selection(widen=False, self_ids=self_ids, reader_lookup=True, precise=True)

    return None
