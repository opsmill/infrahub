from fastapi import APIRouter

from .dependencies import build_graphql_app

router = APIRouter()


graphql_app = build_graphql_app()
router.add_route(path="/", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
router.add_route(path="/{branch_name:path}", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
# router.add_websocket_route(path="/", route=graphql_app)
# router.add_websocket_route(path="/{branch_name:str}", route=graphql_app)
