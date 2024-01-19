from fastapi import APIRouter

from .dependencies import build_graphql_app

router = APIRouter(redirect_slashes=False)


graphql_app = build_graphql_app()
router.add_route(path="/graphql", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
router.add_route(path="/graphql/{branch_name:path}", endpoint=graphql_app, methods=["GET", "POST", "OPTIONS"])
router.add_websocket_route(path="/graphql", endpoint=graphql_app)
router.add_websocket_route(path="/graphql/{branch_name:str}", endpoint=graphql_app)
