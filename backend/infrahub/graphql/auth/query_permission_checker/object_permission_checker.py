from infrahub.auth import AccountSession
from infrahub.core.account import ObjectPermission
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.utils import extract_camelcase_words

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ObjectPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    account_session: AccountSession

    async def supports(self, account_session: AccountSession) -> bool:
        self.account_session = account_session
        return self.account_session.authenticated

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
                str(
                    # Create a object permission instance just to get its string representation
                    ObjectPermission(
                        id="",
                        namespace=extracted_words[0].lower(),
                        kind="".join(extracted_words[1:]).lower(),
                        action=action,
                    )
                )
            )

        if not self.account_session.permissions or not self.account_session.permissions.has_permissions(
            permissions=permissions
        ):
            # raise PermissionDeniedError(f"You are not allowed to perform: {kind_action_map}")
            ...

        return CheckerResolution.NEXT_CHECKER
