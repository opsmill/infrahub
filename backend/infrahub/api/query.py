from typing import Any, Dict

from fastapi import APIRouter, Depends, Path, Request, Response
from graphql import graphql
from neo4j import AsyncSession

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_session,
)
from infrahub.core import registry
from infrahub.core.manager import NodeManager

router = APIRouter(prefix="/query")


@router.get("/{query_id}")
async def graphql_query(
    request: Request,
    response: Response,
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    session: AsyncSession = Depends(get_session),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
):
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    gql_query = await NodeManager.get_one_by_id_or_default_filter(
        session=session, id=query_id, schema_name="CoreGraphQLQuery", branch=branch_params.branch, at=branch_params.at
    )

    schema_branch = registry.schema.get_schema_branch(name=branch_params.branch.name)
    gql_schema = await schema_branch.get_graphql_schema(session=session)

    result = await graphql(
        gql_schema,
        source=gql_query.query.value,  # type: ignore[attr-defined]
        context_value={
            "infrahub_branch": branch_params.branch,
            "infrahub_at": branch_params.at,
            "infrahub_database": request.app.state.db,
            "infrahub_session": session,
        },
        root_value=None,
        variable_values=params,
    )

    response_payload: Dict[str, Any] = {"data": result.data}

    if result.errors:
        response_payload["errors"] = []
        for error in result.errors:
            error_locations = error.locations or []
            response_payload["errors"].append(
                {
                    "message": error.message,
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error_locations],
                }
            )
        response.status_code = 500

    return response_payload
