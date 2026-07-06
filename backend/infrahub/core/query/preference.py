# StandardNode Cypher query for preferences

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import QueryType
from infrahub.core.query.standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class PreferenceGetByOwnerQuery(StandardNodeQuery):
    """Fetch the Preference rows for the given owner ids (account ids and/or the Root id).

    A targeted lookup instead of `get_list()`-ing every row and filtering in Python (which would scan
    every principal's preferences). Serves both a single owner (a user's row or the global row) and
    the effective read, which fetches the account row and the Root row together in ONE query. There
    is at most one row per owner (guaranteed by the per-owner upsert lock).
    """

    name = "preference_get_by_owner"
    type = QueryType.READ

    def __init__(self, owner_ids: list[str], node_type: str, **kwargs: Any) -> None:
        self.owner_ids = owner_ids
        self.node_type = node_type
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["owner_ids"] = self.owner_ids

        # `node_type` is a trusted internal constant — always Preference.get_type() passed by the
        # caller (models.py), never user input — so interpolating it as the node label (Cypher labels
        # can't be parameterised) is safe. `owner_ids` IS a bound $param.
        query = """
        MATCH (n:%s)
        WHERE n.owner_id IN $owner_ids
        """ % (self.node_type,)

        self.add_to_query(query=query)
        self.return_labels = ["n"]
        # Deterministic order so a single-owner read returns a stable row even in the (lock-prevented)
        # event of a duplicate — mirrors the previous get_global guarantee.
        self.order_by = ["n.uuid"]
