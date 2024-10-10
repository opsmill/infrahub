from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.manager import get_schema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.utils import extract_camelcase_words

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ObjectPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can perform some action on some kind of objects."""

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        required_decision = (
            PermissionDecisionFlag.ALLOWED_DEFAULT
            if analyzed_query.branch is None
            or analyzed_query.branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
            else PermissionDecisionFlag.ALLOWED_OTHER
        )

        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        # Identify which operations are performed. As we don't have a mapping between kinds and the
        # operation we currently require permissions all defined permissions for all objects
        # within the GraphQL query / mutation
        actions: set[str] = set()
        for operation in analyzed_query.operations:
            for kind in kinds:
                if operation.name and operation.name.startswith(kind):
                    # An empty string after prefix removal means a query to "view"
                    query_action = operation.name[len(kind) :].lower() or "view"
                    if query_action == "upsert":
                        # Require both create and update for Upsert mutations
                        actions.add("create")
                        actions.add("update")
                    else:
                        actions.add(query_action)

        # Infer required permissions from the kind/operation map
        permissions: list[str] = []
        for action in actions:
            for kind in kinds:
                extracted_words = extract_camelcase_words(kind)
                permissions.append(
                    # Create an object permission instance just to get its string representation
                    str(
                        ObjectPermission(
                            id="",
                            namespace=extracted_words[0],
                            name="".join(extracted_words[1:]),
                            action=action.lower(),
                            decision=required_decision.value,
                        )
                    )
                )

        for permission in permissions:
            has_permission = False
            for permission_backend in registry.permission_backends:
                has_permission = await permission_backend.has_permission(
                    db=db, account_id=account_session.account_id, permission=permission, branch=branch
                )
            if not has_permission:
                raise PermissionDeniedError(f"You do not have the following permission: {permission}")

        return CheckerResolution.NEXT_CHECKER


class AccountManagerPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can perform actions on account related objects.

    This is similar to object permission checker except that we care for any operations on any account related kinds.
    """

    permission_required = f"global:{GlobalPermissions.MANAGE_ACCOUNTS.value}:{PermissionDecision.ALLOWED_ALL.value}"

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        is_account_operation = False
        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)
        operation_names = [operation.name for operation in analyzed_query.operations]

        for kind in kinds:
            schema = get_schema(db=db, branch=branch, node_schema=kind)
            if is_account_operation := kind in (
                InfrahubKind.GENERICACCOUNT,
                InfrahubKind.ACCOUNTGROUP,
                InfrahubKind.ACCOUNTROLE,
            ) or (isinstance(schema, NodeSchema) and InfrahubKind.GENERICACCOUNT in schema.inherit_from):
                break

        # Ignore non-account related operation or viewing account own profile
        if not is_account_operation or operation_names == ["AccountProfile"]:
            return CheckerResolution.NEXT_CHECKER

        has_permission = False
        for permission_backend in registry.permission_backends:
            if has_permission := await permission_backend.has_permission(
                db=db, account_id=account_session.account_id, permission=self.permission_required, branch=branch
            ):
                break

        if not has_permission and analyzed_query.contains_mutation:
            raise PermissionDeniedError("You do not have the permission to manage user accounts, groups or roles")

        return CheckerResolution.NEXT_CHECKER


class PermissionManagerPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can perform actions on permission related object.

    This is similar to object permission checker except that we care for any operations on any permission related kinds.
    """

    permission_required = f"global:{GlobalPermissions.MANAGE_PERMISSIONS.value}:{PermissionDecision.ALLOWED_ALL.value}"

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        is_permission_operation = False
        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        for kind in kinds:
            schema = get_schema(db=db, branch=branch, node_schema=kind)
            if is_permission_operation := kind in (
                InfrahubKind.BASEPERMISSION,
                InfrahubKind.GLOBALPERMISSION,
                InfrahubKind.OBJECTPERMISSION,
            ) or (isinstance(schema, NodeSchema) and InfrahubKind.BASEPERMISSION in schema.inherit_from):
                break

        if not is_permission_operation:
            return CheckerResolution.NEXT_CHECKER

        for permission_backend in registry.permission_backends:
            if not await permission_backend.has_permission(
                db=db, account_id=account_session.account_id, permission=self.permission_required, branch=branch
            ):
                raise PermissionDeniedError("You do not have the permission to manage permissions")

        return CheckerResolution.NEXT_CHECKER


class RepositoryManagerPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can add/edit/delete repository objects.

    This is similar to object permission checker except that we only care about mutations on repositories.
    """

    permission_required = f"global:{GlobalPermissions.MANAGE_REPOSITORIES.value}:{PermissionDecision.ALLOWED_ALL.value}"

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        is_repository_operation = False
        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        for kind in kinds:
            schema = get_schema(db=db, branch=branch, node_schema=kind)
            if is_repository_operation := kind in (
                InfrahubKind.GENERICREPOSITORY,
                InfrahubKind.REPOSITORY,
                InfrahubKind.READONLYREPOSITORY,
            ) or (isinstance(schema, NodeSchema) and InfrahubKind.GENERICREPOSITORY in schema.inherit_from):
                break

        if not is_repository_operation or not analyzed_query.contains_mutation:
            return CheckerResolution.NEXT_CHECKER

        for permission_backend in registry.permission_backends:
            if not await permission_backend.has_permission(
                db=db, account_id=account_session.account_id, permission=self.permission_required, branch=branch
            ):
                raise PermissionDeniedError("You do not have the permission to manage repositories")

        return CheckerResolution.NEXT_CHECKER
