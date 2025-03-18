from dataclasses import dataclass
from typing import Any

from aiodataloader import DataLoader

from infrahub.auth import AccountSession
from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .shared import to_frozen_set


@dataclass
class GetManyParams:
    branch: Branch | str
    fields: dict | None = None
    at: Timestamp | str | None = None
    include_source: bool = False
    include_owner: bool = False
    prefetch_relationships: bool = False
    account: AccountSession | None = None
    branch_agnostic: bool = False

    def __hash__(self) -> int:
        frozen_fields: frozenset | None = None
        if self.fields:
            frozen_fields = to_frozen_set(self.fields)
        timestamp = Timestamp(self.at)
        branch = self.branch.name if isinstance(self.branch, Branch) else self.branch
        account_id = self.account.account_id if isinstance(self.account, AccountSession) else None
        hash_str = "|".join(
            [
                str(hash(frozen_fields)),
                timestamp.to_string(),
                branch,
                str(self.include_source),
                str(self.include_owner),
                str(self.prefetch_relationships),
                str(account_id),
                str(self.branch_agnostic),
            ]
        )
        return hash(hash_str)


class NodeDataLoader(DataLoader[str, Node | None]):
    def __init__(self, db: InfrahubDatabase, query_params: GetManyParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.query_params = query_params
        self.db = db

    async def batch_load_fn(self, keys: list[Any]) -> list[Node | None]:
        async with self.db.start_session() as db:
            nodes_by_id = await NodeManager.get_many(
                db=db,
                ids=keys,
                fields=self.query_params.fields,
                at=self.query_params.at,
                branch=self.query_params.branch,
                include_source=self.query_params.include_source,
                include_owner=self.query_params.include_owner,
                prefetch_relationships=self.query_params.prefetch_relationships,
                account=self.query_params.account,
                branch_agnostic=self.query_params.branch_agnostic,
            )
        results = []
        for node_id in keys:
            results.append(nodes_by_id.get(node_id, None))
        return results
