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
from tests.component.graphql.hidden_mutation_cases import HIDDEN_MUTATION_CASES, HiddenMutationCase


class TestAnonymousAuthChecker:
    def setup_method(self) -> None:
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.query_parameters = MagicMock(spec=GraphqlParams)
        self.mock_anonymous_setting_get = MagicMock(return_value=True)
        self.checker = AnonymousGraphQLPermissionChecker(self.mock_anonymous_setting_get)

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

    async def test_check_passes(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.mock_anonymous_setting_get.return_value = True
        self.graphql_query.contains_mutation = False

        await self.checker.check(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=self.query_parameters,
            branch=branch,
        )


@pytest.fixture
def anonymous_checker() -> AnonymousGraphQLPermissionChecker:
    return AnonymousGraphQLPermissionChecker(lambda: True)


@pytest.mark.parametrize("case", HIDDEN_MUTATION_CASES, ids=lambda case: case.name)
async def test_anonymous_checker_rejects_mutation_hidden_in_fragment(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    anonymous_checker: AnonymousGraphQLPermissionChecker,
    case: HiddenMutationCase,
) -> None:
    """An anonymous caller cannot slip a mutation past the checker by wrapping it in a fragment.

    The checker is driven by a real analyzer here, so this exercises the whole analyzer-to-checker
    seam rather than a mocked value.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    analyzed_query = InfrahubGraphQLQueryAnalyzer(
        query=case.query, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    account_session = AccountSession(account_id="anonymous", auth_type=AuthType.JWT, authenticated=False)

    with pytest.raises(AuthorizationError):
        await anonymous_checker.check(
            db=db,
            account_session=account_session,
            analyzed_query=analyzed_query,
            query_parameters=MagicMock(spec=GraphqlParams),
            branch=default_branch,
        )


async def test_anonymous_checker_allows_genuine_read(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    anonymous_checker: AnonymousGraphQLPermissionChecker,
) -> None:
    """A genuine anonymous read passes the checker, so the hidden-mutation rejection is specific to it."""
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    analyzed_query = InfrahubGraphQLQueryAnalyzer(
        query="query A { __typename }", schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    account_session = AccountSession(account_id="anonymous", auth_type=AuthType.JWT, authenticated=False)

    await anonymous_checker.check(
        db=db,
        account_session=account_session,
        analyzed_query=analyzed_query,
        query_parameters=MagicMock(spec=GraphqlParams),
        branch=default_branch,
    )
