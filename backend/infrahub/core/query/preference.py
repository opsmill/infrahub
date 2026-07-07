from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import QueryType
from infrahub.core.query.standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class PreferenceGetByOwnerQuery(StandardNodeQuery):
    """Fetch the Preference rows for the given owner ids (account ids and/or the Root id).

    There is at most one row per owner (guaranteed by the per-owner upsert lock).
    """

    name = "preference_get_by_owner"
    type = QueryType.READ

    def __init__(self, owner_ids: set[str], node_type: str, **kwargs: Any) -> None:
        self.owner_ids = owner_ids
        self.node_type = node_type
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        # Cypher parameters cannot bind a set, so pass the ids as a list.
        self.params["owner_ids"] = list(self.owner_ids)

        # `node_type` is a trusted internal constant, never user input, so interpolating it as the
        # node label (Cypher labels can't be parameterised) is safe. `owner_ids` IS a bound $param.
        query = """
        MATCH (n:%s)
        WHERE n.owner_id IN $owner_ids
        """ % (self.node_type,)

        self.add_to_query(query=query)
        self.return_labels = ["n"]
        # Deterministic order so a single-owner read returns a stable row even in the (lock-prevented)
        # event of a duplicate.
        self.order_by = ["n.uuid"]
