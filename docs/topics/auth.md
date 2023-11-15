---
label: User Management and Authentication
layout: default
---

### User Management and Authentication

Infrahub now supports standard user management and authentication systems.

A user account can have 3 levels of permissions
- `admin`
- `read-write`
- `read-only`

By default, Infrahub will allow anonymous access in read-only. it's possible to disable this feature via the configuration `main.allow_anonymous_access` or via the environment variable `INFRAHUB_ALLOW_ANONYMOUS_ACCESS`


#### Authentication mechanisms

Infrahub supports two authentication methods
- JWT token: Short live token that are generated on demand from the API
- API Token: Long live token generated ahead of time.

> API token can be generated via the user profile page or via the Graphql interface.

|                    | JWT  | TOKEN |
| ------------------ | ---- | ----- |
| API / GraphQL      | Yes  | Yes   |
| Frontend           | Yes  | No    |
| Python SDK         | Soon | Yes   |
| infrahubctl        | Soon | Yes   |
| GraphQL Playground | No   | Yes   |

While using the API the Authentication Token must be provided in a header named `X-INFRAHUB-KEY`

