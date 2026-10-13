from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.pools.number import UtilizationFigures
from infrahub.pools.number_pool_usage import DivisionEntry, DivisionUsage, PoolDivisions
from infrahub.pools.scope import division_element_path

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.query.resource_manager import NumberPoolDivisionResult
    from infrahub.core.schema import AttributeSchema, RelationshipSchema
    from infrahub.pools.number_pool_repository import NumberPoolRepository
    from infrahub.pools.number_pool_usage import PeerSummary
    from infrahub.pools.number_pool_usage_nodes import PeerSummaryReader
    from infrahub.pools.number_pool_usage_state import NumberPoolStateLoader, PoolScopeFields
    from infrahub.pools.scope import ScopeElement

DISPLAY_LABEL_SEPARATOR = " / "


class NumberPoolDivisionsReader:
    """Reads every division of one number pool that holds a number, each with its figures over the whole pool."""

    def __init__(
        self,
        branch: Branch,
        loader: NumberPoolStateLoader,
        repository: NumberPoolRepository,
        peer_reader: PeerSummaryReader,
    ) -> None:
        self.branch = branch
        self.loader = loader
        self.repository = repository
        self.peer_reader = peer_reader

    async def read(self, pool_id: str) -> PoolDivisions:
        """Return the divisions holding a number, ordered by utilization descending, then by display label.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When the schema of the branch does not define a scope element.

        """
        state = await self.loader.load(pool_id=pool_id)
        if state.scope.is_empty:
            return PoolDivisions(count=0, allocation_scope=(), divisions=())
        results = await self.repository.get_divisions(
            pool=state.pool, branch=self.branch, space=state.space, elements=state.scope.element_paths
        )
        peers = await self.peer_reader.read(ids=division_peer_ids(scope=state.scope, results=results))
        divisions = build_division_usages(scope=state.scope, results=results, size=state.space.size, peers=peers)
        return PoolDivisions(count=len(divisions), allocation_scope=state.scope.elements, divisions=divisions)


def division_peer_ids(scope: PoolScopeFields, results: Sequence[NumberPoolDivisionResult]) -> set[str]:
    """Return the id of every peer a relationship element of the divisions names."""
    return {
        str(value)
        for result in results
        for (_, field), value in zip(scope.element_fields, result.values, strict=True)
        if _is_relationship(field) and value
    }


def build_division_usages(
    scope: PoolScopeFields,
    results: Sequence[NumberPoolDivisionResult],
    size: int,
    peers: dict[str, PeerSummary],
) -> tuple[DivisionUsage, ...]:
    """Return each division with one entry per scope element, ordered by utilization descending, then display label.

    A relationship entry is labeled with its peer's display label, or with the peer id when `peers` lacks the peer.
    """
    divisions = []
    for result in results:
        entries = tuple(
            _entry(element=element, field=field, value=value, peers=peers)
            for (element, field), value in zip(scope.element_fields, result.values, strict=True)
        )
        divisions.append(
            DivisionUsage(
                display_label=DISPLAY_LABEL_SEPARATOR.join(entry.display_label for entry in entries),
                entries=entries,
                figures=UtilizationFigures(
                    size=size, used_default_branch=result.used_default_branch, used_branches=result.used_branches
                ),
            )
        )
    divisions.sort(key=lambda item: (-item.figures.utilization, item.display_label))
    return tuple(divisions)


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
    peers: dict[str, PeerSummary],
) -> DivisionEntry:
    text = _as_text(value)
    if not _is_relationship(field):
        return DivisionEntry(id=element.id, path=element.name, value=value, display_label=text, peer_kind=None)
    peer = peers.get(text)
    return DivisionEntry(
        id=element.id,
        path=element.name,
        value=text,
        display_label=peer.display_label if peer else text,
        peer_kind=peer.kind if peer else None,
    )
