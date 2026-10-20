from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from infrahub.api.admission.middleware import SHED_MARKER_HEADER, SHED_MARKER_VALUE
from infrahub.config import default_cors_allow_headers, default_cors_allow_methods
from infrahub.middleware import CORS_EXPOSE_HEADERS, InfrahubCORSMiddleware
from tests.helpers.admission import install_admission, shed_everything_controller

_ORIGIN = "https://frontend.example"


def _shed_everything_app() -> FastAPI:
    """A bare app with one route, to be gated by a shed-everything controller: every gated call is a 429."""
    app = FastAPI()

    @app.post("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    return app


def _build_app(*, cors_outermost: bool = True) -> FastAPI:
    """App wired like the server: CORS from the shipped defaults around the shed-everything gate.

    ``cors_outermost=False`` puts the gate outside CORS instead, which is what proves the preflight
    exemption holds on its own rather than because CORS answered first.
    """
    app = _shed_everything_app()

    def add_cors() -> None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[_ORIGIN],
            allow_methods=default_cors_allow_methods(),
            allow_headers=default_cors_allow_headers(),
            allow_credentials=True,
            expose_headers=CORS_EXPOSE_HEADERS,
        )

    def add_gate() -> None:
        install_admission(app, shed_everything_controller())

    # Starlette runs the last registered middleware first, so the outermost one is added last.
    for add in (add_gate, add_cors) if cors_outermost else (add_cors, add_gate):
        add()
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("cors_outermost", [True, False], ids=["production-order", "gate-outermost"])
async def test_cors_preflight_allows_x_priority(cors_outermost: bool) -> None:
    """A cross-origin preflight succeeds and x-priority is in the allow-headers, even under shedding.

    In the production order CORS answers the preflight before the gate sees it. With the gate
    outermost, the 200 can only mean the preflight bypassed the (shed-everything) gate, so the
    exemption holds on its own. Either way the allow-headers value proves the shipped default lets
    a cross-origin browser send X-Priority.
    """
    async with _client(_build_app(cors_outermost=cors_outermost)) as client:
        response = await client.options(
            "/work",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-priority",
            },
        )

    assert response.status_code == 200
    assert "x-priority" in response.headers["access-control-allow-headers"].lower()


async def test_non_preflight_request_is_still_shed() -> None:
    """The preflight exemption is narrow: a real cross-origin request is still admission-gated."""
    async with _client(_build_app()) as client:
        response = await client.post("/work", headers={"Origin": _ORIGIN, "X-Priority": "low"})

    assert response.status_code == 429


async def test_shed_response_is_readable_cross_origin() -> None:
    """A shed 429 has the CORS headers a browser needs to hand the response to the client.

    Without the allow-origin the browser blocks the response outright and the client sees an
    opaque network error. Without retry-after and the shed marker in the expose-list it can read
    the status but neither the advised wait nor the proof that the request never reached a
    handler, which is what lets it replay a mutation.
    """
    async with _client(_build_app()) as client:
        response = await client.post("/work", headers={"Origin": _ORIGIN, "X-Priority": "low"})

    assert response.status_code == 429
    assert response.headers["retry-after"]
    assert response.headers[SHED_MARKER_HEADER] == SHED_MARKER_VALUE
    assert response.headers["access-control-allow-origin"] == _ORIGIN
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed
    assert SHED_MARKER_HEADER.lower() in exposed


async def test_server_cors_middleware_wires_the_expose_list() -> None:
    """The server's own CORS middleware exposes the shed headers.

    The tests above wire Starlette's middleware with the expose-list directly, so this is the one
    that fails if ``InfrahubCORSMiddleware`` stops setting it.
    """
    app = _shed_everything_app()
    install_admission(app, shed_everything_controller())
    app.add_middleware(InfrahubCORSMiddleware)

    async with _client(app) as client:
        response = await client.post("/work", headers={"Origin": _ORIGIN, "X-Priority": "low"})

    assert response.status_code == 429
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed
    assert SHED_MARKER_HEADER.lower() in exposed
