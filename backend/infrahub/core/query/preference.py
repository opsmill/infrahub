# StandardNode Cypher queries for preferences

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import QueryType
from infrahub.core.query.standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class UserPreferenceGetByAccountQuery(StandardNodeQuery):
    """Fetch the single UserPreference row owned by a given account.

    A targeted lookup by `account_id` instead of `get_list()`-ing every row and filtering in
    Python (which would scan every user's preferences). There is at most one row per account.
    """

    name = "user_preference_get_by_account"
    type = QueryType.READ

    def __init__(self, account_id: str, node_type: str, **kwargs: Any) -> None:
        self.account_id = account_id
        self.node_type = node_type
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["account_id"] = self.account_id

        query = """
        MATCH (n:%s { account_id: $account_id })
        """ % (self.node_type,)

        self.add_to_query(query=query)
        self.return_labels = ["n"]
        # The per-account upsert lock prevents duplicate rows being created, so there is normally at
        # most one. Order by uuid and cap at one as defense-in-depth: if a duplicate ever did exist,
        # this keeps the read deterministic (mirrors get_global's deterministic-first guarantee).
        self.order_by = ["n.uuid"]
        self.limit = 1
