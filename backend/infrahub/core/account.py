from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin


@dataclass
class Permission:
    id: str
    action: str


@dataclass
class GlobalPermission(Permission):
    name: str

    def __str__(self) -> str:
        return f"global:{self.action}:allow"


@dataclass
class ObjectPermission(Permission):
    namespace: str
    kind: str

    def __str__(self) -> str:
        return f"object:{self.namespace}:{self.kind}:{self.action}"


class AccountGlobalPermissionQuery(Query):
    name: str = "account_global_permissions"

    def __init__(self, account_id: str, **kwargs: Any):
        self.account_id = account_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params["account_id"] = self.account_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        MATCH (account:CoreGenericAccount)
        WHERE account.uuid = $account_id
        CALL {
            WITH account
            MATCH (ns)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        MATCH (account)-[]->(:Relationship {name: "usergroup__users"})<-[]-(:CoreUserGroup)-[]->(:Relationship {name: "role__usergroups"})<-[]-(:CoreUserRole)-[]->(:Relationship {name: "role__permissions"})<-[]-(global_permission:CoreGlobalPermission)-[:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[:HAS_VALUE]->(global_permission_action:AttributeValue)
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)

        self.return_labels = ["global_permission", "global_permission_action"]

    def get_permissions(self) -> list[GlobalPermission]:
        permissions: list[GlobalPermission] = []

        for result in self.get_results():
            permissions.append(
                GlobalPermission(
                    id=result.get("global_permission").get("uuid"),
                    name=result.get("global_permission_action").get("value"),
                    action=result.get("global_permission_action").get("value"),
                )
            )

        return permissions


class AccountObjectPermissionQuery(Query):
    name: str = "account_object_permissions"

    def __init__(self, account_id: str, **kwargs: Any):
        self.account_id = account_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params["account_id"] = self.account_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        # FIXME: Need to find a way to retrieve all attribute values needed
        # The below seems to somewhat gives what's needed
        # ruff: noqa: E501
        query = """
        MATCH (account:CoreGenericAccount)
        WHERE account.uuid = $account_id
        CALL {
            WITH account
            MATCH (ns)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        MATCH (account)-[]->(:Relationship {name: "usergroup__users"})<-[]-(:CoreUserGroup)-[]->(:Relationship {name: "role__usergroups"})<-[]-(:CoreUserRole)-[]->(:Relationship {name: "role__permissions"})<-[]-(object_permission:CoreObjectPermission)-[:HAS_ATTRIBUTE]->(object_permission_attr:Attribute)-[:HAS_VALUE]->(object_permission_attr_value:AttributeValue)
        WHERE object_permission_attr.name IN ["namespace", "kind", "action"]
        WITH object_permission_attr, object_permission_value
        WITH COLLECT([object_permission_attr, object_permission_value]) as names_values
        UNWIND names_values as name_value
        RETURN name_value
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)

        self.return_labels = ["name_value"]

    def get_permissions(self) -> list[ObjectPermission]:
        permissions: list[ObjectPermission] = []
        # for result in self.get_results():
        # permissions.append(
        #     ObjectPermission(
        #         id=result.get("object_permission").get("uuid"),
        #         namespace="",
        #         kind="",
        #         action=result.get("object_permission_action").get("value"),
        #     )
        # )

        return permissions


async def fetch_permissions(
    account_id: str, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None
) -> dict[str, list[GlobalPermission] | list[ObjectPermission]]:
    branch = await registry.get_branch(db=db, branch=branch)

    query1 = await AccountGlobalPermissionQuery.init(db=db, branch=branch, account_id=account_id)
    await query1.execute(db=db)
    global_permissions = query1.get_permissions()

    query2 = await AccountObjectPermissionQuery.init(db=db, branch=branch, account_id=account_id)
    # await query2.execute(db=db)
    object_permissions = query2.get_permissions()

    return {"global_permissions": global_permissions, "object_permissions": object_permissions}


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

        # ruff: noqa: E501
        query = """
        MATCH (at:InternalAccountToken)-[r1:HAS_ATTRIBUTE]-(a:Attribute {name: "token"})-[r2:HAS_VALUE]-(av:AttributeValue { value: $token_value })
        WHERE %s
        WITH at
        MATCH (at)-[r31]-(:Relationship)-[r41]-(acc:CoreGenericAccount)-[r5:HAS_ATTRIBUTE]-(an:Attribute {name: "name"})-[r6:HAS_VALUE]-(av:AttributeValue)
        MATCH (at)-[r32]-(:Relationship)-[r42]-(acc:CoreGenericAccount)-[r7:HAS_ATTRIBUTE]-(ar:Attribute {name: "role"})-[r8:HAS_VALUE]-(avr:AttributeValue)
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
