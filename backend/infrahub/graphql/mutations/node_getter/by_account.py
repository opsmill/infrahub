from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase

from .interface import MutationNodeGetterInterface


class MutationNodeGetterByAccount(MutationNodeGetterInterface):
    """Resolve the single row owned by the account referenced in an upsert payload.

    The target node is identified by its `account` uniqueness key rather than by id/hfid:
    given the `account` peer spec in `data`, resolve the account id (directly via its `id`,
    or by resolving an `hfid` peer spec against InfrahubKind.GENERICACCOUNT) and return the
    one node of `node_schema.kind` related to that account, if any.
    """

    def __init__(self, db: InfrahubDatabase, node_manager: NodeManager) -> None:
        self.db = db
        self.node_manager = node_manager

    async def get_node(
        self,
        node_schema: MainSchemaTypes,
        data: InputObjectType,
        branch: Branch,
    ) -> Node | None:
        account_data = data.get("account")
        if account_data is None:
            return None

        account_id = account_data.get("id")
        if account_id is None:
            account_hfid = account_data.get("hfid")
            if account_hfid is None:
                return None
            # Resolve an hfid peer spec to its id so admin upserts stay idempotent; non-admin
            # callers are rejected later by _validate_account_input regardless.
            account_node = await self.node_manager.get_one_by_hfid(
                db=self.db, hfid=list(account_hfid), kind=InfrahubKind.GENERICACCOUNT, branch=branch
            )
            account_id = account_node.id if account_node else None

        if account_id is None:
            return None

        results = await self.node_manager.query(
            db=self.db,
            schema=node_schema.kind,
            filters={"account__ids": [account_id]},
            branch=branch,
            limit=1,
        )
        return results[0] if results else None
