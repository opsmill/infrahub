from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.utils import extract_camelcase_words

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ObjectPermissionChecker(GraphQLQueryPermissionCheckerInterface):
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
        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        # Identify which operation is performed on which kind
        kind_action_map: dict[str, str] = {}
        for operation in analyzed_query.operations:
            for kind in kinds:
                if operation.name and operation.name.startswith(kind):
                    # An empty string after prefix removal means a query to "view"
                    kind_action_map[kind] = operation.name[len(kind) :] or "view"

        # Infer required permissions from the kind/operation map
        permissions: list[str] = []
        for kind, action in kind_action_map.items():
            extracted_words = extract_camelcase_words(kind)
            permissions.append(
                str(
                    # Create a object permission instance just to get its string representation
                    ObjectPermission(
                        id="",
                        branch=branch.name,
                        namespace=extracted_words[0],
                        name="".join(extracted_words[1:]),
                        action=action.lower(),
                        decision=PermissionDecision.ALLOW.value,
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
