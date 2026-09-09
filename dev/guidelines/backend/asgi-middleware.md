# ASGI Middleware

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md), [API Backpressure](../../knowledge/backend/api-backpressure.md)

Writing FastAPI/Starlette middleware in the backend.

<!-- Extracted from specs/ifc-2886-priority-api-backpressure on 2026-07-26 -->

Write middleware as **pure ASGI** — `async def __call__(self, scope, receive, send)`, subclassing
nothing — when it runs on every request, may short-circuit a request, or sits anywhere near
streaming or background tasks:

```python
class SomeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ...
```

The `@app.middleware("http")` decorator wraps `BaseHTTPMiddleware`, which buffers the entire
response and interferes with streaming responses and background tasks. Reserve it for
non-hot-path work where that cost is irrelevant.

Rules that follow from the ASGI contract:

- Always pass non-`http` scopes (`websocket`, `lifespan`) straight through untouched.
- Short-circuit by constructing and sending the response yourself. Middleware runs outside the
  exception-handler scope, so raising will not reach FastAPI's registered handlers, and those
  handlers cannot attach custom response headers.
- Registration order is inverted: Starlette inserts each `add_middleware(...)` at the front, so
  the **last** registered runs **first** (outermost). Put a gate that must run before auth,
  routing, and telemetry last in `server.py`.
- Anything resolved by `Depends(...)` — including the authenticated user — is not available;
  dependencies resolve per route, after all middleware.

Worked example: `backend/infrahub/api/admission/middleware.py`, with the reasoning in
[API Backpressure](../../knowledge/backend/api-backpressure.md#why-its-built-this-way).

## See Also

- [Python Standards](python.md) - Typing, imports, data structures, path matching
- [API Backpressure](../../knowledge/backend/api-backpressure.md) - Why the admission gate is built this way
