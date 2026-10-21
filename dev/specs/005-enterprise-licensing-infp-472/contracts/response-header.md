# Contract: `X-Infrahub-License-Status` response header

```http
# Today: no license information in responses

# After, enforce mode (second licensing release), license expired
HTTP/1.1 200 OK
X-Infrahub-License-Status: expired
```

## Rules

| Condition | Header |
| --- | --- |
| Mode `quiet` (first licensing release) | Never sent |
| Mode `enforce`, state `not_required` or `valid` | Not sent |
| Mode `enforce`, state `invalid` with reason `internal_error` | Not sent: a defect in Infrahub, not in the customer's license |
| Mode `enforce`, state `expiring`, `unlicensed`, `invalid`, `not_yet_valid`, `expired` | Sent, value = state |
| Path is `/api`, starts with `/api/`, is `/graphql` or starts with `/graphql/` | Eligible |
| Any other path (`/api-static/...`, `/assets/...`, `/favicons/...`, `/docs/...`, the frontend's HTML routes) | Never sent |

- One value, the state name. Clients map it to their own message.
- Error responses on eligible paths carry it when an exception handler renders them: a 401, a 404, or a 500 from an Infrahub `Error` handler. Two error responses never carry it:
  - a 429 from the admission middleware, which sheds the request before the header middleware runs;
  - a 500 for an exception with no registered handler, which Starlette's `ServerErrorMiddleware` renders outside every application middleware.
- `GET /graphql` with `Accept: text/html` serves the frontend's GraphQL page and carries the header, because the path rule decides.
- The header is not in the CORS expose list, so browser JavaScript on another origin cannot read it. Clients that are not browsers, such as the SDK and the MCP server, are unaffected.
- It is sent whatever the authentication, including to callers who are not signed in. This is deliberate: it carries only the state, never the customer name, the failure reason or any other license detail.
- It is the one deliberate place where a caller who is not signed in sees the state: `GET /api/info` gives such callers `license: null` ([api-info.md](api-info.md)).
- If computing the notice raises, the response is sent without the header. The traceback is logged once per process: once per exception type for an error the license service raises, and once for an error in the header middleware itself.
