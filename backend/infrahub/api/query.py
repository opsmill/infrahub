from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Path, Request
from graphql import graphql

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.graphql.utils import extract_data

router = APIRouter(prefix="/query")


@router.get("/{query_id}")
async def graphql_query(
    request: Request,
    query_id: str = Path(description="ID or Name of the GraphQL query to execute"),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Dict:
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    gql_query = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=query_id, schema_name="CoreGraphQLQuery", branch=branch_params.branch, at=branch_params.at
    )

    schema_branch = registry.schema.get_schema_branch(name=branch_params.branch.name)
    gql_schema = await schema_branch.get_graphql_schema(db=db)

    result = await graphql(
        gql_schema,
        source=gql_query.query.value,  # type: ignore[attr-defined]
        context_value={
            "infrahub_branch": branch_params.branch,
            "infrahub_at": branch_params.at,
            "infrahub_database": request.app.state.db,
        },
        root_value=None,
        variable_values=params,
    )
    data = extract_data(query_name=gql_query.name.value, result=result)  # type: ignore[attr-defined]

    response_payload: Dict[str, Any] = {"data": data}

    return response_payload
