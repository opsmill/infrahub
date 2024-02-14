from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from graphql import print_schema

from infrahub.api.dependencies import get_branch_dep
from infrahub.core import registry
from infrahub.core.branch import Branch

from .dependencies import build_graphql_app

router = APIRouter(redirect_slashes=False)


graphql_app = build_graphql_app()
router.add_route(path="/graphql", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
router.add_route(path="/graphql/{branch_name:path}", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
router.add_websocket_route(path="/graphql", endpoint=graphql_app)
router.add_websocket_route(path="/graphql/{branch_name:str}", endpoint=graphql_app)


@router.get("/schema.graphql")
async def get_graphql_schema(branch: Branch = Depends(get_branch_dep)) -> PlainTextResponse:
    schema = registry.schema.get_schema_branch(name=branch.name)
    gql_schema = schema.get_graphql_schema()

    return PlainTextResponse(content=print_schema(gql_schema))
