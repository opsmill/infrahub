from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core.constants import NULL_VALUE, InfrahubKind, PermissionDecision
from infrahub.core.query import Query, QueryType
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions import AssignedPermissions


@dataclass
class GlobalPermission:
    action: str
    decision: int
    description: str = ""
    id: str = ""

    def __str__(self) -> str:
        decision = PermissionDecision(self.decision)
        return f"global:{self.action}:{decision.name.lower()}"

    @classmethod
    def from_string(cls, input: str) -> Self:
        parts = input.split(":")
        if len(parts) != 3 and parts[0] != "global":
            raise ValueError(f"{input} is not a valid format for a Global permission")

        return cls(action=parts[1], decision=PermissionDecision[parts[2].upper()])


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
    type: QueryType = QueryType.READ

    def __init__(self, account_id: str, **kwargs: Any):
        self.account_id = account_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["account_id"] = self.account_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        MATCH (account:%(generic_account_node)s)
        WHERE account.uuid = $account_id
        CALL (account) {
            MATCH (account)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        CALL (account) {
            MATCH (account)-[r1:IS_RELATED]->(:Relationship {name: "group_member"})<-[r2:IS_RELATED]-(account_group:%(account_group_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_group, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_group.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_group, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_group
        }
        WITH account_group

        CALL (account_group) {
            MATCH (account_group)-[r1:IS_RELATED]->(:Relationship {name: "role__accountgroups"})<-[r2:IS_RELATED]-(account_role:%(account_role_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_role, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_role.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_role, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_role
        }
        WITH account_role

        CALL (account_role) {
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(global_permission:%(global_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH global_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY global_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH global_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN global_permission
        }
        WITH global_permission

        CALL (global_permission) {
            WITH global_permission
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(global_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_action, is_active AS gpa_is_active
        WHERE gpa_is_active = TRUE

        CALL (global_permission) {
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(global_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_action, global_permission_decision, is_active AS gpd_is_active
        WHERE gpd_is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "generic_account_node": InfrahubKind.GENERICACCOUNT,
            "account_group_node": InfrahubKind.ACCOUNTGROUP,
            "account_role_node": InfrahubKind.ACCOUNTROLE,
            "global_permission_node": InfrahubKind.GLOBALPERMISSION,
        }

        self.add_to_query(query)

        self.return_labels = ["global_permission", "global_permission_action", "global_permission_decision"]

    def get_permissions(self) -> list[GlobalPermission]:
        permissions: list[GlobalPermission] = []

        for result in self.get_results():
            permissions.append(
                GlobalPermission(
                    id=result.get("global_permission").get("uuid"),
                    action=result.get("global_permission_action").get("value"),
                    decision=result.get("global_permission_decision").get("value"),
                )
            )

        return permissions


class AccountObjectPermissionQuery(Query):
    name: str = "account_object_permissions"
    type: QueryType = QueryType.READ

    def __init__(self, account_id: str, **kwargs: Any):
        self.account_id = account_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["account_id"] = self.account_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )
        self.params.update(branch_params)

        query = """
        MATCH (account:%(generic_account_node)s)
        WHERE account.uuid = $account_id
        CALL (account) {
            MATCH (account)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account as account1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account, r1 as r
        WHERE r.status = "active"
        WITH account
        CALL (account) {
            MATCH (account)-[r1:IS_RELATED]->(:Relationship {name: "group_member"})<-[r2:IS_RELATED]-(account_group:%(account_group_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_group, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_group.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_group, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_group
        }
        WITH account_group

        CALL (account_group) {
            MATCH (account_group)-[r1:IS_RELATED]->(:Relationship {name: "role__accountgroups"})<-[r2:IS_RELATED]-(account_role:%(account_role_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH account_role, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY account_role.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH account_role, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN account_role
        }
        WITH account_role

        CALL (account_role) {
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(object_permission:%(object_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH object_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY object_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH object_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN object_permission
        }
        WITH object_permission

        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(object_permission_namespace:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_namespace, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(object_permission_name:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_name, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(object_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, object_permission_action, is_active AS opa_is_active
        WHERE opa_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(object_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, object_permission_action, object_permission_decision, is_active AS opd_is_active
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


class AccountRoleGlobalPermissionQuery(Query):
    name: str = "account_role_global_permissions"
    type: QueryType = QueryType.READ

    def __init__(self, role_id: str, **kwargs: Any):
        self.role_id = role_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["role_id"] = self.role_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        MATCH (account_role:%(account_role_node)s)
        WHERE account_role.uuid = $role_id
        CALL (account_role) {
            MATCH (account_role)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account_role as account_role1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account_role, r1 as r
        WHERE r.status = "active"
        WITH account_role

        CALL (account_role) {
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(global_permission:%(global_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH global_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY global_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH global_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN global_permission
        }
        WITH global_permission

        CALL (global_permission) {
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(global_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_action, is_active AS gpa_is_active
        WHERE gpa_is_active = TRUE

        CALL (global_permission) {
            MATCH (global_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(global_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN global_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH global_permission, global_permission_action, global_permission_decision, is_active AS gpd_is_active
        WHERE gpd_is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "account_role_node": InfrahubKind.ACCOUNTROLE,
            "global_permission_node": InfrahubKind.GLOBALPERMISSION,
        }

        self.add_to_query(query)

        self.return_labels = ["global_permission", "global_permission_action", "global_permission_decision"]

    def get_permissions(self) -> list[GlobalPermission]:
        permissions: list[GlobalPermission] = []

        for result in self.get_results():
            permissions.append(
                GlobalPermission(
                    id=result.get("global_permission").get("uuid"),
                    action=result.get("global_permission_action").get("value"),
                    decision=result.get("global_permission_decision").get("value"),
                )
            )

        return permissions


class AccountRoleObjectPermissionQuery(Query):
    name: str = "account_role_object_permissions"
    type: QueryType = QueryType.READ

    def __init__(self, role_id: str, **kwargs: Any):
        self.role_id = role_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["role_id"] = self.role_id

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )
        self.params.update(branch_params)

        query = """
        MATCH (account_role:%(account_role_node)s)
        WHERE account_role.uuid = $role_id
        CALL (account_role) {
            MATCH (account_role)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN account_role as account_role1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH account_role, r1 as r
        WHERE r.status = "active"
        WITH account_role

        CALL (account_role) {
            MATCH (account_role)-[r1:IS_RELATED]->(:Relationship {name: "role__permissions"})<-[r2:IS_RELATED]-(object_permission:%(object_permission_node)s)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH object_permission, r1, r2, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY object_permission.uuid, r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            WITH object_permission, head(collect(is_active)) as latest_is_active
            WHERE latest_is_active = TRUE
            RETURN object_permission
        }
        WITH object_permission

        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(object_permission_namespace:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_namespace, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(object_permission_name:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_name, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, is_active AS opn_is_active
        WHERE opn_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "action"})-[r2:HAS_VALUE]->(object_permission_action:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_action, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, object_permission_action, is_active AS opa_is_active
        WHERE opa_is_active = TRUE
        CALL (object_permission) {
            MATCH (object_permission)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "decision"})-[r2:HAS_VALUE]->(object_permission_decision:AttributeValue)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN object_permission_decision, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH object_permission, object_permission_namespace, object_permission_name, object_permission_action, object_permission_decision, is_active AS opd_is_active
        WHERE opd_is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "account_role_node": InfrahubKind.ACCOUNTROLE,
            "object_permission_node": InfrahubKind.OBJECTPERMISSION,
        }

        self.add_to_query(query)

        self.return_labels = [
            "object_permission",
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
                    namespace=result.get("object_permission_namespace").get("value"),
                    name=result.get("object_permission_name").get("value"),
                    action=result.get("object_permission_action").get("value"),
                    decision=result.get("object_permission_decision").get("value"),
                )
            )

        return permissions


async def fetch_role_permissions(role_id: str, db: InfrahubDatabase, branch: Branch) -> AssignedPermissions:
    query1 = await AccountRoleGlobalPermissionQuery.init(db=db, branch=branch, role_id=role_id, branch_agnostic=True)
    await query1.execute(db=db)
    global_permissions = query1.get_permissions()

    query2 = await AccountRoleObjectPermissionQuery.init(db=db, branch=branch, role_id=role_id)
    await query2.execute(db=db)
    object_permissions = query2.get_permissions()

    return {"global_permissions": global_permissions, "object_permissions": object_permissions}


class AccountTokenValidateQuery(Query):
    name: str = "account_token_validate"
    type: QueryType = QueryType.READ

    def __init__(self, token: str, **kwargs: Any):
        self.token = token
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )
        self.params.update(branch_params)
        self.params.update(
            {
                "token_attr_name": "token",
                "token_relationship_name": "account__token",
                "token_value": self.token,
                "null_value": NULL_VALUE,
            }
        )

        query = """
// --------------
// get the active token node for this token value, if it exists
// --------------
MATCH (token_node:%(token_node_kind)s)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: $token_attr_name})
    -[r2:HAS_VALUE]->(av:AttributeValueIndexed { value: $token_value })
WHERE all(r in [r1, r2] WHERE (%(branch_filter)s))
ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
LIMIT 1
WITH token_node
WHERE r1.status = "active" AND r2.status = "active"
// --------------
// get the expiration time
// --------------
OPTIONAL MATCH (token_node)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "expiration"})
    -[r2:HAS_VALUE]->(av)
WHERE all(r in [r1, r2] WHERE (%(branch_filter)s))
ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
LIMIT 1
WITH token_node, CASE
    WHEN r1.status = "active" AND r2.status = "active" AND av.value <> $null_value THEN av.value
    ELSE NULL
END AS expiration
// --------------
// get the linked account node from the token node
// --------------
MATCH (token_node)-[r1:IS_RELATED]-(:Relationship {name: $token_relationship_name})-[r2:IS_RELATED]-(account_node:%(account_node_kind)s)
WHERE all(r in [r1, r2] WHERE (%(branch_filter)s))
ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
LIMIT 1
WITH expiration, account_node
WHERE r1.status = "active" AND r2.status = "active"
        """ % {
            "branch_filter": branch_filter,
            "token_node_kind": InfrahubKind.ACCOUNTTOKEN,
            "account_node_kind": InfrahubKind.GENERICACCOUNT,
        }
        self.add_to_query(query)
        self.return_labels = ["account_node.uuid AS account_uuid", "expiration"]

    def get_account_id(self) -> str | None:
        """Return the account id that matched the query or a None."""
        result = self.get_result()
        if not result:
            return None
        account_uuid = result.get_as_str(label="account_uuid")
        expiration_with_tz = result.get_as_str(label="expiration")
        if expiration_with_tz is None:
            return account_uuid
        expiration = Timestamp(expiration_with_tz)
        if expiration < Timestamp():
            return None
        return account_uuid


async def validate_token(token: str, db: InfrahubDatabase, branch: Branch | str | None = None) -> str | None:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await AccountTokenValidateQuery.init(db=db, branch=branch, token=token)
    await query.execute(db=db)
    return query.get_account_id()
