from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts

from infrahub.graphql.api.dependencies import get_graphql_query_permission_checker
from infrahub.prefect_server.app import router as task_manager_router
from infrahub.prefect_server.events import get_prefect_database
from infrahub.server import app

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from fastapi.dependencies.models import Dependant
    from starlette.routing import BaseRoute


@dataclass
class RouteDependenciesTestCase:
    name: str
    routes: Sequence[BaseRoute]
    known_dependency: Callable[..., Any]
    known_dependency_routes: set[str]
    """Routes that use the known dependency, which shows the walk reaches nested routers and dependencies."""


ROUTE_DEPENDENCIES_TEST_CASES: list[RouteDependenciesTestCase] = [
    RouteDependenciesTestCase(
        name="api_server",
        routes=app.routes,
        known_dependency=get_graphql_query_permission_checker,
        known_dependency_routes={"GET /api/query/{query_id}", "POST /api/query/{query_id}"},
    ),
    RouteDependenciesTestCase(
        name="task_manager",
        routes=task_manager_router.routes,
        known_dependency=get_prefect_database,
        known_dependency_routes={"POST /infrahub/events/filter"},
    ),
]


def _dependency_calls(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            yield dependency.call
        yield from _dependency_calls(dependency)


def _route_dependencies(routes: Sequence[BaseRoute]) -> set[tuple[str, Callable[..., Any]]]:
    dependencies: set[tuple[str, Callable[..., Any]]] = set()
    for context in iter_route_contexts(routes):
        if not isinstance(context.original_route, APIRoute | APIWebSocketRoute):
            continue
        route = f"{','.join(sorted(context.methods or ['WEBSOCKET']))} {context.path}"
        dependencies.update((route, call) for call in _dependency_calls(context.dependant))
    return dependencies


def _resolves_on_event_loop(call: Callable[..., Any]) -> bool:
    if inspect.isclass(call):
        return False
    function = call if inspect.isroutine(call) else type(call).__call__
    return inspect.iscoroutinefunction(function) or inspect.isasyncgenfunction(function)


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in ROUTE_DEPENDENCIES_TEST_CASES],
)
def test_route_dependencies_resolve_on_the_event_loop(test_case: RouteDependenciesTestCase) -> None:
    """FastAPI resolves a sync dependency in a worker thread, which costs a thread handoff on every request."""
    dependencies = _route_dependencies(test_case.routes)
    sync_dependencies = sorted(
        f"{route}: {call.__module__}.{call.__qualname__}"
        for route, call in dependencies
        if not _resolves_on_event_loop(call)
    )

    assert sync_dependencies == []
    assert {route for route, call in dependencies if call is test_case.known_dependency} == (
        test_case.known_dependency_routes
    )
