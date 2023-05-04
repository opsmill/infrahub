"""
This code has been forked from https://github.com/ciscorn/starlette-graphene3 in order to support branch and dynamic schema.
"""

from __future__ import annotations

import asyncio
import json
import logging
from inspect import isawaitable
from typing import (
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

import graphene
from graphql import (  # pylint: disable=no-name-in-module
    ExecutionContext,
    ExecutionResult,
    GraphQLError,
    Middleware,
    OperationType,
    execute,
    graphql,
    parse,
    subscribe,
    validate,
)
from graphql.language.ast import (  # pylint: disable=no-name-in-module,import-error
    DocumentNode,
    OperationDefinitionNode,
)
from graphql.utilities import (  # pylint: disable=no-name-in-module,import-error
    get_operation_ast,
)
from neo4j import AsyncSession
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import Receive, Scope, Send
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

import infrahub.config as config
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import BranchNotFound
from infrahub.utils import str_to_bool


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


def make_graphiql_handler() -> Callable[[Request], Response]:
    def handler(request: Request) -> Response:
        return HTMLResponse(_GRAPHIQL_HTML)

    return handler


def make_playground_handler(playground_options: Optional[Dict[str, Any]] = None) -> Callable[[Request], Response]:
    playground_options_str = json.dumps(playground_options or {})
    content = _PLAYGROUND_HTML.replace("PLAYGROUND_OPTIONS", playground_options_str)

    def handler(request: Request) -> Response:
        return HTMLResponse(content)

    return handler


class InfrahubGraphQLApp:
    def __init__(
        self,
        schema: graphene.Schema = None,
        *,
        on_get: Optional[Callable[[Request], Union[Response, Awaitable[Response]]]] = None,
        root_value: RootValue = None,
        middleware: Optional[Middleware] = None,
        error_formatter: Callable[[GraphQLError], GraphQLFormattedError] = format_error,
        logger_name: Optional[str] = None,
        execution_context_class: Optional[Type[ExecutionContext]] = None,
        playground: bool = False,  # Deprecating. Use on_get instead.
    ):
        self._schema = schema
        self.on_get = on_get
        self.root_value = root_value
        self.error_formatter = error_formatter
        self.middleware = middleware
        self.execution_context_class = execution_context_class
        self.logger = logging.getLogger(logger_name or __name__)

        if playground and self.on_get is None:
            self.on_get = make_playground_handler()

    # async def _get_schema(self, session: AsyncSession):
    #     if not self._schema:
    #         default_branch = config.SETTINGS.main.default_branch
    #         await generate_object_types(session=session, branch=default_branch)
    #         types_dict = registry.get_all_graphql_type(branch=default_branch)
    #         types = list(types_dict.values())

    #         self._schema = graphene.Schema(
    #             query=await get_gql_query(session=session),
    #             mutation=await get_gql_mutation(session=session),
    #             subscription=await get_gql_subscription(session=session),
    #             types=types,
    #             auto_camelcase=False,
    #         )

    #     return self._schema

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope=scope, receive=receive)
            response: Optional[Response] = None

            async with request.app.state.db.session(database=config.SETTINGS.database.database) as session:
                # Retrieve the branch name from the request and validate that it exist in the database
                try:
                    branch_name = request.path_params.get("branch_name", config.SETTINGS.main.default_branch)
                    branch = await get_branch(session=session, branch=branch_name)
                    branch.ephemeral_rebase = str_to_bool(request.query_params.get("rebase", False))
                except BranchNotFound as exc:
                    response = JSONResponse({"errors": [exc.message]}, status_code=404)

                if request.method == "POST" and not response:
                    response = await self._handle_http_request(request=request, session=session, branch=branch)
                elif request.method == "GET" and not response:
                    response = await self._get_on_get(request)
                elif request.method == "OPTIONS" and not response:
                    response = Response(status_code=200, headers={"Allow": "GET, POST, OPTIONS"})

                if not response:
                    response = Response(status_code=405)

                await response(scope, receive, send)

        elif scope["type"] == "websocket":
            websocket = WebSocket(scope=scope, receive=receive, send=send)
            await self._run_websocket_server(websocket)

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

    async def _get_context_value(self, session: AsyncSession, request: HTTPConnection, branch: Branch) -> Dict:
        # info.context["infrahub_account"] = account

        context_value = {
            "infrahub_branch": branch,
            "infrahub_at": Timestamp(request.query_params.get("at", None)),
            "request": request,
            "background": BackgroundTasks(),
            "infrahub_database": request.app.state.db,
            "infrahub_rpc_client": request.app.state.rpc_client,
            "infrahub_session": session,
        }

        return context_value

    async def _handle_http_request(self, request: Request, session: AsyncSession, branch: Branch) -> JSONResponse:
        try:
            operations = await _get_operation_from_request(request)
        except ValueError as exc:
            return JSONResponse({"errors": [exc.args[0]]}, status_code=400)

        if isinstance(operations, list):
            return JSONResponse({"errors": ["This server does not support batching"]}, status_code=400)

        operation = operations
        query = operation["query"]
        variable_values = operation.get("variables")
        operation_name = operation.get("operationName")

        context_value = await self._get_context_value(session=session, request=request, branch=branch)

        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        graphql_schema = await schema_branch.get_graphql_schema(session=session)

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

    async def _run_websocket_server(self, websocket: WebSocket) -> None:
        subscriptions: Dict[str, AsyncGenerator[Any, None]] = {}
        await websocket.accept("graphql-ws")
        try:
            while WebSocketState.DISCONNECTED not in (websocket.client_state, websocket.application_state):
                message = await websocket.receive_json()
                await self._handle_websocket_message(message, websocket, subscriptions)
        except WebSocketDisconnect:
            pass
        finally:
            if subscriptions:
                await asyncio.gather(*(subscription.aclose() for _, subscription in subscriptions.items()))

    async def _handle_websocket_message(
        self,
        message: Dict[str, Any],
        websocket: WebSocket,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
    ) -> None:
        operation_id = cast(str, message.get("id"))
        message_type = cast(str, message.get("type"))

        if message_type == GQL_CONNECTION_INIT:
            websocket.scope["connection_params"] = message.get("payload")
            await websocket.send_json({"type": GQL_CONNECTION_ACK})
        elif message_type == GQL_CONNECTION_TERMINATE:
            await websocket.close()
        elif message_type == GQL_START:
            await self._ws_on_start(message.get("payload"), operation_id, websocket, subscriptions)
        elif message_type == GQL_STOP:
            if operation_id in subscriptions:
                await subscriptions[operation_id].aclose()
                del subscriptions[operation_id]

    async def _ws_on_start(
        self,
        data: Any,
        operation_id: str,
        websocket: WebSocket,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
    ) -> None:
        query = data["query"]
        variable_values = data.get("variables")
        operation_name = data.get("operationName")
        context_value = await self._get_context_value(websocket)  # pylint: disable=no-value-for-parameter
        errors: List[GraphQLError] = []
        operation: Optional[OperationDefinitionNode] = None
        document: Optional[DocumentNode] = None

        try:
            document = parse(query)
            operation = get_operation_ast(document, operation_name)
            errors = validate(self.schema.graphql_schema, document)  # pylint: disable=no-member
        except GraphQLError as e:
            errors = [e]

        if not errors:
            assert document is not None
            if operation and operation.operation == OperationType.SUBSCRIPTION:
                errors = await self._start_subscription(
                    websocket,
                    operation_id,
                    subscriptions,
                    document,
                    context_value,
                    variable_values,
                    operation_name,
                )
            else:
                errors = await self._handle_query_over_ws(
                    websocket,
                    operation_id,
                    document,
                    context_value,
                    variable_values,
                    operation_name,
                )

        if errors:
            await websocket.send_json(
                {
                    "type": GQL_ERROR,
                    "id": operation_id,
                    "payload": self.error_formatter(errors[0]),
                }
            )

    async def _handle_query_over_ws(
        self,
        websocket: WebSocket,
        operation_id: str,
        document: DocumentNode,
        context_value: ContextValue,
        variable_values: Dict[str, Any],
        operation_name: str,
    ) -> List[GraphQLError]:
        result = execute(
            self.schema.graphql_schema,  # pylint: disable=no-member
            document,
            root_value=self.root_value,
            context_value=context_value,
            variable_values=variable_values,
            operation_name=operation_name,
            middleware=self.middleware,
            execution_context_class=self.execution_context_class,
        )

        if isinstance(result, ExecutionResult) and result.errors:
            return result.errors

        if isawaitable(result):
            result = await cast(Awaitable[ExecutionResult], result)

        result = cast(ExecutionResult, result)

        payload: Dict[str, Any] = {}
        payload["data"] = result.data
        if result.errors:
            for error in result.errors:
                if error.original_error:
                    self.logger.error(
                        "An exception occurred in resolvers",
                        exc_info=error.original_error,
                    )
            payload["errors"] = [self.error_formatter(error) for error in result.errors]

        await websocket.send_json({"type": GQL_DATA, "id": operation_id, "payload": payload})
        return []

    async def _start_subscription(
        self,
        websocket: WebSocket,
        operation_id: str,
        subscriptions: Dict[str, AsyncGenerator[Any, None]],
        document: DocumentNode,
        context_value: ContextValue,
        variable_values: Dict[str, Any],
        operation_name: str,
    ) -> List[GraphQLError]:
        result = await subscribe(
            self.schema.graphql_schema,  # pylint: disable=no-member
            document,
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


_PLAYGROUND_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset=utf-8/>
  <meta name="viewport" content="user-scalable=no, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, minimal-ui">
  <title>GraphQL Playground</title>
  <link rel="stylesheet" href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/css/index.css" />
  <link rel="shortcut icon" href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/favicon.png" />
  <script src="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/js/middleware.js"></script>
</head>
<body>
  <div id="root">
    <style>
      body {
        background-color: rgb(23, 42, 58);
        font-family: Open Sans, sans-serif;
        height: 90vh;
      }
      #root {
        height: 100%;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .loading {
        font-size: 32px;
        font-weight: 200;
        color: rgba(255, 255, 255, .6);
        margin-left: 20px;
      }
      img {
        width: 78px;
        height: 78px;
      }
      .title {
        font-weight: 400;
      }
    </style>
    <img src='//cdn.jsdelivr.net/npm/graphql-playground-react/build/logo.png' alt=''>
    <div class="loading"> Loading
      <span class="title">GraphQL Playground</span>
    </div>
  </div>
  <script>window.addEventListener('load', function (event) {
      GraphQLPlayground.init(document.getElementById('root'), PLAYGROUND_OPTIONS)
    })</script>
</body>
</html>
""".strip()  # noqa: B950

_GRAPHIQL_HTML = """
<!DOCTYPE html>
<html>
<head>
  <style>
    html, body {
      height: 100%;
      margin: 0;
      overflow: hidden;
      width: 100%;
    }
    #graphiql {
      height: 100vh;
    }
  </style>
  <link href="//unpkg.com/graphiql/graphiql.css" rel="stylesheet"/>
  <script src="//unpkg.com/react@16/umd/react.production.min.js"></script>
  <script src="//unpkg.com/react-dom@16/umd/react-dom.production.min.js"></script>
  <script src="//unpkg.com/subscriptions-transport-ws@0.7.0/browser/client.js"></script>
  <script src="//unpkg.com/graphiql-subscriptions-fetcher@0.0.2/browser/client.js"></script>
