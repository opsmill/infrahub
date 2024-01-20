"""
This code has been forked from https://github.com/ciscorn/starlette-graphene3 in order to support branch and dynamic schema.
"""

from __future__ import annotations

import asyncio
import json
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

from graphql import (  # pylint: disable=no-name-in-module
    ExecutionContext,
    ExecutionResult,
    GraphQLError,
    Middleware,
    OperationType,
    graphql,
    parse,
    subscribe,
    validate,
)
from graphql.utilities import (  # pylint: disable=no-name-in-module,import-error
    get_operation_ast,
)
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

# pylint: disable=no-name-in-module,unused-argument,ungrouped-imports,raise-missing-from

try:
    # graphql-core==3.2.*
    from graphql import GraphQLFormattedError
    from graphql.error.graphql_error import format_error
except ImportError:
    # graphql-core==3.1.*
    from graphql import format_error

    GraphQLFormattedError = Dict[str, Any]

from infrahub_sdk.utils import str_to_bool

import infrahub.config as config
from infrahub.api.dependencies import api_key_scheme, cookie_auth_scheme, jwt_scheme
from infrahub.auth import AccountSession, authentication_token
from infrahub.core import get_branch, registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import BranchNotFound
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.log import get_logger

if TYPE_CHECKING:
    import graphene
    from graphql import GraphQLSchema
    from graphql.language.ast import (  # pylint: disable=no-name-in-module,import-error
        DocumentNode,
        OperationDefinitionNode,
    )
    from starlette.types import Receive, Scope, Send

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from .auth.query_permission_checker.checker import GraphQLQueryPermissionChecker


GQL_CONNECTION_ACK = "connection_ack"
GQL_CONNECTION_ERROR = "connection_error"
GQL_CONNECTION_INIT = "connection_init"
GQL_CONNECTION_TERMINATE = "connection_terminate"
GQL_COMPLETE = "complete"
GQL_DATA = "data"
GQL_ERROR = "error"
GQL_START = "start"
GQL_STOP = "stop"

ContextValue = Union[Any, Callable[[HTTPConnection], Any]]
RootValue = Any


