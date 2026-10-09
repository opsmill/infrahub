"""The utilization, the divisions and the tracked numbers of one number pool, as the dedicated queries report them."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.number import NumberUtilizationGetter, UtilizationFigures
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_space import SchemaAttributeDomains, to_pool_ranges
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from infrahub.pools.scope import AllocationScope, AllocationScopeResolver, Division, division_element_path

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.constants import PoolRecordProvenance
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.query.resource_manager import NumberPoolAllocatedResult
    from infrahub.core.schema import AttributeSchema, RelationshipSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import ScopeElement

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 1000
DISPLAY_LABEL_SEPARATOR = " / "


@dataclass(frozen=True)
class RangeUsage:
    id: str
    display_label: str
    start: int
    end: int
    weight: int
    figures: UtilizationFigures


@dataclass(frozen=True)
class PoolUsage:
    id: str
    display_label: str
    allocation_scope: tuple[ScopeElement, ...]
    figures: UtilizationFigures
    ranges: tuple[RangeUsage, ...]


@dataclass(frozen=True)
class DivisionEntry:
    id: str
    path: str
    value: str | float | bool
    display_label: str
    peer_kind: str | None


@dataclass(frozen=True)
class DivisionUsage:
    display_label: str
    entries: tuple[DivisionEntry, ...]
    figures: UtilizationFigures


@dataclass(frozen=True)
class PoolDivisions:
    count: int
    allocation_scope: tuple[ScopeElement, ...]
    divisions: tuple[DivisionUsage, ...]


@dataclass(frozen=True)
class HoldingObject:
    id: str
    hfid: list[str] | None
    kind: str
    display_label: str


@dataclass(frozen=True)
class RangeReference:
    id: str
    display_label: str


@dataclass(frozen=True)
class TrackedNumber:
    value: int
    branch: str
    holder: HoldingObject
    identifier: str
    provenance: PoolRecordProvenance
    range: RangeReference


@dataclass(frozen=True)
class TrackedNumbersPage:
    count: int
    allocations: tuple[TrackedNumber, ...]


@dataclass(frozen=True)
class _PoolState:
    """A pool with its scope resolved on the request branch and the ranges it allocates from."""

    pool: CoreNumberPool
    scope: AllocationScope
    element_fields: list[tuple[ScopeElement, AttributeSchema | RelationshipSchema]]
    ranges: list[CoreNumberPoolRange]
    range_labels: dict[str, str]
    domain: NumberDomain
    space: EffectiveSpace


class NumberPoolUsageReader:
    """Reads one number pool's utilization, divisions and tracked numbers, its scope resolved on the schema of `branch`."""

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        self.repository = NumberPoolRepository(db=db)

    async def utilization(self, pool_id: str, division: Sequence[tuple[str, object]] | None) -> PoolUsage:
        """Return the figures of the pool and of each range, only of `division` on a scoped pool.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When `division` is given on an unscoped pool, names no scope element or one twice, gives
                a value that does not have the type its element stores, or is missing on a scoped pool, or when the
                schema of the branch does not define a scope element.

        """
        state = await self._load(pool_id=pool_id)
        selected = self._division(state=state, entries=division)
        if not state.scope.is_empty and (selected is None or len(selected.values) != len(state.scope.elements)):
            raise ValidationError(
                f"The pool {pool_id} has an allocation scope; give a division with a value for every element "
                "to read its utilization"
            )
        getter = NumberUtilizationGetter(
            db=self.db, pool=state.pool, space=state.space, branch=self.branch, division=selected
        )
        await getter.load_data()
        ranges = sorted(state.ranges, key=lambda item: int(item.start.value))
        return PoolUsage(
            id=pool_id,
            display_label=await state.pool.get_display_label(db=self.db),
            allocation_scope=state.scope.elements,
            figures=getter.figures,
            ranges=tuple(
                RangeUsage(
                    id=item.get_id(),
                    display_label=state.range_labels[item.get_id()],
                    start=int(item.start.value),
                    end=int(item.end.value),
                    weight=item.allocation_weight.value or 0,
                    figures=getter.range_figures(range_id=item.get_id()),
                )
                for item in ranges
            ),
        )

    async def divisions(self, pool_id: str) -> PoolDivisions:
        """Return every division holding a number, ordered by utilization descending, then by display label.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When the schema of the branch does not define a scope element.

        """
        state = await self._load(pool_id=pool_id)
        if state.scope.is_empty:
            return PoolDivisions(count=0, allocation_scope=(), divisions=())
        results = await self.repository.get_divisions(
            pool=state.pool,
            branch=self.branch,
            space=state.space,
            elements=[division_element_path(field=field) for _, field in state.element_fields],
        )
        peers = await self._peers(
            ids={
                str(value)
                for result in results
                for (_, field), value in zip(state.element_fields, result.values, strict=True)
                if _is_relationship(field) and value
            }
        )
        divisions = []
        for result in results:
            entries = tuple(
                _entry(element=element, field=field, value=value, peers=peers)
                for (element, field), value in zip(state.element_fields, result.values, strict=True)
            )
            divisions.append(
                DivisionUsage(
                    display_label=DISPLAY_LABEL_SEPARATOR.join(entry.display_label for entry in entries),
                    entries=entries,
                    figures=UtilizationFigures(
                        size=state.space.size,
                        used_default_branch=result.used_default_branch,
                        used_branches=result.used_branches,
                    ),
                )
            )
        divisions.sort(key=lambda item: (-item.figures.utilization, item.display_label))
        return PoolDivisions(count=len(divisions), allocation_scope=state.scope.elements, divisions=tuple(divisions))

    async def tracked_numbers(
        self,
        pool_id: str,
        division: Sequence[tuple[str, object]] | None,
        range_id: str | None,
        branch_name: str | None,
        provenance: PoolRecordProvenance | None,
        offset: int | None,
        limit: int | None,
    ) -> TrackedNumbersPage:
        """Return one page of the numbers the pool tracks, ordered by value, branch, then holding object id.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When `offset` or `limit` is negative, `range_id` is not a range of the pool, `division`
                is given on an unscoped pool, names no scope element or one twice or gives a value that does not have
                the type its element stores, or when the schema of the branch does not define a scope element.

        """
        for name, page_value in (("offset", offset), ("limit", limit)):
            if page_value is not None and page_value < 0:
                raise ValidationError(f"{name} must be 0 or greater")
        state = await self._load(pool_id=pool_id)
        space = state.space
        if range_id is not None:
            selected_ranges = [item for item in state.ranges if item.get_id() == range_id]
            if not selected_ranges:
                raise ValidationError(f"The range {range_id} does not belong to the pool {pool_id}")
            space = EffectiveSpace(ranges=to_pool_ranges(ranges=selected_ranges), domain=state.domain)
        selected = self._division(state=state, entries=division)
        if space.is_empty:
            return TrackedNumbersPage(count=0, allocations=())

        query = await NumberPoolGetAllocated.init(
            db=self.db,
            pool=state.pool,
            ranges=space.as_query_ranges(),
            branch_name=branch_name,
            provenance=provenance,
            division=selected,
            offset=DEFAULT_OFFSET if offset is None else offset,
            limit=DEFAULT_LIMIT if limit is None else limit,
            branch=self.branch,
            branch_agnostic=True,
        )
        count = await query.count(db=self.db)
        # A query with no limit reads every row, so a page of zero rows is not read at all.
        if limit == 0:
            return TrackedNumbersPage(count=count, allocations=())
        await query.execute(db=self.db)
        rows = query.get_data()
        holders = await self._holders(rows=rows, kind=str(state.pool.get_attribute("node").value))
        return TrackedNumbersPage(
            count=count,
            allocations=tuple(
                TrackedNumber(
                    value=row.value,
                    branch=row.branch,
                    holder=holders[row.branch, row.id],
                    identifier=row.identifier,
                    provenance=row.provenance,
                    range=_range_reference(space=state.space, labels=state.range_labels, value=row.value),
                )
                for row in rows
            ),
        )

    async def _load(self, pool_id: str) -> _PoolState:
        pool = await NodeManager.get_one(
            db=self.db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, branch=self.branch, raise_on_error=True
        )
        if not isinstance(pool, CoreNumberPool):
            raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_id, branch_name=self.branch.name)
        scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool_id)
        ranges = await self.repository.get_ranges(pool_id=pool_id)
        domain = SchemaAttributeDomains(schema=self.db.schema, branch=self.branch).domain_of(
            kind=str(pool.get_attribute("node").value), attribute_name=str(pool.get_attribute("node_attribute").value)
        )
        return _PoolState(
            pool=pool,
            scope=scope,
            element_fields=self._element_fields(pool=pool, scope=scope),
            ranges=ranges,
            range_labels={item.get_id(): await item.get_display_label(db=self.db) for item in ranges},
            domain=domain,
            space=EffectiveSpace(ranges=to_pool_ranges(ranges=ranges), domain=domain),
        )

    def _element_fields(
        self, pool: CoreNumberPool, scope: AllocationScope
    ) -> list[tuple[ScopeElement, AttributeSchema | RelationshipSchema]]:
        """Return each scope element with the field that holds it on the pool's kind on the request branch.

        Raises:
            ValidationError: When the schema of the request branch does not define a scope element on the pool's kind.

        """
        resolver = AllocationScopeResolver(schema_branch=registry.schema.get_schema_branch(name=self.branch.name))
        return resolver.element_fields(kind=str(pool.get_attribute("node").value), scope=scope, pool=pool.get_id())

    @staticmethod
    def _division(state: _PoolState, entries: Sequence[tuple[str, object]] | None) -> Division | None:
        """Return the division the entries name, or None when no entry is given.

        Raises:
            ValidationError: When entries are given on an unscoped pool, name no scope element or one twice, or give a
                value that does not have the type its element stores.

        """
        if not entries:
            return None
        if state.scope.is_empty:
            raise ValidationError(
                f"The pool {state.pool.get_id()} has no allocation scope; the division filter cannot be applied"
            )
        return Division.from_entries(entries=entries, element_fields=state.element_fields)

    async def _peers(self, ids: set[str]) -> dict[str, tuple[str, str]]:
        """Return the display label and kind of each peer, read on any branch, for the peers that can be read."""
        if not ids:
            return {}
        nodes = await NodeManager.get_many(db=self.db, ids=sorted(ids), branch=self.branch, branch_agnostic=True)
        return {node_id: (await node.get_display_label(db=self.db), node.get_kind()) for node_id, node in nodes.items()}

    async def _holders(
        self, rows: Sequence[NumberPoolAllocatedResult], kind: str
    ) -> dict[tuple[str, str], HoldingObject]:
        """Return each row's holding object read on the row's branch, with one read per branch."""
        ids_by_branch: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            ids_by_branch[row.branch].add(row.id)
        holders: dict[tuple[str, str], HoldingObject] = {}
        for branch_name, ids in ids_by_branch.items():
            nodes = await NodeManager.get_many(db=self.db, ids=sorted(ids), branch=branch_name)
            for node_id in ids:
                node = nodes.get(node_id)
                holders[branch_name, node_id] = (
                    HoldingObject(
                        id=node_id,
                        hfid=await node.get_hfid(db=self.db),
                        kind=node.get_kind(),
                        display_label=await node.get_display_label(db=self.db),
                    )
                    if node is not None
                    else HoldingObject(id=node_id, hfid=None, kind=kind, display_label=node_id)
                )
        return holders


def _is_relationship(field: AttributeSchema | RelationshipSchema) -> bool:
    return division_element_path(field=field).is_relationship


def _as_text(value: str | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _entry(
    element: ScopeElement,
    field: AttributeSchema | RelationshipSchema,
    value: str | float | bool,
    peers: dict[str, tuple[str, str]],
) -> DivisionEntry:
    text = _as_text(value)
    if not _is_relationship(field):
        return DivisionEntry(id=element.id, path=element.name, value=value, display_label=text, peer_kind=None)
    display_label, peer_kind = peers.get(text, (text, None))
    return DivisionEntry(id=element.id, path=element.name, value=text, display_label=display_label, peer_kind=peer_kind)


def _range_reference(space: EffectiveSpace, labels: dict[str, str], value: int) -> RangeReference:
    range_id = space.range_for(value) or ""
    return RangeReference(id=range_id, display_label=labels.get(range_id, ""))
