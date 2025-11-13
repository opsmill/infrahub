from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from graphql import parse, print_ast, print_schema
from starlette.routing import Route, WebSocketRoute

from infrahub.api.dependencies import get_branch_dep, get_current_user
from infrahub.core import registry
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.graphql.schema_sort import sort_schema_ast

from .dependencies import build_graphql_app

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch

router = APIRouter(redirect_slashes=False)


graphql_app = build_graphql_app()
router.routes.append(Route(path="/graphql", endpoint=graphql_app, methods=["POST", "OPTIONS"]))
router.routes.append(Route(path="/graphql/{branch_name:path}", endpoint=graphql_app, methods=["POST", "OPTIONS"]))
router.routes.append(WebSocketRoute(path="/graphql", endpoint=graphql_app))
router.routes.append(WebSocketRoute(path="/graphql/{branch_name:str}", endpoint=graphql_app))


@router.get("/schema.graphql")
async def get_graphql_schema(
    branch: Branch = Depends(get_branch_dep),
    _: AccountSession = Depends(get_current_user),
    sort_schema: bool = Query(default=False, alias="sorted", description="Whether to sort the schema alphabetically."),
) -> PlainTextResponse:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    gqlm = graphql_registry.get_manager_for_branch(branch=branch, schema_branch=schema_branch)
    graphql_schema = gqlm.get_graphql_schema()

    if sort_schema:
        schema_str = print_schema(graphql_schema)
        schema_ast = parse(schema_str)
        sorted_schema_ast = sort_schema_ast(schema_ast)
        return PlainTextResponse(content=print_ast(sorted_schema_ast))

    return PlainTextResponse(content=print_schema(graphql_schema))
