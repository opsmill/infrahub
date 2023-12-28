from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from fastapi import APIRouter, Depends, Path, Query, Request
from graphql import graphql
from infrahub_sdk.utils import dict_hash

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core import registry
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.graphql.utils import extract_data
from infrahub.log import get_logger
from infrahub.message_bus import messages

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient

log = get_logger()
router = APIRouter(prefix="/query")


@router.get("/{query_id}")
async def graphql_query(
    request: Request,
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    subscribers: List[str] = Query([], description="List of subscribers to attach to the CoreGraphqlQueryGroup"),
    update_group: bool = Query(
        False, description="When True create or update a CoreGraphqlQueryGroup with all nodes related to this query."
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

    gql_query = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=query_id, schema_name="CoreGraphQLQuery", branch=branch_params.branch, at=branch_params.at
    )

    schema_branch = registry.schema.get_schema_branch(name=branch_params.branch.name)
    gql_schema = await schema_branch.get_graphql_schema(db=db)

    related_node_ids: set[str] = set()
    result = await graphql(
        gql_schema,
        source=gql_query.query.value,  # type: ignore[attr-defined]
        context_value={
            "infrahub_branch": branch_params.branch,
            "infrahub_at": branch_params.at,
            "infrahub_database": request.app.state.db,
            "related_node_ids": related_node_ids,
        },
        root_value=None,
        variable_values=params,
    )
    data = extract_data(query_name=gql_query.name.value, result=result)  # type: ignore[attr-defined]

    response_payload: Dict[str, Any] = {"data": data}

    if update_group:
        rpc_client: InfrahubRpcClient = request.app.state.rpc_client
        await rpc_client.send(
            message=messages.RequestGraphQLQueryGroupUpdate(
                branch=branch_params.branch.name,
                query_id=gql_query.id,
                query_name=gql_query.name.value,  # type: ignore[attr-defined]
                related_node_ids=related_node_ids,
                subscribers=set(subscribers),
                params_hash=dict_hash(params),
            )
        )

    return response_payload
