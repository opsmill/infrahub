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
| Mode `enforce`, state `expiring`, `unlicensed`, `invalid`, `not_yet_valid`, `expired` | Sent, value = state |
| Path is `/api`, starts with `/api/`, is `/graphql` or starts with `/graphql/` | Eligible |
| Any other path (`/api-static/...`, `/assets/...`, `/favicons/...`, `/docs/...`, the frontend's HTML routes) | Never sent |

- One value, the state name. Clients map it to their own message.
- Error responses (4xx, 5xx) on eligible paths carry it too.
- It is sent whatever the authentication, including to callers who are not signed in. This is deliberate: it carries only the state, never the customer name, the failure reason or any other license detail.
- It is the one deliberate place where a caller who is not signed in sees the state: `GET /api/info` gives such callers `license: null` ([api-info.md](api-info.md)).
- If computing the notice raises, the response is sent without the header and the error is logged.