class InfrahubGraphQLApp:
    def __init__(
        self,
        permission_checker: GraphQLQueryPermissionChecker,
        schema: graphene.Schema = None,
        *,
        on_get: Optional[Callable[[Request], Union[Response, Awaitable[Response]]]] = None,
        root_value: RootValue = None,
        middleware: Optional[Middleware] = None,
        error_formatter: Callable[[GraphQLError], GraphQLFormattedError] = format_error,
        execution_context_class: Optional[Type[ExecutionContext]] = None,
    ):
        self._schema = schema
        self.on_get = on_get
        self.root_value = root_value
        self.error_formatter = error_formatter
        self.middleware = middleware
        self.execution_context_class = execution_context_class
        self.logger = get_logger(name="infrahub.graphql")
        self.permission_checker = permission_checker

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope=scope, receive=receive)
            response: Optional[Response] = None
            jwt_auth = await jwt_scheme(request)
            api_key = await api_key_scheme(request)
            cookie_auth = await cookie_auth_scheme(request)

            db: InfrahubDatabase = request.app.state.db

            async with db.start_session() as db:
                jwt_token = None
                if jwt_auth:
                    jwt_token = jwt_auth.credentials
                elif cookie_auth and not api_key:
                    jwt_token = cookie_auth
                account_session = await authentication_token(jwt_token=jwt_token, api_key=api_key, db=db)

                # Retrieve the branch name from the request and validate that it exist in the database
                try:
                    branch_name = request.path_params.get("branch_name", config.SETTINGS.main.default_branch)
                    branch = await get_branch(db=db, branch=branch_name)
                    branch.ephemeral_rebase = str_to_bool(request.query_params.get("rebase", False))
                except BranchNotFound as exc:
                    response = JSONResponse({"errors": [exc.message]}, status_code=404)

                if request.method == "POST" and not response:
                    response = await self._handle_http_request(
                        request=request, db=db, branch=branch, account_session=account_session
                    )
                elif request.method == "GET" and not response:
                    response = await self._get_on_get(request)
                elif request.method == "OPTIONS" and not response:
                    response = Response(status_code=200, headers={"Allow": "GET, POST, OPTIONS"})

                if not response:
                    response = Response(status_code=405)

                await response(scope, receive, send)

        elif scope["type"] == "websocket":
            websocket = WebSocket(scope=scope, receive=receive, send=send)

            db: InfrahubDatabase = websocket.app.state.db

            async with db.start_session() as db:
                branch_name = websocket.path_params.get("branch_name", config.SETTINGS.main.default_branch)
                branch = await get_branch(db=db, branch=branch_name)
                branch.ephemeral_rebase = str_to_bool(websocket.path_params.get("rebase", False))

                await self._run_websocket_server(db=db, branch=branch, websocket=websocket)

        else:
            raise ValueError(f"Unsupported scope type: ${scope['type']}")

    async def _get_on_get(self, request: Request) -> Optional[Response]:
        handler = self.on_get

        if handler is None:
            return None

        response = handler(request)
        if isawaitable(response):
            return await cast(Awaitable[Response], response)

        return cast(Response, response)

    async def _get_context_value(
        self, db: InfrahubDatabase, request: HTTPConnection, branch: Branch, account_session: AccountSession
    ) -> Dict:
        context_value = {
            "infrahub_branch": branch,
            "infrahub_at": Timestamp(request.query_params.get("at", None)),
            "request": request,
            "background": BackgroundTasks(),
            "infrahub_database": db,
            "infrahub_rpc_client": request.app.state.rpc_client,
            "account_session": account_session,
            "related_node_ids": set(),
        }

        return context_value

    async def _get_context_value_ws(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        websocket: WebSocket,
        account_session: Optional[AccountSession] = None,
    ) -> Dict:
        context_value = {
            "infrahub_branch": branch,
            "infrahub_at": Timestamp(),
            "background": BackgroundTasks(),
            "infrahub_database": db,
            "infrahub_rpc_client": websocket.app.state.rpc_client,
            "account_session": account_session,
            "related_node_ids": set(),
        }
        return context_value

    async def _handle_http_request(
        self, request: Request, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> JSONResponse:
        try:
            operations = await _get_operation_from_request(request)
        except ValueError as exc:
            return JSONResponse({"errors": [exc.args[0]]}, status_code=400)

        if isinstance(operations, list):
            return JSONResponse({"errors": ["This server does not support batching"]}, status_code=400)

        operation = operations
        query = operation["query"]
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        graphql_schema = await schema_branch.get_graphql_schema(db=db)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(query=query, schema=graphql_schema, branch=branch)
        await self.permission_checker.check(account_session=account_session, analyzed_query=analyzed_query)

        variable_values = operation.get("variables")
        operation_name = operation.get("operationName")
        context_value = await self._get_context_value(
            request=request, db=db, branch=branch, account_session=account_session
        )

        result = await graphql(
            schema=graphql_schema,
            source=query,
            context_value=context_value,
            root_value=self.root_value,
            middleware=self.middleware,
            variable_values=variable_values,
            operation_name=operation_name,
            execution_context_class=self.execution_context_class,
        )

        response: Dict[str, Any] = {"data": result.data}
        if result.errors:
            for error in result.errors:
                if error.original_error:
                    self.logger.error(
                        "An exception occurred in resolvers",
                        exc_info=error.original_error,
                    )
            response["errors"] = [self.error_formatter(error) for error in result.errors]

        return JSONResponse(
            response,
            status_code=200,
            background=context_value.get("background"),
        )

    async def _run_websocket_server(self, db: InfrahubDatabase, branch: Branch, websocket: WebSocket) -> None:
        subscriptions: Dict[str, AsyncGenerator[Any, None]] = {}
        await websocket.accept("graphql-ws")
        try:
            while WebSocketState.DISCONNECTED not in (websocket.client_state, websocket.application_state):
                message = await websocket.receive_json()
                await self._handle_websocket_message(
                    db=db, branch=branch, message=message, websocket=websocket, subscriptions=subscriptions
                )
        except WebSocketDisconnect:
            pass
        finally:
            if subscriptions:
                await asyncio.gather(*(subscription.aclose() for _, subscription in subscriptions.items()))

    async def _handle_websocket_message(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        message: Dict[str, Any],
        websocket: WebSocket,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
    ) -> None:
        operation_id = cast(str, message.get("id"))
        message_type = cast(str, message.get("type"))

        if message_type == GQL_CONNECTION_INIT:
            websocket.scope["connection_params"] = message.get("payload")
        elif message_type == GQL_CONNECTION_TERMINATE:
            await websocket.close()
        elif message_type == GQL_START:
            await self._ws_on_start(
                db=db,
                branch=branch,
                data=message.get("payload"),
                operation_id=operation_id,
                websocket=websocket,
                subscriptions=subscriptions,
            )
        elif message_type == GQL_STOP:
            if operation_id in subscriptions:
                await subscriptions[operation_id].aclose()
                del subscriptions[operation_id]

    async def _ws_on_start(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        data: Any,
        operation_id: str,
        websocket: WebSocket,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
    ) -> None:
        query = data["query"]
        variable_values = data.get("variables")
        operation_name = data.get("operationName")

        context_value = await self._get_context_value_ws(db=db, branch=branch, websocket=websocket)
        errors: List[GraphQLError] = []
        operation: Optional[OperationDefinitionNode] = None
        document: Optional[DocumentNode] = None

        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        graphql_schema = await schema_branch.get_graphql_schema(db=db)

        try:
            document = parse(query)
            operation = get_operation_ast(document, operation_name)
            errors = validate(graphql_schema, document)
        except GraphQLError as e:
            errors = [e]

        if not errors:
            assert document is not None
            if operation and operation.operation == OperationType.SUBSCRIPTION:
                errors = await self._start_subscription(
                    graphql_schema=graphql_schema,
                    websocket=websocket,
                    operation_id=operation_id,
                    subscriptions=subscriptions,
                    document=document,
                    context_value=context_value,
                    variable_values=variable_values,
                    operation_name=operation_name,
                )
            else:
                raise ValueError(f"Unsupported operation (type {operation}) for the websocket endpoint")

        if errors:
            await websocket.send_json(
                {
                    "type": GQL_ERROR,
                    "id": operation_id,
                    "payload": self.error_formatter(errors[0]),
                }
            )

    async def _start_subscription(
        self,
        graphql_schema: GraphQLSchema,
        websocket: WebSocket,
        operation_id: str,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
        document: DocumentNode,
        context_value: ContextValue,
        variable_values: Dict[str, Any],
        operation_name: str,
    ) -> List[GraphQLError]:
        result = await subscribe(
            schema=graphql_schema,
            document=document,
            context_value=context_value,
            root_value=self.root_value,
            variable_values=variable_values,
            operation_name=operation_name,
        )

        if isinstance(result, ExecutionResult) and result.errors:
            return result.errors

        asyncgen = cast(AsyncGenerator[Any, None], result)
        subscriptions[operation_id] = asyncgen
        asyncio.create_task(self._observe_subscription(asyncgen, operation_id, websocket))
        return []

    async def _observe_subscription(
        self,
        asyncgen: AsyncGenerator[Any, None],
        operation_id: str,
        websocket: WebSocket,
    ) -> None:
        try:
            async for result in asyncgen:
                payload = {"data": result.data}
                await websocket.send_json({"type": GQL_DATA, "id": operation_id, "payload": payload})
        except Exception as error:  # pylint: disable=broad-exception-caught
            if not isinstance(error, GraphQLError):
                self.logger.error("An exception occurred in resolvers", exc_info=error)
                error = GraphQLError(str(error), original_error=error)
            await websocket.send_json(
                {
                    "type": GQL_DATA,
                    "id": operation_id,
                    "payload": {"errors": [self.error_formatter(error)]},
                }
            )

        if WebSocketState.DISCONNECTED not in (websocket.client_state, websocket.application_state):
            await websocket.send_json({"type": GQL_COMPLETE, "id": operation_id})


async def _get_operation_from_request(
    request: Request,
) -> Union[Dict[str, Any], List[Any]]:
    content_type = request.headers.get("Content-Type", "").split(";")[0]
    if content_type == "application/json":
        try:
            return cast(Union[Dict[str, Any], List[Any]], await request.json())
        except (TypeError, ValueError):
            raise ValueError("Request body is not a valid JSON")
    elif content_type == "multipart/form-data":
        return await _get_operation_from_multipart(request)
    else:
        raise ValueError("Content-type must be application/json or multipart/form-data")


async def _get_operation_from_multipart(
    request: Request,
) -> Union[Dict[str, Any], List[Any]]:
    try:
        request_body = await request.form()
    except Exception:
        raise ValueError("Request body is not a valid multipart/form-data")

    try:
        operations = json.loads(request_body.get("operations"))
    except (TypeError, ValueError):
        raise ValueError("'operations' must be a valid JSON")
    if not isinstance(operations, (dict, list)):
        raise ValueError("'operations' field must be an Object or an Array")

    try:
        name_path_map = json.loads(request_body.get("map"))
    except (TypeError, ValueError):
        raise ValueError("'map' field must be a valid JSON")
    if not isinstance(name_path_map, dict):
        raise ValueError("'map' field must be an Object")

    files = {k: v for (k, v) in request_body.items() if isinstance(v, UploadFile)}
    for name, paths in name_path_map.items():
        file = files.get(name)
        if not file:
            raise ValueError(f"File fields don't contain a valid UploadFile type for '{name}' mapping")

        for path in paths:
            path = tuple(path.split("."))
            _inject_file_to_operations(operations, file, path)

    return operations


def _inject_file_to_operations(ops_tree: Any, _file: UploadFile, path: Sequence[str]) -> None:
    k = path[0]
    key: Union[str, int]
    try:
        key = int(k)
    except ValueError:
        key = k
    if len(path) == 1:
        if ops_tree[key] is None:
            ops_tree[key] = _file
    else:
        _inject_file_to_operations(ops_tree[key], _file, path[1:])