</head>
<body>
  <script src="//unpkg.com/graphiql/graphiql.min.js"></script>
  <script>
    // Parse the cookie value for a CSRF token
    var csrftoken;
    var cookies = ('; ' + document.cookie).split('; csrftoken=');
    if (cookies.length == 2)
      csrftoken = cookies.pop().split(';').shift();

    // Collect the URL parameters
    var parameters = {};
    window.location.search.substr(1).split('&').forEach(function (entry) {
      var eq = entry.indexOf('=');
      if (eq >= 0) {
        parameters[decodeURIComponent(entry.slice(0, eq))] =
          decodeURIComponent(entry.slice(eq + 1));
      }
    });

    // Produce a Location query string from a parameter object.
    var graphqlParamNames = {
      query: true,
      variables: true,
      operationName: true
    };
    var otherParams = {};
    for (var k in parameters) {
      if (parameters.hasOwnProperty(k) && graphqlParamNames[k] !== true) {
        otherParams[k] = parameters[k];
      }
    }
    var fetchURL = '?' + Object.keys(otherParams).map(function (key) {
      return encodeURIComponent(key) + '=' +
          encodeURIComponent(otherParams[key]);
      }
    ).join('&');

    // Defines a GraphQL fetcher using the fetch API.
    function graphQLFetcher(graphQLParams) {
      var headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      };
      if (csrftoken) {
        headers['X-CSRFToken'] = csrftoken;
      }
      return fetch(fetchURL, {
        method: 'post',
        headers: headers,
        body: JSON.stringify(graphQLParams),
        credentials: 'include',
      }).then(function (response) {
        return response.text();
      }).then(function (responseBody) {
        try {
          return JSON.parse(responseBody);
        } catch (error) {
          return responseBody;
        }
      });
    }

    // if variables was provided, try to format it.
    if (parameters.variables) {
      try {
        parameters.variables =
          JSON.stringify(JSON.parse(parameters.variables), null, 2);
      } catch (e) {
        // Do nothing, we want to display the invalid JSON as a string, rather
        // than present an error.
      }
    }

    // When the query and variables string is edited, update the URL bar so
    // that it can be easily shared
    function onEditQuery(newQuery) {
      parameters.query = newQuery;
      updateURL();
    }
    function onEditVariables(newVariables) {
      parameters.variables = newVariables;
      updateURL();
    }
    function onEditOperationName(newOperationName) {
      parameters.operationName = newOperationName;
      updateURL();
    }
    function updateURL() {
      history.replaceState(null, null, locationQuery(parameters));
    }
    var subscriptionsEndpoint = (location.protocol === 'http:' ? 'ws' : 'wss') + '://' + location.host + location.pathname;
    var subscriptionsClient = new window.SubscriptionsTransportWs.SubscriptionClient(subscriptionsEndpoint, {
      reconnect: true
    });
    var fetcher = window.GraphiQLSubscriptionsFetcher.graphQLFetcher(subscriptionsClient, graphQLFetcher);

    // Render <GraphiQL /> into the body.
    ReactDOM.render(
      React.createElement(GraphiQL, {
        fetcher: fetcher,
        query: parameters.query,
        variables: parameters.variables,
        operationName: parameters.operationName,
        onEditQuery: onEditQuery,
        onEditVariables: onEditVariables,
        onEditOperationName: onEditOperationName,
      }),
      document.body
    );
  </script>
</body>
</html>
""".strip()  # noqa: B950
