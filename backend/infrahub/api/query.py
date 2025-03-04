from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Body, Depends, Path, Query, Request
from graphql import graphql
from pydantic import BaseModel, Field

from infrahub.api.dependencies import BranchParams, get_branch_params, get_current_user, get_db
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreGraphQLQuery
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.api.dependencies import build_graphql_query_permission_checker
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.metrics import (
    GRAPHQL_DURATION_METRICS,
    GRAPHQL_QUERY_DEPTH_METRICS,
    GRAPHQL_QUERY_HEIGHT_METRICS,
    GRAPHQL_QUERY_OBJECTS_METRICS,
    GRAPHQL_QUERY_VARS_METRICS,
    GRAPHQL_RESPONSE_SIZE_METRICS,
    GRAPHQL_TOP_LEVEL_QUERIES_METRICS,
)
from infrahub.graphql.utils import extract_data
from infrahub.groups.models import RequestGraphQLQueryGroupUpdate
from infrahub.log import get_logger
from infrahub.workflows.catalogue import GRAPHQL_QUERY_GROUP_UPDATE

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.graphql.auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
    from infrahub.services import InfrahubServices


log = get_logger()
router = APIRouter(prefix="/query")


class QueryPayload(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


async def execute_query(
    db: InfrahubDatabase,
    request: Request,
    branch_params: BranchParams,
    query_id: str,
    params: dict[str, str],
    update_group: bool,
    subscribers: list[str],
    permission_checker: GraphQLQueryPermissionChecker,
    account_session: AccountSession,
) -> dict[str, Any]:
    gql_query = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=query_id, kind=CoreGraphQLQuery, branch=branch_params.branch, at=branch_params.at
    )

    context = InfrahubContext.init(branch=branch_params.branch, account=account_session)

    gql_params = await prepare_graphql_params(
        db=db,
        branch=branch_params.branch,
        at=branch_params.at,
        account_session=account_session,
        service=request.app.state.service,
    )
    schema_branch = db.schema.get_schema_branch(name=branch_params.branch.name)

    analyzed_query = InfrahubGraphQLQueryAnalyzer(
        query=gql_query.query.value,
        schema=gql_params.schema,
        schema_branch=schema_branch,
        branch=branch_params.branch,
    )
    await permission_checker.check(
        db=db,
        account_session=account_session,
        analyzed_query=analyzed_query,
        query_parameters=gql_params,
        branch=branch_params.branch,
    )

    labels = {
        "type": "mutation" if analyzed_query.contains_mutation else "query",
        "branch": branch_params.branch.name,
        "operation": "",
        "name": gql_query.name.value,
        "query_id": query_id,
    }

    with GRAPHQL_DURATION_METRICS.labels(**labels).time():
        result = await graphql(
            schema=gql_params.schema,
            source=gql_query.query.value,
            context_value=gql_params.context,
            root_value=None,
            variable_values=params,
        )

    data = extract_data(query_name=gql_query.name.value, result=result)

    GRAPHQL_RESPONSE_SIZE_METRICS.labels(**labels).observe(len(data))
    GRAPHQL_QUERY_DEPTH_METRICS.labels(**labels).observe(await analyzed_query.calculate_depth())
    GRAPHQL_QUERY_HEIGHT_METRICS.labels(**labels).observe(await analyzed_query.calculate_height())
    GRAPHQL_QUERY_VARS_METRICS.labels(**labels).observe(len(analyzed_query.variables))
    GRAPHQL_TOP_LEVEL_QUERIES_METRICS.labels(**labels).observe(analyzed_query.nbr_queries)
    GRAPHQL_QUERY_OBJECTS_METRICS.labels(**labels).observe(len(analyzed_query.query_report.impacted_models))

    response_payload: dict[str, Any] = {"data": data}

    related_node_ids = gql_params.context.related_node_ids or set()

    if update_group:
        service: InfrahubServices = request.app.state.service
        model = RequestGraphQLQueryGroupUpdate(
            branch=branch_params.branch.name,
            query_id=gql_query.id,
            query_name=gql_query.name.value,
            related_node_ids=sorted(related_node_ids),
            subscribers=sorted(subscribers),
            params=params,
        )
        await service.workflow.submit_workflow(
            workflow=GRAPHQL_QUERY_GROUP_UPDATE, context=context, parameters={"model": model}
        )

    return response_payload


@router.post("/{query_id}")
async def graphql_query_post(
    request: Request,
    payload: QueryPayload = Body(
        QueryPayload(),  # noqa: B008
        description="Payload of the request, must be used to provide the variables",
    ),
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    subscribers: list[str] = Query(
        [], description=f"List of subscribers to attach to the {InfrahubKind.GRAPHQLQUERYGROUP}"
    ),
    update_group: bool = Query(
        False,
        description=f"When True create or update a {InfrahubKind.GRAPHQLQUERYGROUP} with all nodes related to this query.",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    account_session: AccountSession = Depends(get_current_user),
    permission_checker: GraphQLQueryPermissionChecker = Depends(build_graphql_query_permission_checker),
) -> dict:
    return await execute_query(
        db=db,
        request=request,
        branch_params=branch_params,
        query_id=query_id,
        params=payload.variables,
        update_group=update_group,
        subscribers=subscribers,
        permission_checker=permission_checker,
        account_session=account_session,
    )


@router.get("/{query_id}")
async def graphql_query_get(
    request: Request,
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    subscribers: list[str] = Query(
        [], description=f"List of subscribers to attach to the {InfrahubKind.GRAPHQLQUERYGROUP}"
    ),
    update_group: bool = Query(
        False,
        description=f"When True create or update a {InfrahubKind.GRAPHQLQUERYGROUP} with all nodes related to this query.",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    account_session: AccountSession = Depends(get_current_user),
    permission_checker: GraphQLQueryPermissionChecker = Depends(build_graphql_query_permission_checker),
) -> dict:
    params = {
        key: value
        for key, value in request.query_params.items()
        if key not in ["branch", "at", "update_group", "subscribers"]
    }

    return await execute_query(
        db=db,
        request=request,
        branch_params=branch_params,
        query_id=query_id,
        params=params,
        update_group=update_group,
        subscribers=subscribers,
        permission_checker=permission_checker,
        account_session=account_session,
    )
