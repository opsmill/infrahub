from typing import Optional

from infrahub.auth import AccountPermissions, AccountSession
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.utils import extract_camelcase_words

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ObjectPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self) -> None:
        self.permissions: Optional[AccountPermissions] = None

    async def supports(self, account_session: AccountSession) -> bool:
        self.permissions = account_session.permissions
        return account_session.authenticated

    async def check(
        self, analyzed_query: InfrahubGraphQLQueryAnalyzer, query_parameters: GraphqlParams
    ) -> CheckerResolution:
        kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        # Identify which operation is performed on which kind
        kind_action_map: dict[str, str] = {}
        for operation in analyzed_query.operations:
            for kind in kinds:
                if operation.name.startswith(kind):
                    # An empty string after prefix removal means a query to "view"
                    kind_action_map[kind] = operation.name[len(kind) :].lower() or "view"

        # Infer required permissions from the kind/operation map
        permissions: list[str] = []
        for kind, action in kind_action_map.items():
            extracted_words = extract_camelcase_words(kind)
            permissions.append(
                AccountPermissions.infer_object_permission_string(
                    namespace=extracted_words[0].lower(), kind="".join(extracted_words[1:]).lower(), action=action
                )
            )

        if not self.permissions or not self.permissions.has_permissions(permissions=permissions):
            # raise PermissionDeniedError(f"You are not allowed to perform: {kind_action_map}")
            ...

        return CheckerResolution.NEXT_CHECKER
