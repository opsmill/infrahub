from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.routing import Route

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def frontend_app(tmp_path: Path) -> FastAPI:
    """App wired like the server: real API routes plus the SPA served via app.frontend().

    The frontend is registered as a low-priority route group, exactly as in the server, so it is
    only consulted after the API routes and can never shadow them. The POST-only /graphql API
    route plus the explicit /graphql GET SPA routes mirror the server: /graphql is both a
    POST-only API endpoint and a browser-navigable SPA view, so a GET must still reach the SPA.
    """
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    index = dist / "index.html"
    index.write_text("<!doctype html><title>Infrahub</title>")
    (dist / "assets" / "app.js").write_text("console.log('app')")

    app = FastAPI(openapi_url="/api/openapi.json")

    @app.get("/api/known")
    async def known() -> dict[str, bool]:
        return {"ok": True}

    async def graphql_api(request: Request) -> PlainTextResponse:
        return PlainTextResponse("graphql")

    app.router.routes.append(Route(path="/graphql", endpoint=graphql_api, methods=["POST", "OPTIONS"]))
    app.router.routes.append(
        Route(path="/graphql/{branch_name:path}", endpoint=graphql_api, methods=["POST", "OPTIONS"])
    )

    app.frontend("/", directory=dist, fallback="auto", check_dir=False)

    async def graphql_sandbox_app(branch_name: str = "") -> FileResponse:
        return FileResponse(index)

    app.add_api_route("/graphql", graphql_sandbox_app, include_in_schema=False)
    app.add_api_route("/graphql/{branch_name:path}", graphql_sandbox_app, include_in_schema=False)
    return app


def test_known_api_route_is_not_shadowed(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/api/known")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unknown_api_path_non_html_returns_404(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/api/does-not-exist", headers={"accept": "application/json"})
    assert response.status_code == 404


def test_unknown_api_path_browser_navigation_returns_index(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/api/does-not-exist", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text


def test_browser_deep_link_returns_index(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/objects/some-node", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text


def test_root_returns_index(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text


def test_static_asset_is_served(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_graphql_api_post_is_not_shadowed(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.post("/graphql")
    assert response.status_code == 200
    assert response.text == "graphql"


def test_graphql_sandbox_browser_navigation_returns_index(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/graphql", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text


def test_graphql_sandbox_branch_deep_link_returns_index(frontend_app: FastAPI) -> None:
    client = TestClient(frontend_app)
    response = client.get("/graphql/main", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text


@pytest.fixture
def instrumented_frontend_app(frontend_app: FastAPI) -> Iterator[FastAPI]:
    """The app wired like the server but wrapped with the OpenTelemetry FastAPI instrumentor.

    opentelemetry-instrumentation-fastapi before 0.64b0 read a route attribute that FastAPI 0.137+
    no longer exposes on the wrapper objects stored in app.routes, so resolving the span name for a
    method-mismatched request raised inside the instrumentation and returned a 500 before routing.
    A browser GET against the POST-only /graphql API is exactly such a method mismatch, so the
    instrumented app is the setup where that regression surfaced.
    """
    FastAPIInstrumentor().instrument_app(frontend_app)
    yield frontend_app
    FastAPIInstrumentor().uninstrument_app(frontend_app)


def test_graphql_sandbox_reachable_through_instrumented_app(instrumented_frontend_app: FastAPI) -> None:
    client = TestClient(instrumented_frontend_app)
    response = client.get("/graphql", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "<title>Infrahub</title>" in response.text
