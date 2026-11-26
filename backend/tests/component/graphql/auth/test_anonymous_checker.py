from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker
from infrahub.graphql.initialization import GraphqlParams, prepare_graphql_params
from infrahub.graphql.schema import QUERIES_REQUIRING_AUTHENTICATION


class TestAnonymousAuthChecker:
    def setup_method(self) -> None:
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.query_parameters = MagicMock(spec=GraphqlParams)
        self.graphql_query.operation_names = []
        self.mock_anonymous_setting_get = MagicMock(return_value=True)
        self.checker = AnonymousGraphQLPermissionChecker(
            anonymous_access_allowed_func=self.mock_anonymous_setting_get,
            operations_requiring_authentication=QUERIES_REQUIRING_AUTHENTICATION,
        )

    @pytest.mark.parametrize("is_authenticated,is_supported", [(True, False), (False, True)])
    async def test_supports_unauthenticated_accounts(
        self, db: InfrahubDatabase, branch: Branch, is_authenticated: bool, is_supported: bool
    ) -> None:
        self.account_session.authenticated = is_authenticated

        has_support = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is has_support

    @pytest.mark.parametrize("anonymous_setting,query_has_mutations", [(False, False), (False, True), (True, True)])
    async def test_failures_raise_error(
        self, db: InfrahubDatabase, branch: Branch, anonymous_setting: bool, query_has_mutations: bool
    ) -> None:
        self.mock_anonymous_setting_get.return_value = anonymous_setting
        self.graphql_query.contains_mutation = query_has_mutations

        with pytest.raises(AuthorizationError):
            await self.checker.check(
                db=db,
                account_session=self.account_session,
                analyzed_query=self.graphql_query,
                query_parameters=self.query_parameters,
                branch=branch,
            )

    @pytest.mark.parametrize("operation_name", sorted(QUERIES_REQUIRING_AUTHENTICATION))
    async def test_operation_requiring_authentication_raises_error(
        self, db: InfrahubDatabase, branch: Branch, operation_name: str
    ) -> None:
        # Even with anonymous access enabled and no mutation, an operation bound to the caller's
        # identity is rejected.
        self.mock_anonymous_setting_get.return_value = True
        self.graphql_query.contains_mutation = False
        self.graphql_query.operation_names = [operation_name]

        with pytest.raises(AuthorizationError, match=r"^Authentication is required to perform this operation$"):
            await self.checker.check(
                db=db,
                account_session=self.account_session,
                analyzed_query=self.graphql_query,
                query_parameters=self.query_parameters,
                branch=branch,
            )

    async def test_check_passes(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.mock_anonymous_setting_get.return_value = True
        self.graphql_query.contains_mutation = False
        self.graphql_query.operation_names = ["InfrahubInfo"]

        await self.checker.check(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=self.query_parameters,
            branch=branch,
        )


@pytest.mark.parametrize(
    "wrapped_mutation",
    [
        pytest.param(
            'query A { __typename } mutation B { ... on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
            id="inline-fragment",
        ),
        pytest.param(
            'query A { __typename } mutation B { ... { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
            id="inline-fragment-without-type-condition",
        ),
        pytest.param(
            "query A { __typename } mutation B { ...Hidden }"
            ' fragment Hidden on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } }',
            id="fragment-spread",
        ),
    ],
)
async def test_anonymous_checker_rejects_mutation_hidden_in_fragment(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    wrapped_mutation: str,
) -> None:
    """An anonymous caller cannot slip a mutation past the checker by wrapping it in a fragment.

    The checker is driven by a real analyzer here, so this exercises the whole analyzer-to-checker
    seam rather than a mocked ``contains_mutation`` value.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    checker = AnonymousGraphQLPermissionChecker(
        anonymous_access_allowed_func=lambda: True,
        operations_requiring_authentication=QUERIES_REQUIRING_AUTHENTICATION,
    )
    account_session = AccountSession(account_id="anonymous", auth_type=AuthType.JWT, authenticated=False)

    exploit = InfrahubGraphQLQueryAnalyzer(
        query=wrapped_mutation, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    with pytest.raises(AuthorizationError):
        await checker.check(
            db=db,
            account_session=account_session,
            analyzed_query=exploit,
            query_parameters=MagicMock(spec=GraphqlParams),
            branch=default_branch,
        )

    # Control: a genuine anonymous read is still allowed, so the rejection above is specific to the
    # hidden mutation and not a blanket refusal.
    control = InfrahubGraphQLQueryAnalyzer(
        query="query A { __typename }", schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    await checker.check(
        db=db,
        account_session=account_session,
        analyzed_query=control,
        query_parameters=MagicMock(spec=GraphqlParams),
        branch=default_branch,
    )
