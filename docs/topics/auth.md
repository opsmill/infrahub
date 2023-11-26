---
label: User management and authentication
layout: default
---

# User management and authentication

Infrahub now supports standard user management and authentication systems.

A user account can have 3 levels of permissions

- `admin`
- `read-write`
- `read-only`

By default, Infrahub will allow anonymous access in read-only. It's possible to disable this via the configuration `main.allow_anonymous_access` or via the environment variable `INFRAHUB_ALLOW_ANONYMOUS_ACCESS`.

## Authentication mechanisms

Infrahub supports two authentication methods

- JWT token: Short life tokens generated on demand from the API.
- API Token: Long life tokens generated ahead of time.

> API tokens can be generated via the user profile page or via the GraphQL interface.

|                    | JWT  | TOKEN |
| ------------------ | ---- | ----- |
| API / GraphQL      | Yes  | Yes   |
| Frontend           | Yes  | No    |
| Python SDK         | Soon | Yes   |
| infrahubctl        | Soon | Yes   |
| GraphQL Playground | No   | Yes   |

!!!

While using the API, the authentication token must be provided in a header named `X-INFRAHUB-KEY`.

!!!
