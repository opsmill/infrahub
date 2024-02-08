from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from fastapi import APIRouter, Body, Depends, Path, Query, Request
from graphql import graphql
from pydantic import BaseModel, Field

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
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
from infrahub.log import get_logger
from infrahub.message_bus import messages

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient

log = get_logger()
router = APIRouter(prefix="/query")


class QueryPayload(BaseModel):
    variables: Dict[str, str] = Field(default_factory=dict)


async def execute_query(
    db: InfrahubDatabase,
    request: Request,
    branch_params: BranchParams,
    query_id: str,
    params: Dict[str, str],
    update_group: bool,
    subscribers: List[str],
) -> Dict[str, Any]:
    gql_query = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=query_id, schema_name=InfrahubKind.GRAPHQLQUERY, branch=branch_params.branch, at=branch_params.at
    )

    gql_params = prepare_graphql_params(db=db, branch=branch_params.branch, at=branch_params.at)
    analyzed_query = InfrahubGraphQLQueryAnalyzer(
        query=gql_query.query.value, schema=gql_params.schema, branch=branch_params.branch
    )

    labels = {
        "type": "mutation" if analyzed_query.contains_mutation else "query",
        "branch": branch_params.branch.name,
        "operation": "",
        "name": gql_query.name.value,
    }

    with GRAPHQL_DURATION_METRICS.labels(**labels).time():
        result = await graphql(
            schema=gql_params.schema,
            source=gql_query.query.value,  # type: ignore[attr-defined]
            context_value=gql_params.context,
            root_value=None,
            variable_values=params,
        )

    data = extract_data(query_name=gql_query.name.value, result=result)  # type: ignore[attr-defined]

    GRAPHQL_RESPONSE_SIZE_METRICS.labels(**labels).observe(len(data))
    GRAPHQL_QUERY_DEPTH_METRICS.labels(**labels).observe(await analyzed_query.calculate_depth())
    GRAPHQL_QUERY_HEIGHT_METRICS.labels(**labels).observe(await analyzed_query.calculate_height())
    GRAPHQL_QUERY_VARS_METRICS.labels(**labels).observe(len(analyzed_query.variables))
    GRAPHQL_TOP_LEVEL_QUERIES_METRICS.labels(**labels).observe(analyzed_query.nbr_queries)
    GRAPHQL_QUERY_OBJECTS_METRICS.labels(**labels).observe(
        len(await analyzed_query.get_models_in_use(types=gql_params.context.types))
    )

    response_payload: Dict[str, Any] = {"data": data}

    related_node_ids = gql_params.context.related_node_ids or set()

    if update_group:
        rpc_client: InfrahubRpcClient = request.app.state.rpc_client
        await rpc_client.send(
            message=messages.RequestGraphQLQueryGroupUpdate(
                branch=branch_params.branch.name,
                query_id=gql_query.id,
                query_name=gql_query.name.value,  # type: ignore[attr-defined]
                related_node_ids=sorted(list(related_node_ids)),
                subscribers=sorted(subscribers),
                params=params,
            )
        )

    return response_payload


@router.post("/{query_id}")
async def graphql_query_post(
    request: Request,
    payload: QueryPayload = Body(
        QueryPayload(), description="Payload of the request, must be used to provide the variables"
    ),
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    subscribers: List[str] = Query(
        [], description=f"List of subscribers to attach to the {InfrahubKind.GRAPHQLQUERYGROUP}"
    ),
    update_group: bool = Query(
        False,
        description=f"When True create or update a {InfrahubKind.GRAPHQLQUERYGROUP} with all nodes related to this query.",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Dict:
    return await execute_query(
        db=db,
        request=request,
        branch_params=branch_params,
        query_id=query_id,
        params=payload.variables,
        update_group=update_group,
        subscribers=subscribers,
    )


@router.get("/{query_id}")
async def graphql_query_get(
    request: Request,
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    subscribers: List[str] = Query(
        [], description=f"List of subscribers to attach to the {InfrahubKind.GRAPHQLQUERYGROUP}"
    ),
    update_group: bool = Query(
        False,
        description=f"When True create or update a {InfrahubKind.GRAPHQLQUERYGROUP} with all nodes related to this query.",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Dict:
    params = {
        key: value
        for key, value in request.query_params.items()
        if key not in ["branch", "rebase", "at", "update_group", "subscribers"]
    }

    return await execute_query(
        db=db,
        request=request,
        branch_params=branch_params,
        query_id=query_id,
        params=params,
        update_group=update_group,
        subscribers=subscribers,
    )
