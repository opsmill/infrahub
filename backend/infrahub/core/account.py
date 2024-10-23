from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub.core.constants import InfrahubKind, PermissionDecision
from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions


# pylint: disable=redefined-builtin


@dataclass
class GlobalPermission:
    action: str
    decision: int
    description: str = ""
    id: str = ""

    def __str__(self) -> str:
        decision = PermissionDecision(self.decision)
        return f"global:{self.action}:{decision.name.lower()}"


@dataclass
class ObjectPermission:
    namespace: str
    name: str
    action: str
    decision: int
    description: str = ""
    id: str = ""

    def __str__(self) -> str:
        decision = PermissionDecision(self.decision)
        return f"object:{self.namespace}:{self.name}:{self.action}:{decision.name.lower()}"


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
        MATCH (account:%(generic_account_node)s)
        WHERE account.uuid = $account_id
        CALL {
            WITH account
            MATCH (account)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        CALL {
            WITH account
            MATCH (account)-[r1:IS_RELATED]->(:Relationship {name: "group_member"})<-[r2:IS_RELATED]-(account_group:%(account_group_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_group, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_group.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_group, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_group
        }
        WITH account_group

        CALL {
            WITH account_group
            MATCH (account_group)-[r1:IS_RELATED]->(:Relationship {name: "role__accountgroups"})<-[r2:IS_RELATED]-(account_role:%(account_role_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_role, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_role.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_role, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_role
        }
        WITH account_role

        CALL {
            WITH account_role
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(global_permission:%(global_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH global_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY global_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH global_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN global_permission
        }
        WITH global_permission

        CALL {
            WITH global_permission
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "description"})-[r2:HAS_VALUE]->(global_permission_description:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_description, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_description, is_active AS gpn_is_active
        WHERE gpn_is_active = TRUE

        CALL {
            WITH global_permission
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(global_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_description, global_permission_action, is_active AS gpa_is_active
        WHERE gpa_is_active = TRUE

        CALL {
            WITH global_permission
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(global_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_description, global_permission_action, global_permission_decision, is_active AS gpd_is_active
        WHERE gpd_is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "generic_account_node": InfrahubKind.GENERICACCOUNT,
            "account_group_node": InfrahubKind.ACCOUNTGROUP,
            "account_role_node": InfrahubKind.ACCOUNTROLE,
            "global_permission_node": InfrahubKind.GLOBALPERMISSION,
        }

        self.add_to_query(query)

        self.return_labels = [
            "global_permission",
            "global_permission_description",
            "global_permission_action",
            "global_permission_decision",
        ]

    def get_permissions(self) -> list[GlobalPermission]:
        permissions: list[GlobalPermission] = []

        for result in self.get_results():
            permissions.append(
                GlobalPermission(
                    id=result.get("global_permission").get("uuid"),
                    description=result.get("global_permission_description").get("value"),
                    action=result.get("global_permission_action").get("value"),
                    decision=result.get("global_permission_decision").get("value"),
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

        query = """
        MATCH (account:%(generic_account_node)s)
        WHERE account.uuid = $account_id
        CALL {
            WITH account
            MATCH (account)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        CALL {
            WITH account
            MATCH (account)-[r1:IS_RELATED]->(:Relationship {name: "group_member"})<-[r2:IS_RELATED]-(account_group:%(account_group_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_group, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_group.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_group, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_group
        }
        WITH account_group

        CALL {
            WITH account_group
            MATCH (account_group)-[r1:IS_RELATED]->(:Relationship {name: "role__accountgroups"})<-[r2:IS_RELATED]-(account_role:%(account_role_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_role, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_role.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_role, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_role
        }
        WITH account_role

        CALL {
            WITH account_role
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(object_permission:%(object_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH object_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY object_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH object_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN object_permission
        }
        WITH object_permission

        CALL {
            WITH object_permission
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "description"})-[r2:HAS_VALUE]->(object_permission_description:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_description, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_description, is_active AS opn_is_active
        WHERE opn_is_active = TRUE

        CALL {
            WITH object_permission
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(object_permission_namespace:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_namespace, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_description, object_permission_namespace, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL {
            WITH object_permission
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(object_permission_name:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_name, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_description, object_permission_namespace, object_permission_name, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL {
            WITH object_permission
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(object_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_description, object_permission_namespace, object_permission_name, object_permission_action, is_active AS opa_is_active
        WHERE opa_is_active = TRUE
        CALL {
            WITH object_permission
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(object_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_description, object_permission_namespace, object_permission_name, object_permission_action, object_permission_decision, is_active AS opd_is_active
        WHERE opd_is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "account_group_node": InfrahubKind.ACCOUNTGROUP,
            "account_role_node": InfrahubKind.ACCOUNTROLE,
            "generic_account_node": InfrahubKind.GENERICACCOUNT,
            "object_permission_node": InfrahubKind.OBJECTPERMISSION,
        }

        self.add_to_query(query)

        self.return_labels = [
            "object_permission",
            "object_permission_description",
            "object_permission_namespace",
            "object_permission_name",
            "object_permission_action",
            "object_permission_decision",
        ]

    def get_permissions(self) -> list[ObjectPermission]:
        permissions: list[ObjectPermission] = []
        for result in self.get_results():
            permissions.append(
                ObjectPermission(
                    id=result.get("object_permission").get("uuid"),
                    description=result.get("object_permission_description").get("value"),
                    namespace=result.get("object_permission_namespace").get("value"),
                    name=result.get("object_permission_name").get("value"),
                    action=result.get("object_permission_action").get("value"),
                    decision=result.get("object_permission_decision").get("value"),
                )
            )

        return permissions


async def fetch_permissions(account_id: str, db: InfrahubDatabase, branch: Branch) -> AssignedPermissions:
    query1 = await AccountGlobalPermissionQuery.init(db=db, branch=branch, account_id=account_id, branch_agnostic=True)
    await query1.execute(db=db)
    global_permissions = query1.get_permissions()

    query2 = await AccountObjectPermissionQuery.init(db=db, branch=branch, account_id=account_id)
    await query2.execute(db=db)
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
