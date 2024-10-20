from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from graphql import print_schema
from starlette.routing import Route, WebSocketRoute

from infrahub.api.dependencies import get_branch_dep
from infrahub.core.branch import Branch
from infrahub.graphql.manager import GraphQLSchemaManager

from .dependencies import build_graphql_app

router = APIRouter(redirect_slashes=False)


graphql_app = build_graphql_app()
router.routes.append(Route(path="/graphql", endpoint=graphql_app, methods=["POST", "OPTIONS"]))
router.routes.append(Route(path="/graphql/{branch_name:path}", endpoint=graphql_app, methods=["POST", "OPTIONS"]))
router.routes.append(WebSocketRoute(path="/graphql", endpoint=graphql_app))
router.routes.append(WebSocketRoute(path="/graphql/{branch_name:str}", endpoint=graphql_app))


@router.get("/schema.graphql", include_in_schema=False)
async def get_graphql_schema(branch: Branch = Depends(get_branch_dep)) -> PlainTextResponse:
    gqlm = GraphQLSchemaManager.get_manager_for_branch(branch=branch)
    graphql_schema = gqlm.get_graphql_schema()
    return PlainTextResponse(content=print_schema(graphql_schema))
