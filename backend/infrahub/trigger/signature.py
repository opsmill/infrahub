from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self

from infrahub.core.node.standard import StandardNode, StandardNodeOrdering
from infrahub.core.query.standard_node import StandardNodeGetListQuery

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


class TriggerSignatureGetListQueryBase(StandardNodeGetListQuery):
    def __init__(
        self,
        branch_name: str | None = None,
        target_kind: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._branch_name = branch_name
        self._target_kind = target_kind
        self._signature_filter_params: dict[str, Any] = {}

        self.raw_filter = " AND ".join(self._collect_conditions())

        super().__init__(**kwargs)

        self.params.update(self._signature_filter_params)

    def _collect_conditions(self) -> list[str]:
        conditions: list[str] = []

        if self._branch_name is not None:
            self._signature_filter_params["filter_branch"] = self._branch_name
            conditions.append("n.branch = $filter_branch")

        if self._target_kind is not None:
            self._signature_filter_params["filter_target_kind"] = self._target_kind
            conditions.append("n.target_kind = $filter_target_kind")

        return conditions


class TriggerSignatureBase(StandardNode):
    """Common shape for trigger-signature StandardNodes: a hash of a schema-derived definition
    scoped to (branch, target_kind), used by setup flows to detect when downstream values
    must be recomputed."""

    branch: str
    target_kind: str
    definition_hash: str

    list_query_cls: ClassVar[type[TriggerSignatureGetListQueryBase]] = TriggerSignatureGetListQueryBase

    @classmethod
    async def get_list(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        offset: int | None = None,
        ids: list[str] | None = None,
        name: str | None = None,
        node_ordering: StandardNodeOrdering | None = None,
        **kwargs: Any,
    ) -> list[Self]:
        branch: str | None = kwargs.pop("branch", None)
        target_kind: str | None = kwargs.pop("target_kind", None)

        node_ordering = node_ordering or StandardNodeOrdering()
        query: Query = await cls.list_query_cls.init(
            db=db,
            node_class=cls,
            ids=ids,
            node_name=name,
            limit=limit,
            offset=offset,
            node_ordering=node_ordering,
            branch_name=branch,
            target_kind=target_kind,
            **kwargs,
        )
        await query.execute(db=db)
        return [cls.from_db(node=result.get_node("n")) for result in query.get_results()]
