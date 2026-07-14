# Contract: CORS Preflight Allows `x-priority`

**Feature**: IFC-2890 | **Type**: Backend CORS contract

Covers FR-006: cross-origin frontends must be able to send `X-Priority`.

## Change

`backend/infrahub/config.py :: default_cors_allow_headers()` appends `"x-priority"` to its returned list. The value flows through `ApiSettings.cors_allow_headers` → `InfrahubCORSMiddleware` (`backend/infrahub/middleware.py`) → the `Access-Control-Allow-Headers` response.

New default list (order not significant):

```
accept, authorization, content-type, user-agent, x-csrftoken, x-requested-with, x-priority
```

## Guarantees

```
GIVEN a cross-origin browser about to send a request carrying X-Priority
WHEN it issues the CORS preflight
     OPTIONS <any Infrahub API path>
       Origin: https://frontend.example
       Access-Control-Request-Method: POST
       Access-Control-Request-Headers: x-priority
THEN the response is 200
AND  `Access-Control-Allow-Headers` includes `x-priority`

GIVEN the preflight succeeded
WHEN the actual cross-origin request carrying `X-Priority: high` is sent
THEN the browser does not block it
AND  the request is accepted and processed by the server
```

## Notes

- The header value semantics are unchanged; the admission layer (IFC-2886) already parses `x-priority`. This contract only concerns the CORS allow-list.
- Same-origin production deployments do not preflight; this contract is verified explicitly precisely because same-origin cannot catch a missing allow-list entry (the "passes in prod, fails in dev" trap).
- Operators may override `cors_allow_headers` via `INFRAHUB_API_CORS_ALLOW_HEADERS`; an override that omits `x-priority` would break cross-origin priority — documented, not enforced.

## Verification

A backend component test issues the OPTIONS preflight above against a test app whose CORS config is built from the shipped default and asserts `x-priority` appears in `Access-Control-Allow-Headers`. See [quickstart.md](../quickstart.md).
