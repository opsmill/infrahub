from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin


class AccountTokenValidateQuery(Query):
    name: str = "account_token_validate"

    def __init__(self, token: str, **kwargs: Any):
        self.token = token
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        token_filter_perms, token_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(token_params)

        account_filter_perms, account_params = self.branch.get_query_filter_relationships(
            rel_labels=["r31", "r32", "r41", "r42", "r5", "r6", "r7", "r8"],
            at=self.at,
            include_outside_parentheses=True,
        )
        self.params.update(account_params)

        self.params["token_value"] = self.token

        query = """
        MATCH (at:InternalAccountToken)-[r1:HAS_ATTRIBUTE]-(a:Attribute {name: "token"})-[r2:HAS_VALUE]-(av:AttributeValue { value: $token_value })
        WHERE %s
        WITH at
        MATCH (at)-[r31]-(:Relationship)-[r41]-(acc:CoreAccount)-[r5:HAS_ATTRIBUTE]-(an:Attribute {name: "name"})-[r6:HAS_VALUE]-(av:AttributeValue)
        MATCH (at)-[r32]-(:Relationship)-[r42]-(acc:CoreAccount)-[r7:HAS_ATTRIBUTE]-(ar:Attribute {name: "role"})-[r8:HAS_VALUE]-(avr:AttributeValue)
        WHERE %s
        """ % (
            "\n AND ".join(token_filter_perms),
            "\n AND ".join(account_filter_perms),
        )

        self.add_to_query(query)

        self.return_labels = ["at", "av", "avr", "acc"]

    def get_account_name(self) -> Optional[str]:
        """Return the account name that matched the query or None."""
        if result := self.get_result():
            return result.get("av").get("value")

        return None

    def get_account_id(self) -> Optional[str]:
        """Return the account id that matched the query or a None."""
        if result := self.get_result():
            return result.get("acc").get("uuid")

        return None

    def get_account_role(self) -> str:
        """Return the account role that matched the query or a None."""
        if result := self.get_result():
            return result.get("avr").get("value")

        return "read-only"


async def validate_token(
    token: str, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None
) -> tuple[Optional[str], str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await AccountTokenValidateQuery.init(db=db, branch=branch, token=token)
    await query.execute(db=db)
    return query.get_account_id(), query.get_account_role()
